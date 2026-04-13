"""
Song generation orchestrator (§24, T-160).

Given a blueprint with an approved `assigned_artist_id`, build the final
prompt, call the chosen music provider, and persist a `songs_master`
row in `draft` status alongside the `music_generation_calls` row.

Release assembly is NOT done here (§24 explicit decision) — a song lives
as a post-QA draft until T-183 binds it to a release.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _voice_dna_summary(voice_dna: dict | None) -> str:
    """Flatten voice_dna JSON into a compact natural-language block."""
    if not voice_dna:
        return ""
    lines = []
    if (t := voice_dna.get("timbre_core")):
        lines.append(f"Timbre: {t}")
    if (r := voice_dna.get("range_estimate")):
        lines.append(f"Vocal range: {r}")
    ds = voice_dna.get("delivery_style")
    if isinstance(ds, list) and ds:
        lines.append(f"Delivery style: {', '.join(ds)}")
    elif isinstance(ds, str):
        lines.append(f"Delivery style: {ds}")
    if (a := voice_dna.get("accent_pronunciation")):
        lines.append(f"Accent: {a}")
    if (at := voice_dna.get("autotune_profile")):
        lines.append(f"Autotune: {at}")
    ad = voice_dna.get("adlib_profile")
    if isinstance(ad, list) and ad:
        lines.append(f"Adlibs: {', '.join(ad)}")
    if not lines:
        return ""
    return "[VOICE DNA]\n" + "\n".join(lines)


def _voice_state_reference_block(voice_state: dict | None, artist_song_count: int) -> str:
    """
    Return the §21 two-phase prompt fragment.

    Rule 1 (song_count == 0 or no state): empty string — the descriptive
    voice_dna_summary already carries all the info.
    Rule 2 (song_count >= 1 with reference URLs): text block listing the
    seed + best + latest reference URLs.
    """
    if artist_song_count == 0 or not voice_state:
        return ""
    parts = ["[VOICE REFERENCE]",
             "This artist has an established vocal identity. Match it tightly."]
    if (seed := voice_state.get("seed_song_audio_url")):
        parts.append(f"Seed reference: {seed}")
    if (best := voice_state.get("best_reference_audio_url")):
        parts.append(f"Best-performing reference: {best}")
    if (latest := voice_state.get("latest_reference_audio_url")):
        parts.append(f"Most-recent reference: {latest}")
    if (persona := voice_state.get("suno_persona_id")):
        parts.append(f"Provider persona id: {persona}")
    parts.append(
        "Consistency targets: timbre drift < 0.12, pitch contour > 0.75, "
        "delivery style matches. Fail rather than compromise voice identity."
    )
    if len(parts) == 2:
        # Nothing useful beyond the header — skip the block entirely.
        return ""
    return "\n".join(parts)


def assemble_generation_prompt(
    *,
    artist: dict,
    blueprint: dict,
    voice_state: dict | None,
) -> str:
    """
    Build the final text prompt the music provider receives.

    Contract (PRD §24):
      final_prompt =
          artist.voice_dna_summary +
          voice_state_reference_block +    # empty for first song
          song_blueprint.smart_prompt_text +
          production_constraints +
          policy_constraints
    """
    artist_song_count = int(artist.get("song_count") or 0)
    voice_summary = _voice_dna_summary(artist.get("voice_dna"))
    voice_ref = _voice_state_reference_block(voice_state, artist_song_count)
    smart_prompt = (blueprint.get("smart_prompt_text") or "").strip()

    production_constraints = [
        "[PRODUCTION]",
        "Loudness target: -14 LUFS (Spotify).",
        "Duration: within requested window.",
        "Stereo master.",
    ]

    policy_constraints = []
    content_rating = artist.get("content_rating", "mild")
    if content_rating == "clean":
        policy_constraints = ["[POLICY] No explicit language."]
    elif content_rating == "mild":
        policy_constraints = ["[POLICY] Mild language OK, no slurs."]
    # explicit → no constraint injected

    blocks = [voice_summary, voice_ref, smart_prompt,
              "\n".join(production_constraints),
              "\n".join(policy_constraints)]
    final = "\n\n".join(b for b in blocks if b)
    return final


def derive_song_title(blueprint: dict, artist: dict) -> str:
    """
    Pick a working title for a draft song. Not final — the user can
    rename before release assembly (§30).

    Strategy: pull a theme from the blueprint, combine with a stock
    noun. If no themes, fall back to "<Genre> Draft #<count+1>".
    """
    themes = blueprint.get("target_themes") or []
    if themes:
        first = str(themes[0]).strip().title()
        return f"{first} Study"
    genre = (blueprint.get("primary_genre") or blueprint.get("genre_id") or "Untitled").title()
    count = int(artist.get("song_count") or 0)
    return f"{genre} Draft #{count + 1}"
