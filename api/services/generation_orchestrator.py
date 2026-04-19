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


# ── Per-song theme resolver (#17 composition pivot) ──────────────────────
# Per-song theme picked in the song generation window. Resolved here, not
# stored as prompt text on the blueprint. Free-form strings pass through
# verbatim. The two `*_default` sentinels look at artist DNA / genre
# traits respectively so a single song can ride either rail without the
# operator typing anything.

_FIXED_THEME_FRAGMENTS: dict[str, str] = {
    "love_relationships": (
        "Lyrics center on a love relationship — attraction, tension, "
        "intimacy, distance, reconciliation, or the small textures of "
        "being with one specific person. Concrete imagery, not abstract."
    ),
    "sex": (
        "Lyrics are openly sensual / sexual — desire, anticipation, "
        "physicality. Adult and direct without being clinical or "
        "gratuitous. Match the artist's edge profile."
    ),
    "introspection": (
        "Lyrics are introspective — internal monologue, self-doubt, "
        "self-discovery, processing an experience. First-person, "
        "specific, restrained imagery."
    ),
    "family": (
        "Lyrics are about family — parent, sibling, child, chosen "
        "family. Specific moments, not generic gratitude. Tone can be "
        "warm, complicated, or grieving depending on the artist."
    ),
    "god": (
        "Lyrics engage spiritually — faith, doubt, prayer, the divine, "
        "the soul. Frame consistent with the artist's persona "
        "(devotional, searching, skeptical, etc.) — never preachy."
    ),
    "partying": (
        "Lyrics are about going out, celebrating, getting loose. "
        "Friends, the night, the room, the rush. Energetic and "
        "specific over generic 'turn up' platitudes."
    ),
}


def _theme_from_artist_default(artist: dict) -> str:
    """Derive a theme directive from the artist's lyrical + persona DNA.

    Reads `lyrical_dna.recurring_themes` first (the artist's house
    themes), falling back to `persona_dna.recurring_motifs`. Returns
    empty string if neither is present so the orchestrator skips the
    block cleanly."""
    ldna = artist.get("lyrical_dna") or {}
    pdna = artist.get("persona_dna") or {}
    themes = ldna.get("recurring_themes")
    if isinstance(themes, list) and themes:
        joined = ", ".join(str(t) for t in themes)
        return f"Lyrics ride the artist's recurring themes: {joined}."
    motifs = pdna.get("recurring_motifs")
    if isinstance(motifs, list) and motifs:
        joined = ", ".join(str(m) for m in motifs)
        return f"Lyrics ride the artist's recurring motifs: {joined}."
    return ""


def _theme_from_genre_default(genre_traits: dict | None) -> str:
    """Derive a theme directive from the genre's traits row.

    Pulls `notes` (CEO-authored prose about how the genre handles
    lyrics) and `structural_conventions` (form / length / hook
    guidance). Falls back to the vocabulary era as a last hint."""
    if not genre_traits:
        return ""
    parts: list[str] = []
    if (notes := genre_traits.get("notes")):
        parts.append(str(notes).strip())
    if (struct := genre_traits.get("structural_conventions")):
        parts.append(f"Structural conventions: {struct}")
    if not parts:
        if (era := genre_traits.get("vocabulary_era")):
            parts.append(f"Lyrical vocabulary era: {era}")
    if not parts:
        return ""
    return "Lyrics ride the genre's conventions. " + " ".join(parts)


def _theme_block(
    theme: str | None,
    artist: dict,
    genre_traits: dict | None,
) -> str:
    """
    Resolve a per-song `theme` selection into a `[THEME]` prompt block.

    Picklist values: 'artist_default' | 'genre_default' |
    'love_relationships' | 'sex' | 'introspection' | 'family' | 'god' |
    'partying'. Anything else is treated as free-text and passed
    through verbatim (so the user can type a custom theme in the song
    window and have it injected as-is). `None` is treated as
    artist_default.
    """
    if theme is None or theme == "" or theme == "artist_default":
        body = _theme_from_artist_default(artist)
    elif theme == "genre_default":
        body = _theme_from_genre_default(genre_traits)
    elif theme in _FIXED_THEME_FRAGMENTS:
        body = _FIXED_THEME_FRAGMENTS[theme]
    else:
        # Free-text: pass through verbatim.
        body = str(theme).strip()
    if not body:
        return ""
    return f"[THEME]\n{body}"


