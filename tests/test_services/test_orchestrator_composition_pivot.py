"""
Orchestrator composition pivot — task #17.

The blueprint no longer carries `smart_prompt_text`; the orchestrator
composes the prompt internally from blueprint structured fields + artist
DNA + per-song theme + per-song content_rating_override.

These tests pin the new contract:
  - [STYLE] block is composed from blueprint sonic / lyrical / audience
    fields. No smart_prompt_text is read.
  - [THEME] block is resolved from a picklist or free-text input.
  - artist_default theme derives from artist DNA.
  - genre_default theme derives from genre_traits.
  - content_rating_override wins over artist.content_rating.
"""
from __future__ import annotations

from api.services.generation_orchestrator import assemble_generation_prompt


def _bare_artist():
    return {
        "voice_dna": {"timbre_core": "warm tenor"},
        "song_count": 0,
        "content_rating": "mild",
    }


def _artist_with_dna():
    return {
        "voice_dna": {"timbre_core": "warm tenor"},
        "persona_dna": {
            "backstory": "Atlanta to Seoul at 17.",
            "personality_traits": ["confident", "flirty"],
            "recurring_motifs": ["midnight neon", "bilingual switch"],
        },
        "lyrical_dna": {
            "recurring_themes": ["midnight drives", "longing", "neon"],
            "vocab_level": "conversational",
            "language": "en",
            "perspective": "first person",
        },
        "song_count": 0,
        "content_rating": "mild",
    }


def _full_blueprint():
    return {
        "primary_genre": "pop.k-pop",
        "adjacent_genres": ["pop", "r&b"],
        "target_tempo": 118,
        "target_key": 7,            # G
        "target_mode": 1,           # major
        "target_energy": 0.78,
        "target_danceability": 0.72,
        "target_valence": 0.65,
        "target_themes": ["confidence", "flirty banter"],
        "avoid_themes": ["self-pity"],
        "vocabulary_tone": "conversational gen-z",
        "target_audience_tags": ["gen_z", "female_lean"],
        "voice_requirements": {"description": "soft tenor with autotune doubles"},
        "production_notes": "supersaw stabs, sidechained pads",
        "reference_track_descriptors": ["NewJeans 'Super Shy' chorus rush"],
    }


# ── Composition (#17) — STYLE block replaces smart_prompt_text ──────────

def test_style_block_composed_from_blueprint_fields():
    """STYLE block must surface every structured field the user set on
    the blueprint — no LLM-authored smart_prompt_text required."""
    prompt = assemble_generation_prompt(
        artist=_bare_artist(),
        blueprint=_full_blueprint(),
        voice_state=None,
    )
    assert "[STYLE]" in prompt
    assert "pop.k-pop" in prompt
    assert "tempo 118 BPM" in prompt
    assert "key G major" in prompt
    assert "energy 0.78" in prompt
    assert "Recipe themes: confidence, flirty banter" in prompt
    assert "Avoid themes: self-pity" in prompt
    assert "gen_z" in prompt
    assert "soft tenor with autotune doubles" in prompt
    assert "supersaw stabs" in prompt
    assert "Super Shy" in prompt


def test_no_smart_prompt_text_is_required():
    """Old contract required smart_prompt_text on the blueprint. New
    contract MUST NOT — passing a blueprint with no smart_prompt_text
    must produce a usable prompt."""
    bp = _full_blueprint()
    assert "smart_prompt_text" not in bp  # sanity
    prompt = assemble_generation_prompt(
        artist=_bare_artist(), blueprint=bp, voice_state=None,
    )
    # Prompt has structure / style / production / policy at minimum
    assert "[STYLE]" in prompt
    assert "[PRODUCTION]" in prompt


def test_legacy_smart_prompt_text_still_appended_when_provided():
    """Back-compat: callers that still have a stored smart_prompt_text
    can pass it as `legacy_smart_prompt_text` and it lands AFTER the
    composed style/theme blocks (free-form addendum)."""
    prompt = assemble_generation_prompt(
        artist=_bare_artist(),
        blueprint=_full_blueprint(),
        voice_state=None,
        legacy_smart_prompt_text="STYLE: extra prose the user wrote.",
    )
    style_idx = prompt.index("[STYLE]")
    legacy_idx = prompt.index("STYLE: extra prose")
    assert legacy_idx > style_idx, "legacy text must come AFTER composed STYLE"


# ── THEME block ──────────────────────────────────────────────────────────

