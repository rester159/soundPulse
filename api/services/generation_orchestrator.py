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


def _persona_dna_summary(persona_dna: dict | None) -> str:
    """Flatten the artist's persona_dna into a `[PERSONA]` block.

    Persona is who the artist IS — backstory, personality traits,
    posting style, controversy stance, recurring motifs that shape the
    voice in the song. Always injected if present (independent of the
    blueprint), so a single persona stays consistent across genres /
    blueprints / songs."""
    if not persona_dna or not isinstance(persona_dna, dict):
        return ""
    lines: list[str] = []
    if (b := persona_dna.get("backstory")):
        lines.append(f"Backstory: {b}")
    pt = persona_dna.get("personality_traits")
    if isinstance(pt, list) and pt:
        lines.append(f"Personality traits: {', '.join(str(x) for x in pt)}")
    elif isinstance(pt, str) and pt.strip():
        lines.append(f"Personality traits: {pt.strip()}")
    if (ps := persona_dna.get("posting_style")):
        lines.append(f"Posting / social tone: {ps}")
    if (cs := persona_dna.get("controversy_stance")):
        lines.append(f"Controversy stance: {cs}")
    motifs = persona_dna.get("recurring_motifs")
    if isinstance(motifs, list) and motifs:
        lines.append(f"Recurring motifs: {', '.join(str(x) for x in motifs)}")
    elif isinstance(motifs, str) and motifs.strip():
        lines.append(f"Recurring motifs: {motifs.strip()}")
    # Catch-all: surface any remaining string-valued keys that weren't
    # explicitly handled above so a future schema addition shows up
    # automatically without code changes.
    handled = {"backstory", "personality_traits", "posting_style",
               "controversy_stance", "recurring_motifs"}
    for k, v in persona_dna.items():
        if k in handled:
            continue
        if isinstance(v, str) and v.strip():
            lines.append(f"{k.replace('_', ' ').capitalize()}: {v.strip()}")
        elif isinstance(v, list) and v and all(isinstance(x, str) for x in v):
            lines.append(f"{k.replace('_', ' ').capitalize()}: {', '.join(v)}")
    if not lines:
        return ""
    return "[PERSONA]\n" + "\n".join(lines)


def _lyrical_dna_summary(lyrical_dna: dict | None) -> str:
    """Flatten the artist's lyrical_dna into a `[LYRICAL DNA]` block.

    Lyrical DNA is the artist's recurring lyrical voice — themes they
    return to, vocabulary tier, perspective, language(s). Injected
    unconditionally so the lyrics in the generated song stay in the
    artist's voice even when the blueprint pushes a new theme."""
    if not lyrical_dna or not isinstance(lyrical_dna, dict):
        return ""
    lines: list[str] = []
    rt = lyrical_dna.get("recurring_themes")
    if isinstance(rt, list) and rt:
        lines.append(f"Recurring themes: {', '.join(str(x) for x in rt)}")
    elif isinstance(rt, str) and rt.strip():
        lines.append(f"Recurring themes: {rt.strip()}")
    if (vl := lyrical_dna.get("vocab_level") or lyrical_dna.get("vocabulary_level")):
        lines.append(f"Vocabulary tier: {vl}")
    if (lang := lyrical_dna.get("language") or lyrical_dna.get("languages")):
        if isinstance(lang, list):
            lines.append(f"Language(s): {', '.join(str(x) for x in lang)}")
        else:
            lines.append(f"Language: {lang}")
    if (persp := lyrical_dna.get("perspective")):
        lines.append(f"Perspective: {persp}")
    motifs = lyrical_dna.get("recurring_motifs")
    if isinstance(motifs, list) and motifs:
        lines.append(f"Recurring motifs: {', '.join(str(x) for x in motifs)}")
    elif isinstance(motifs, str) and motifs.strip():
        lines.append(f"Recurring motifs: {motifs.strip()}")
    avoid = lyrical_dna.get("avoid_themes") or lyrical_dna.get("anti_themes")
    if isinstance(avoid, list) and avoid:
        lines.append(f"Avoid themes: {', '.join(str(x) for x in avoid)}")
    handled = {"recurring_themes", "vocab_level", "vocabulary_level",
               "language", "languages", "perspective", "recurring_motifs",
               "avoid_themes", "anti_themes"}
    for k, v in lyrical_dna.items():
        if k in handled:
            continue
        if isinstance(v, str) and v.strip():
            lines.append(f"{k.replace('_', ' ').capitalize()}: {v.strip()}")
        elif isinstance(v, list) and v and all(isinstance(x, str) for x in v):
            lines.append(f"{k.replace('_', ' ').capitalize()}: {', '.join(v)}")
    if not lines:
        return ""
    return "[LYRICAL DNA]\n" + "\n".join(lines)


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
    structure_block: str | None = None,
) -> str:
    """
    Build the final text prompt the music provider receives.

    Contract (PRD §24 + task #109):
      final_prompt =
          structure_block +                 # task #109: prepended; empty if unset
          artist.voice_dna_summary +
          voice_state_reference_block +    # empty for first song
          artist.persona_dna_summary +     # ALWAYS injected if present — keeps
                                            #   the artist's identity stable across
                                            #   blueprints / genres / sessions
          artist.lyrical_dna_summary +     # ALWAYS injected if present — locks the
                                            #   lyrical voice independent of the
                                            #   blueprint's per-song themes
          song_blueprint.smart_prompt_text +
          production_constraints +
          policy_constraints

    `structure_block` is the formatted [STRUCTURE]\\n[Section: N bars{,
    instrumental}] block produced by `api.services.structure_prompt.
    structure_block_for_prompt()`. It comes FIRST so Suno reads the
    structural directive before the smart_prompt narrative — getting the
    bar counts right is the load-bearing change for this feature.

    Persona + lyrical DNA are injected UNCONDITIONALLY (regardless of
    blueprint contents) so a single artist stays recognizable across
    songs. Per-song themes from the blueprint layer ON TOP of these
    artist-level constants — not in place of them.
    """
    artist_song_count = int(artist.get("song_count") or 0)
    voice_summary = _voice_dna_summary(artist.get("voice_dna"))
    voice_ref = _voice_state_reference_block(voice_state, artist_song_count)
    persona_summary = _persona_dna_summary(artist.get("persona_dna"))
    lyrical_summary = _lyrical_dna_summary(artist.get("lyrical_dna"))
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

    blocks = [
        (structure_block or "").strip(),
        voice_summary,
        voice_ref,
        persona_summary,
        lyrical_summary,
        smart_prompt,
        "\n".join(production_constraints),
        "\n".join(policy_constraints),
    ]
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