# ── Blueprint sonic / lyrical / audience composer (#17) ──────────────────
# Replaces the old `smart_prompt_text` author flow. We compose a `[STYLE]`
# block from the blueprint's structured fields (genre, sonic targets,
# audience, themes, production notes, references) so the operator can
# adjust any field in the Blueprint UI and have it reflected in the
# generated song without re-running an LLM author pass.

_KEY_NAMES = ["C", "C♯/D♭", "D", "D♯/E♭", "E", "F", "F♯/G♭", "G", "G♯/A♭", "A", "A♯/B♭", "B"]
_MODE_NAMES = {0: "minor", 1: "major"}


def _style_block_from_blueprint(blueprint: dict) -> str:
    """Compose a `[STYLE]` block from the blueprint's structured fields.

    The blueprint is a pure recipe — sonic targets, lyrical guardrails,
    audience, production references. We render it as a deterministic
    prose block so what the user sees in the Blueprint UI is what the
    music provider receives."""
    if not blueprint:
        return ""
    lines: list[str] = []

    # Genre identity
    primary = blueprint.get("primary_genre") or blueprint.get("genre_id")
    if primary:
        adj = blueprint.get("adjacent_genres") or []
        if isinstance(adj, list) and adj:
            lines.append(f"Genre: {primary} (with influence from {', '.join(adj)})")
        else:
            lines.append(f"Genre: {primary}")

    # Sonic targets
    sonic_bits: list[str] = []
    if (t := blueprint.get("target_tempo")) is not None:
        sonic_bits.append(f"tempo {round(float(t))} BPM")
    if (k := blueprint.get("target_key")) is not None:
        try:
            ki = int(k) % 12
            mode = blueprint.get("target_mode")
            mode_str = _MODE_NAMES.get(int(mode), "") if mode is not None else ""
            sonic_bits.append(f"key {_KEY_NAMES[ki]}{(' ' + mode_str) if mode_str else ''}")
        except Exception:
            pass
    for k_name, label in (
        ("target_energy", "energy"),
        ("target_danceability", "danceability"),
        ("target_valence", "valence"),
        ("target_acousticness", "acousticness"),
    ):
        if (v := blueprint.get(k_name)) is not None:
            try:
                sonic_bits.append(f"{label} {float(v):.2f}")
            except Exception:
                pass
    if sonic_bits:
        lines.append("Sonic target: " + ", ".join(sonic_bits) + ".")

    # Lyrical guardrails (themes from the blueprint LAYER on top of the
    # per-song theme — they're not the same thing. Blueprint themes are
    # the recipe defaults; the per-song [THEME] block overrides scope.)
    if (themes := blueprint.get("target_themes")):
        if isinstance(themes, list) and themes:
            lines.append(f"Recipe themes: {', '.join(str(t) for t in themes)}.")
    if (avoid := blueprint.get("avoid_themes")):
        if isinstance(avoid, list) and avoid:
            lines.append(f"Avoid themes: {', '.join(str(t) for t in avoid)}.")
    if (tone := blueprint.get("vocabulary_tone")):
        lines.append(f"Vocabulary tone: {tone}.")

    # Audience + voice requirements
    if (aud := blueprint.get("target_audience_tags")):
        if isinstance(aud, list) and aud:
            lines.append(f"Target audience: {', '.join(str(a) for a in aud)}.")
    vr = blueprint.get("voice_requirements")
    if isinstance(vr, dict):
        desc = vr.get("description") or vr.get("notes")
        if desc:
            lines.append(f"Voice requirements: {desc}.")
        else:
            for k, v in vr.items():
                if isinstance(v, str) and v.strip():
                    lines.append(f"Voice {k}: {v.strip()}.")
    elif isinstance(vr, str) and vr.strip():
        lines.append(f"Voice requirements: {vr.strip()}.")

    # Production
    if (notes := blueprint.get("production_notes")):
        lines.append(f"Production notes: {notes}.")
    if (refs := blueprint.get("reference_track_descriptors")):
        if isinstance(refs, list) and refs:
            lines.append(f"Reference feel: {'; '.join(str(r) for r in refs)}.")

    if not lines:
        return ""
    return "[STYLE]\n" + "\n".join(lines)


