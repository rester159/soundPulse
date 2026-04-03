"""
Blueprint service — generates Song DNA blueprints and music generation prompts.

Analyzes what's working in a genre right now and translates it into
actionable prompts for Suno, Udio, and SOUNDRAW.
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select, text, and_
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.trending_snapshot import TrendingSnapshot
from api.models.track import Track
from api.models.genre import Genre

logger = logging.getLogger(__name__)

# Key-to-name mapping
KEY_NAMES = {0: "C", 1: "C#", 2: "D", 3: "D#", 4: "E", 5: "F",
             6: "F#", 7: "G", 8: "G#", 9: "A", 10: "A#", 11: "B"}
MODE_NAMES = {0: "minor", 1: "major"}


async def get_genre_opportunities(db: AsyncSession) -> list[dict]:
    """
    Rank genres by opportunity score = trending velocity x inverse saturation.
    Returns genres sorted by which ones have the most untapped potential.
    """
    lookback = date.today() - timedelta(days=60)

    # Get recent snapshots with their signals (which contain genre data)
    result = await db.execute(
        select(
            TrendingSnapshot.entity_id,
            TrendingSnapshot.composite_score,
            TrendingSnapshot.velocity,
            TrendingSnapshot.signals_json,
        )
        .where(TrendingSnapshot.snapshot_date >= lookback)
        .where(TrendingSnapshot.entity_type == "track")
        .where(TrendingSnapshot.signals_json.isnot(None))
    )
    rows = result.all()

    # Extract genres from signals and aggregate
    genre_data: dict[str, dict] = {}
    seen_entities: dict[str, set] = {}

    for row in rows:
        signals = row.signals_json or {}
        # Genre info comes from Chartmetric as "genres" (string like "pop, indie pop")
        # or from Spotify as "spotify_genres" (list)
        genre_str = signals.get("genres") or signals.get("track_genre") or ""
        genre_list = signals.get("spotify_genres") or []

        if isinstance(genre_str, str) and genre_str:
            genre_list = genre_list + [g.strip() for g in genre_str.split(",") if g.strip()]

        if not genre_list:
            continue

        for genre_tag in genre_list:
            genre_tag = genre_tag.strip().lower()
            if not genre_tag or len(genre_tag) < 2:
                continue

            if genre_tag not in genre_data:
                genre_data[genre_tag] = {
                    "total_composite": 0,
                    "total_velocity": 0,
                    "count": 0,
                }
                seen_entities[genre_tag] = set()

            gd = genre_data[genre_tag]
            gd["total_composite"] += row.composite_score or 0
            gd["total_velocity"] += row.velocity or 0
            gd["count"] += 1
            seen_entities[genre_tag].add(str(row.entity_id))

    # Compute opportunity scores
    opportunities = []
    for genre_tag, gd in genre_data.items():
        track_count = len(seen_entities.get(genre_tag, set()))
        if track_count < 2:
            continue

        avg_composite = gd["total_composite"] / gd["count"] if gd["count"] > 0 else 0
        avg_velocity = gd["total_velocity"] / gd["count"] if gd["count"] > 0 else 0

        # Opportunity = momentum (high velocity) + quality (high composite) - saturation (too many = crowded)
        momentum = max(0, avg_velocity) / 10  # normalize
        quality = avg_composite / 100
        saturation = min(1.0, track_count / 50)  # >50 tracks = fully saturated

        opportunity = (0.4 * momentum + 0.4 * quality + 0.2 * (1 - saturation))
        confidence = min(1.0, track_count / 10)

        opportunities.append({
            "genre": genre_tag,
            "genre_name": genre_tag.replace(".", " > ").replace("-", " ").title(),
            "opportunity_score": round(max(0, opportunity), 3),
            "confidence": round(confidence, 2),
            "track_count": track_count,
            "avg_composite": round(avg_composite, 1),
            "avg_velocity": round(avg_velocity, 2),
            "momentum": "rising" if avg_velocity > 0.5 else "stable" if avg_velocity > -0.5 else "declining",
        })

    opportunities.sort(key=lambda x: x["opportunity_score"], reverse=True)
    return opportunities[:50]


async def generate_blueprint(
    db: AsyncSession,
    genre: str,
    model: str = "suno",
) -> dict[str, Any]:
    """
    Generate a Song DNA blueprint for the given genre based on what's
    currently trending, then translate it to a model-specific prompt.
    """
    lookback = date.today() - timedelta(days=30)

    # Get tracks in this genre by searching signals for the genre tag
    result = await db.execute(
        select(
            TrendingSnapshot.entity_id,
            TrendingSnapshot.composite_score,
            TrendingSnapshot.velocity,
            TrendingSnapshot.signals_json,
        )
        .where(TrendingSnapshot.snapshot_date >= lookback)
        .where(TrendingSnapshot.entity_type == "track")
        .where(TrendingSnapshot.signals_json.isnot(None))
        .order_by(TrendingSnapshot.composite_score.desc())
        .limit(200)
    )
    all_snapshots = result.all()

    # Filter to those matching the genre
    tracks = []
    for row in all_snapshots:
        signals = row.signals_json or {}
        genre_str = signals.get("genres") or signals.get("track_genre") or ""
        genre_list = signals.get("spotify_genres") or []
        if isinstance(genre_str, str):
            genre_list = genre_list + [g.strip().lower() for g in genre_str.split(",")]
        if genre.lower() in [g.lower() for g in genre_list]:
            tracks.append(row)
        if len(tracks) >= 50:
            break

    if not tracks:
        return {
            "blueprint": None,
            "prompt": None,
            "model": model,
            "error": f"No trending data found for genre '{genre}' in the last 30 days",
        }

    # Aggregate Song DNA features across top performers
    blueprint = _aggregate_song_dna(tracks, genre)

    # Generate model-specific prompt
    prompt = _generate_prompt(blueprint, model)

    return {
        "blueprint": blueprint,
        "prompt": prompt,
        "model": model,
        "genre": genre,
        "track_count": len(tracks),
    }


def _aggregate_song_dna(tracks: list, genre: str) -> dict:
    """Aggregate Song DNA features from a list of tracks."""
    tempos = []
    energies = []
    valences = []
    danceabilities = []
    keys = []
    modes = []
    acousticness_vals = []
    themes_count: dict[str, int] = {}
    genres_from_signals = []

    for track in tracks:
        signals = track.signals_json or {}

        # Audio features may be in signals (from spotify_audio enricher)
        af = signals.get("audio_features") or {}
        if af.get("tempo"):
            tempos.append(af["tempo"])
        if af.get("energy") is not None:
            energies.append(af["energy"])
        if af.get("valence") is not None:
            valences.append(af["valence"])
        if af.get("danceability") is not None:
            danceabilities.append(af["danceability"])
        if af.get("key") is not None:
            keys.append(af["key"])
        if af.get("mode") is not None:
            modes.append(af["mode"])
        if af.get("acousticness") is not None:
            acousticness_vals.append(af["acousticness"])

        # Spotify popularity as a proxy for energy/quality if no audio features
        if signals.get("spotify_popularity") is not None and not af:
            energies.append(min(1.0, signals["spotify_popularity"] / 100))

        # Lyrics themes
        if signals.get("primary_theme"):
            theme = signals["primary_theme"]
            themes_count[theme] = themes_count.get(theme, 0) + 1
        if signals.get("themes"):
            for t in signals["themes"]:
                themes_count[t] = themes_count.get(t, 0) + 1

        # Genre tags from signals
        genre_str = signals.get("genres") or signals.get("track_genre") or ""
        if isinstance(genre_str, str) and genre_str:
            genres_from_signals.append(genre_str)

    # Compute averages
    avg_tempo = round(sum(tempos) / len(tempos)) if tempos else None
    avg_energy = round(sum(energies) / len(energies), 2) if energies else None
    avg_valence = round(sum(valences) / len(valences), 2) if valences else None
    avg_danceability = round(sum(danceabilities) / len(danceabilities), 2) if danceabilities else None
    avg_acousticness = round(sum(acousticness_vals) / len(acousticness_vals), 2) if acousticness_vals else None

    # Dominant key and mode
    dominant_key = max(set(keys), key=keys.count) if keys else None
    dominant_mode = max(set(modes), key=modes.count) if modes else None

    key_name = KEY_NAMES.get(dominant_key, "?") if dominant_key is not None else None
    mode_name = MODE_NAMES.get(dominant_mode, "?") if dominant_mode is not None else None

    # Top themes
    sorted_themes = sorted(themes_count.items(), key=lambda x: x[1], reverse=True)
    top_themes = [t[0] for t in sorted_themes[:3]] if sorted_themes else ["general"]

    # Mood description
    if avg_valence is not None:
        if avg_valence < 0.3:
            mood = "dark, melancholic"
        elif avg_valence < 0.5:
            mood = "moody, atmospheric"
        elif avg_valence < 0.7:
            mood = "upbeat, positive"
        else:
            mood = "euphoric, energetic"
    else:
        mood = "varied"

    # Energy description
    if avg_energy is not None:
        if avg_energy < 0.4:
            energy_desc = "low-energy, chill"
        elif avg_energy < 0.7:
            energy_desc = "moderate energy"
        else:
            energy_desc = "high-energy, intense"
    else:
        energy_desc = "varied"

    return {
        "genre": genre,
        "genre_name": genre.replace(".", " > ").replace("-", " ").title(),
        "sample_size": len(tracks),
        "sonic_profile": {
            "tempo": avg_tempo,
            "tempo_range": f"{min(tempos):.0f}-{max(tempos):.0f}" if tempos else None,
            "key": key_name,
            "mode": mode_name,
            "key_display": f"{key_name} {mode_name}" if key_name and mode_name else None,
            "energy": avg_energy,
            "energy_description": energy_desc,
            "valence": avg_valence,
            "mood": mood,
            "danceability": avg_danceability,
            "acousticness": avg_acousticness,
        },
        "lyrical_profile": {
            "top_themes": top_themes,
            "primary_theme": top_themes[0] if top_themes else "general",
        },
        "recommendation": {
            "mood": mood,
            "energy": energy_desc,
            "structure": "[Intro] [Verse] [Pre-Chorus] [Chorus] [Verse] [Chorus] [Bridge] [Chorus] [Outro]",
        },
        "genre_tags": list(set(genres_from_signals))[:5] if genres_from_signals else [genre],
    }


def _generate_prompt(blueprint: dict, model: str) -> str | dict:
    """Translate a blueprint into a model-specific prompt."""
    sp = blueprint.get("sonic_profile", {})
    lp = blueprint.get("lyrical_profile", {})
    genre = blueprint.get("genre_name", "pop")

    tempo = sp.get("tempo")
    key_display = sp.get("key_display")
    mood = sp.get("mood", "varied")
    energy_desc = sp.get("energy_description", "moderate")
    themes = lp.get("top_themes", ["general"])
    theme_str = ", ".join(themes)

    if model == "suno":
        style_parts = [genre.lower()]
        if tempo:
            style_parts.append(f"{tempo} BPM")
        if key_display:
            style_parts.append(key_display)
        style_parts.append(f"{mood} mood")
        style_parts.append(energy_desc)

        style = ", ".join(style_parts)

        lyrics = f"""[Intro]
