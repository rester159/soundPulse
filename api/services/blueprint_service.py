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
    Opportunity Score v2 — breakout-informed ranking.

    Replaces the naive v1 formula (which ranked niche genres with 2-3
    tracks at the top because saturation was inverted). v2 uses signals
    that actually predict songwriting success:

      breakout_rate    = % of tracks in this genre that have broken out
      momentum         = recent velocity trend (acceleration)
      hit_quality      = avg composite ratio of breakout tracks
      competitive_gap  = unique_artists / track_count (open field?)
      data_confidence  = sample size confidence

    The formula is intentionally biased toward genres with PROVEN breakout
    activity, not just high theoretical "momentum × quality - saturation."
    See planning/PRD/breakoutengine_prd.md §8 for the rationale.
    """
    from sqlalchemy import text as sa_text

    # Aggregate everything we need in one SQL pass: track count, breakout
    # count, avg composite/velocity, unique artists, avg breakout score,
    # all per genre (using tracks.genres array — the classified taxonomy).
    result = await db.execute(sa_text("""
        WITH genre_tracks AS (
            SELECT
                UNNEST(t.genres) AS genre_id,
                t.id AS track_id,
                t.artist_id
            FROM tracks t
            WHERE t.genres IS NOT NULL
              AND array_length(t.genres, 1) > 0
        ),
        genre_stats AS (
            SELECT
                gt.genre_id,
                COUNT(DISTINCT gt.track_id) AS track_count,
                COUNT(DISTINCT gt.artist_id) AS unique_artists,
                AVG(ts.composite_score) AS avg_composite,
                AVG(ts.velocity) AS avg_velocity
            FROM genre_tracks gt
            LEFT JOIN trending_snapshots ts
                ON ts.entity_id = gt.track_id
                AND ts.entity_type = 'track'
                AND ts.snapshot_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY gt.genre_id
        ),
        breakout_stats AS (
            SELECT
                genre_id,
                COUNT(*) AS breakout_count,
                AVG(breakout_score) AS avg_breakout_score,
                AVG(composite_ratio) AS avg_composite_ratio,
                AVG(velocity_ratio) AS avg_velocity_ratio
            FROM breakout_events
            WHERE detection_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY genre_id
        )
        SELECT
            gs.genre_id,
            gs.track_count,
            gs.unique_artists,
            COALESCE(gs.avg_composite, 0) AS avg_composite,
            COALESCE(gs.avg_velocity, 0) AS avg_velocity,
            COALESCE(bs.breakout_count, 0) AS breakout_count,
            COALESCE(bs.avg_breakout_score, 0) AS avg_breakout_score,
            COALESCE(bs.avg_composite_ratio, 0) AS avg_composite_ratio,
            COALESCE(bs.avg_velocity_ratio, 0) AS avg_velocity_ratio
        FROM genre_stats gs
        LEFT JOIN breakout_stats bs ON bs.genre_id = gs.genre_id
        WHERE gs.track_count >= 3
    """))

    rows = result.fetchall()

    opportunities = []
    for row in rows:
        genre_id = row[0]
        track_count = int(row[1])
        unique_artists = int(row[2])
        avg_composite = float(row[3])
        avg_velocity = float(row[4])
        breakout_count = int(row[5])
        avg_breakout_score = float(row[6])
        avg_composite_ratio = float(row[7])
        avg_velocity_ratio = float(row[8])

        # ---- v2 formula components ----
        # 1. Breakout rate: % of tracks that achieved breakout status
        breakout_rate = breakout_count / max(track_count, 1)
        breakout_rate_score = min(breakout_rate * 5, 1.0)  # 20% breakout rate = max

        # 2. Hit quality: how dramatic are the breakouts?
        # avg_composite_ratio of 5x = strong, 10x = exceptional
        hit_quality_score = min(avg_composite_ratio / 8.0, 1.0)

        # 3. Momentum: average velocity ratio of breakouts
        # 5x normal velocity = strong viral signal, 20x = exceptional
        momentum_score = min(avg_velocity_ratio / 10.0, 1.0)

        # 4. Competitive gap: unique artists per track
        # Higher = more diverse, open field. Lower = dominated by few.
        artist_diversity = unique_artists / max(track_count, 1)
        competitive_gap = artist_diversity  # already in [0, 1]

        # 5. Data confidence: penalty for tiny sample sizes
        confidence = min(track_count / 20.0, 1.0)

        # ---- Combined score ----
        # Weights bias toward genres with PROVEN breakout activity:
        # 35% breakout rate + 25% hit quality + 20% momentum + 10% gap + 10% confidence
        opportunity = (
            0.35 * breakout_rate_score +
            0.25 * hit_quality_score +
            0.20 * momentum_score +
            0.10 * competitive_gap +
            0.10 * confidence
        )

        # Momentum label
        if avg_velocity_ratio >= 3:
            momentum_label = "rising"
        elif avg_velocity_ratio >= 1.2:
            momentum_label = "stable"
        else:
            momentum_label = "declining"

        opportunities.append({
            "genre": genre_id,
            "genre_name": genre_id.replace(".", " > ").replace("-", " ").title(),
            "opportunity_score": round(opportunity, 3),
            "confidence": round(confidence, 2),
            "track_count": track_count,
            "unique_artists": unique_artists,
            "breakout_count": breakout_count,
            "breakout_rate": round(breakout_rate, 3),
            "avg_composite": round(avg_composite, 1),
            "avg_velocity": round(avg_velocity, 2),
            "avg_breakout_score": round(avg_breakout_score, 3),
            "avg_composite_ratio": round(avg_composite_ratio, 2),
            "avg_velocity_ratio": round(avg_velocity_ratio, 2),
            "momentum": momentum_label,
            # Component breakdown (for transparency in the UI)
            "score_breakdown": {
                "breakout_rate": round(breakout_rate_score, 3),
                "hit_quality": round(hit_quality_score, 3),
                "momentum": round(momentum_score, 3),
                "competitive_gap": round(competitive_gap, 3),
                "confidence": round(confidence, 3),
            },
        })

    # Sort by opportunity score, but require at least 1 breakout to surface
    # in the top results — pure baseline genres go below the breakout-genres.
    opportunities.sort(
        key=lambda x: (x["breakout_count"] > 0, x["opportunity_score"]),
        reverse=True,
    )
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
    # Anchor to most recent data so historical backfill always shows
    latest_row = await db.execute(
        select(func.max(TrendingSnapshot.snapshot_date))
        .where(TrendingSnapshot.entity_type == "track")
    )
    latest_date = latest_row.scalar() or date.today()
    lookback = latest_date - timedelta(days=60)

    # Get tracks in this genre. JOIN to tracks table so we have
    # access to tracks.audio_features — the canonical source for
    # tempo/energy/danceability/etc. Previously this read audio
    # features from signals_json, but chart-data snapshots don't
    # carry audio_features in their signals. The actual features
    # are stored on the track row by the Tunebat/Chartmetric
    # audio enrichment pipeline.
    result = await db.execute(
        select(
            TrendingSnapshot.entity_id,
            TrendingSnapshot.composite_score,
            TrendingSnapshot.velocity,
            TrendingSnapshot.signals_json,
            Track.audio_features,
        )
        .join(Track, Track.id == TrendingSnapshot.entity_id)
        .where(TrendingSnapshot.snapshot_date >= lookback)
        .where(TrendingSnapshot.entity_type == "track")
        .where(TrendingSnapshot.signals_json.isnot(None))
        .order_by(TrendingSnapshot.composite_score.desc().nullslast())
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

        # Audio features: prefer the track-level column (canonical,
        # populated by Tunebat/Chartmetric enrichment pipelines),
        # fall back to signals_json.audio_features for snapshots
        # that carry features inline.
        af = track.audio_features if hasattr(track, 'audio_features') and track.audio_features else {}
        if not af:
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