def assemble_generation_prompt(
    *,
    artist: dict,
    blueprint: dict,
    voice_state: dict | None,
    structure_block: str | None = None,
    theme: str | None = None,
    content_rating_override: str | None = None,
    genre_traits: dict | None = None,
    # Back-compat shim: callers from before #17 may still pass a literal
    # smart_prompt_text. We accept it but no longer privilege it — it
    # lands AFTER the composed [STYLE] block as a free-form addendum.
    legacy_smart_prompt_text: str | None = None,
) -> str:
    """
    Build the final text prompt the music provider receives (#17).

    Composition order:
      structure_block             # [STRUCTURE] from genre_structures (#109)
      voice_dna_summary           # [VOICE DNA] from artist
      voice_reference_block       # [VOICE REFERENCE] from prior songs
      persona_dna_summary         # [PERSONA] always injected if present
      lyrical_dna_summary         # [LYRICAL DNA] always injected if present
      style_block_from_blueprint  # [STYLE] composed from blueprint fields
      theme_block                 # [THEME] from per-song picker
      legacy_smart_prompt_text    # back-compat free-form addendum
      production_constraints
      policy_constraints

    No smart_prompt_text is read from the blueprint. The blueprint is a
    pure recipe (genre + sonic + lyrical guardrails + audience), and the
    per-song theme + content rating override are layered ON TOP of it
    here. This is the #17 composition pivot.

    `content_rating_override` (clean | explicit) wins over
    `artist.content_rating` if supplied. Use this to wire up the per-song
    clean/explicit toggle in the song window.
    """
    artist_song_count = int(artist.get("song_count") or 0)
    voice_summary = _voice_dna_summary(artist.get("voice_dna"))
    voice_ref = _voice_state_reference_block(voice_state, artist_song_count)
    persona_summary = _persona_dna_summary(artist.get("persona_dna"))
    lyrical_summary = _lyrical_dna_summary(artist.get("lyrical_dna"))
    style_block = _style_block_from_blueprint(blueprint or {})
    theme_block = _theme_block(theme, artist or {}, genre_traits)
    legacy_addendum = (legacy_smart_prompt_text or "").strip()

    production_constraints = [
        "[PRODUCTION]",
        "Loudness target: -14 LUFS (Spotify).",
        "Duration: within requested window.",
        "Stereo master.",
    ]

    # Per-song override > artist default. Mild is the artist default
    # when nothing is set.
    effective_rating = (
        (content_rating_override or "").strip().lower()
        or artist.get("content_rating", "mild")
    )
    policy_constraints: list[str] = []
    if effective_rating == "clean":
        policy_constraints = ["[POLICY] No explicit language."]
    elif effective_rating == "mild":
        policy_constraints = ["[POLICY] Mild language OK, no slurs."]
    elif effective_rating == "explicit":
        policy_constraints = ["[POLICY] Explicit language permitted; avoid slurs targeting protected groups."]

    blocks = [
        (structure_block or "").strip(),
        voice_summary,
        voice_ref,
        persona_summary,
        lyrical_summary,
        style_block,
        theme_block,
        legacy_addendum,
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