(Atmospheric opening, {mood} tone)

[Verse 1]
(Theme: {theme_str}. Write 4-6 lines.)

[Pre-Chorus]
(Building tension toward the hook)

[Chorus]
(Catchy, memorable hook. Theme: {theme_str}.)

[Verse 2]
(Deeper exploration of theme. 4-6 lines.)

[Chorus]
(Repeat hook with slight variation)

[Bridge]
(Emotional shift or new perspective)

[Chorus]
(Final hook, full energy)

[Outro]
(Fade or resolution)"""

        return f"STYLE: {style}\n\n---\n\nLYRICS:\n{lyrics}"

    elif model == "udio":
        parts = [genre.lower()]
        if tempo:
            parts.append(f"{tempo} BPM")
        if mood:
            parts.append(f"{mood}")
        if energy_desc:
            parts.append(energy_desc)
        parts.append(f"Themes: {theme_str}")

        return "PROMPT: " + ", ".join(parts)

    elif model == "soundraw":
        mood_map = {
            "dark, melancholic": "Sad",
            "moody, atmospheric": "Mysterious",
            "upbeat, positive": "Happy",
            "euphoric, energetic": "Powerful",
        }

        return {
            "mood": mood_map.get(mood, "Dreamy"),
            "genre": genre.split(" > ")[0] if " > " in genre else genre,
            "tempo": tempo or 120,
            "energy_levels": "medium" if (sp.get("energy") or 0.5) < 0.7 else "high",
            "length": 180,
        }

    elif model == "musicgen":
        parts = [genre.lower()]
        if tempo:
            parts.append(f"{tempo} BPM")
        if mood:
            parts.append(mood)
        if energy_desc:
            parts.append(energy_desc)
        parts.append("instrumental")

        return "PROMPT: " + ", ".join(parts)

    return f"Genre: {genre}, Mood: {mood}, Tempo: {tempo}, Themes: {theme_str}"
