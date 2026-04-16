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
        "smart_prompt_text": "Write a confident pop song about overcoming doubt.",
        "primary_genre": "pop",
    }


def test_no_structure_block_param_yields_pre_109_prompt():
    """Backwards compat: omitting the new kwarg leaves the prompt
    structurally identical to pre-#109 output (modulo formatting)."""
    prompt = assemble_generation_prompt(
        artist=_artist(), blueprint=_blueprint(), voice_state=None,
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
    prompt = assemble_generation_prompt(
        artist=_artist(),
        blueprint=_blueprint(),
        voice_state=None,
        structure_block=sb,
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