def test_theme_artist_default_pulls_from_lyrical_dna():
    prompt = assemble_generation_prompt(
        artist=_artist_with_dna(),
        blueprint=_full_blueprint(),
        voice_state=None,
        theme="artist_default",
    )
    assert "[THEME]" in prompt
    assert "midnight drives" in prompt
    assert "longing" in prompt


def test_theme_artist_default_falls_back_to_persona_motifs_when_no_lyrical():
    artist = _artist_with_dna()
    artist["lyrical_dna"] = {}  # remove lyrical themes
    prompt = assemble_generation_prompt(
        artist=artist,
        blueprint=_full_blueprint(),
        voice_state=None,
        theme="artist_default",
    )
    assert "[THEME]" in prompt
    assert "midnight neon" in prompt
    assert "bilingual switch" in prompt


def test_theme_none_treated_as_artist_default():
    """Caller didn't pick a theme → orchestrator treats null like
    artist_default. Same semantics, no surprise empty prompt."""
    prompt_none = assemble_generation_prompt(
        artist=_artist_with_dna(),
        blueprint=_full_blueprint(),
        voice_state=None,
        theme=None,
    )
    prompt_default = assemble_generation_prompt(
        artist=_artist_with_dna(),
        blueprint=_full_blueprint(),
        voice_state=None,
        theme="artist_default",
    )
    # Both must contain the artist's recurring themes
    assert "midnight drives" in prompt_none
    assert "midnight drives" in prompt_default


def test_theme_genre_default_pulls_from_genre_traits():
    traits = {
        "notes": "K-pop rewards code-switching and concept-teaser lyricism.",
        "structural_conventions": "VPCV-PC-B-C; 3:00–3:30; English hook + Hangul verses standard.",
        "vocabulary_era": "gen_z",
    }
    prompt = assemble_generation_prompt(
        artist=_bare_artist(),
        blueprint=_full_blueprint(),
        voice_state=None,
        theme="genre_default",
        genre_traits=traits,
    )
    assert "[THEME]" in prompt
    assert "code-switching" in prompt
    assert "VPCV-PC-B-C" in prompt


def test_theme_fixed_picklist_emits_canonical_fragment():
    """The fixed picklist (love/sex/family/etc.) maps to canonical
    prompt fragments — predictable, no LLM needed, no creative drift."""
    prompt = assemble_generation_prompt(
        artist=_bare_artist(),
        blueprint=_full_blueprint(),
        voice_state=None,
        theme="love_relationships",
    )
    assert "[THEME]" in prompt
    assert "love relationship" in prompt.lower()


def test_theme_free_text_passed_through_verbatim():
    """Anything not in the picklist is treated as free text the user
    typed in the song window — passed through as the THEME body."""
    custom = "Lyrics about drifting sideways through Atlanta at 4 a.m."
    prompt = assemble_generation_prompt(
        artist=_bare_artist(),
        blueprint=_full_blueprint(),
        voice_state=None,
        theme=custom,
    )
    assert "[THEME]" in prompt
    assert "drifting sideways through Atlanta at 4 a.m." in prompt


# ── Per-song content_rating_override ─────────────────────────────────────

def test_content_rating_override_wins_over_artist_default():
    artist = _bare_artist()
    artist["content_rating"] = "clean"
    prompt = assemble_generation_prompt(
        artist=artist,
        blueprint=_full_blueprint(),
        voice_state=None,
        content_rating_override="explicit",
    )
    # Explicit policy fragment, NOT clean
    assert "Explicit language permitted" in prompt
    assert "No explicit language" not in prompt


def test_no_override_uses_artist_default_rating():
    artist = _bare_artist()
    artist["content_rating"] = "clean"
    prompt = assemble_generation_prompt(
        artist=artist,
        blueprint=_full_blueprint(),
        voice_state=None,
    )
    assert "No explicit language" in prompt


# ── Block ordering — STYLE before THEME, both before legacy/PRODUCTION ──

def test_block_order_style_then_theme_then_production():
    prompt = assemble_generation_prompt(
        artist=_artist_with_dna(),
        blueprint=_full_blueprint(),
        voice_state=None,
        theme="love_relationships",
    )
    style_idx = prompt.index("[STYLE]")
    theme_idx = prompt.index("[THEME]")
    prod_idx = prompt.index("[PRODUCTION]")
    assert style_idx < theme_idx < prod_idx
