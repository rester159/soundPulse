"""
Orchestrator structure injection — task #109 Phase 2.

Asserts that `assemble_generation_prompt()` prepends the [STRUCTURE]
block when one is provided and degrades gracefully when it isn't (so
old call sites that haven't been updated still work).
"""
from __future__ import annotations

from api.services.generation_orchestrator import assemble_generation_prompt
from api.services.structure_prompt import structure_block_for_prompt


def _artist():
    return {
        "voice_dna": {"timbre_core": "bright tenor"},
        "song_count": 0,
        "content_rating": "mild",
    }


def _blueprint():
    return {
        # smart_prompt_text is no longer read by the orchestrator (#17
        # composition pivot), but we keep it on this fixture and pass it
        # via the back-compat shim where these tests assert on it.
        "smart_prompt_text": "Write a confident pop song about overcoming doubt.",
        "primary_genre": "pop",
    }


def test_no_structure_block_param_yields_pre_109_prompt():
    """Backwards compat: omitting the new structure_block kwarg leaves
    the prompt structurally identical to pre-#109 output (modulo
    formatting). Smart prompt text passes through the legacy shim."""
    bp = _blueprint()
    prompt = assemble_generation_prompt(
        artist=_artist(),
        blueprint=bp,
        voice_state=None,
        legacy_smart_prompt_text=bp["smart_prompt_text"],
    )
    assert "[STRUCTURE]" not in prompt
    assert "Write a confident pop song" in prompt


def test_structure_block_is_prepended_first():
    """When provided, [STRUCTURE] sits at the very top of the prompt
    so Suno reads the structural directive before the narrative."""
    sb = structure_block_for_prompt([
        {"name": "Intro", "bars": 8, "vocals": False},
        {"name": "Verse", "bars": 16, "vocals": True},
        {"name": "Chorus", "bars": 8, "vocals": True},
    ])
    bp = _blueprint()
    prompt = assemble_generation_prompt(
        artist=_artist(),
        blueprint=bp,
        voice_state=None,
        structure_block=sb,
        legacy_smart_prompt_text=bp["smart_prompt_text"],
    )
    assert prompt.startswith("[STRUCTURE]")
    # Each section line is present
    assert "[Intro: 8 bars, instrumental]" in prompt
    assert "[Verse: 16 bars]" in prompt
    assert "[Chorus: 8 bars]" in prompt
    # Smart prompt still appears AFTER structure
    intro_idx = prompt.index("[Intro:")
    smart_idx = prompt.index("Write a confident")
    assert intro_idx < smart_idx, "structure must come before smart_prompt narrative"


def test_empty_structure_block_does_not_inject_header():
    """If resolver returns nothing, no malformed [STRUCTURE] header
    is emitted — important for the orchestrator's try/except path that
    swallows resolution errors."""
    prompt = assemble_generation_prompt(
        artist=_artist(),
        blueprint=_blueprint(),
        voice_state=None,
        structure_block="",
    )
    assert "[STRUCTURE]" not in prompt


# ── Persona + Lyrical DNA injection ───────────────────────────────────────
# User requirement: artist's persona + lyrical DNA must be in EVERY
# song-generation prompt regardless of blueprint, so the artist stays
# recognizable across blueprints / sessions.

def _artist_with_dna():
    return {
        "voice_dna": {"timbre_core": "warm tenor"},
        "persona_dna": {
            "backstory": "Raised in Atlanta, moved to Seoul at 17.",
            "personality_traits": ["confident", "flirty", "internet-native"],
            "posting_style": "casual photo dumps with one-line captions",
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


def test_persona_dna_block_injected_when_present():
    prompt = assemble_generation_prompt(
        artist=_artist_with_dna(), blueprint=_blueprint(), voice_state=None,
    )
    assert "[PERSONA]" in prompt
    assert "Backstory: Raised in Atlanta" in prompt
    assert "Personality traits: confident, flirty, internet-native" in prompt
    assert "Posting / social tone: casual photo dumps" in prompt


def test_lyrical_dna_block_injected_when_present():
    prompt = assemble_generation_prompt(
        artist=_artist_with_dna(), blueprint=_blueprint(), voice_state=None,
    )
    assert "[LYRICAL DNA]" in prompt
    assert "Recurring themes: midnight drives, longing, neon" in prompt
    assert "Vocabulary tier: conversational" in prompt
    assert "Language: en" in prompt
    assert "Perspective: first person" in prompt


def test_persona_and_lyrical_blocks_skipped_when_absent():
    """A bare artist (no persona/lyrical DNA fields) must not produce
    empty [PERSONA] / [LYRICAL DNA] headers."""
    prompt = assemble_generation_prompt(
        artist=_artist(), blueprint=_blueprint(), voice_state=None,
    )
    assert "[PERSONA]" not in prompt
    assert "[LYRICAL DNA]" not in prompt


def test_persona_dna_injection_independent_of_blueprint():
    """The user's hard requirement: persona DNA appears in the prompt
    EVEN IF the blueprint mentions nothing about the artist's brand.
    The blueprint can change song-to-song; persona is a constant."""
    bp_text = "STYLE: punk thrash. LYRICS: scream about politics."
    prompt = assemble_generation_prompt(
        artist=_artist_with_dna(),
        blueprint={},
        voice_state=None,
        legacy_smart_prompt_text=bp_text,
    )
    assert "[PERSONA]" in prompt
    assert "[LYRICAL DNA]" in prompt
    # Free-form blueprint text still appears too — DNA layers ON TOP
    # of, not in place of, the blueprint.
    assert "punk thrash" in prompt


def test_persona_block_passes_through_unknown_keys():
    """Unrecognized string-valued keys on persona_dna get surfaced in
    the [PERSONA] block automatically — no code change needed when the
    schema picks up new fields."""
    artist = _artist()
    artist["persona_dna"] = {
        "backstory": "—",
        "favorite_food": "Korean BBQ",  # not in the explicit handler
        "spirit_animal": "snow leopard",
    }
    prompt = assemble_generation_prompt(
        artist=artist, blueprint=_blueprint(), voice_state=None,
    )
    assert "Favorite food: Korean BBQ" in prompt
    assert "Spirit animal: snow leopard" in prompt
