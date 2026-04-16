"""
Structure prompt formatter tests (task #109 Phase 2, PRD §70).

Turns a [{name, bars, vocals}] list into a Suno tag block:
    [Intro: 8 bars, instrumental]
    [Verse 1: 16 bars]
    [Pre-chorus: 4 bars]
    ...
"""
from __future__ import annotations

import pytest

from api.services.structure_prompt import (
    format_structure_for_suno,
    structure_block_for_prompt,
)


def test_format_single_vocal_section():
    structure = [{"name": "Verse", "bars": 16, "vocals": True}]
    assert format_structure_for_suno(structure) == "[Verse: 16 bars]"


def test_format_single_instrumental_section_appends_instrumental_tag():
    structure = [{"name": "Intro", "bars": 8, "vocals": False}]
    assert format_structure_for_suno(structure) == "[Intro: 8 bars, instrumental]"


def test_format_multi_section_joined_with_newlines():
    structure = [
        {"name": "Intro", "bars": 8, "vocals": False},
        {"name": "Verse 1", "bars": 16, "vocals": True},
        {"name": "Chorus", "bars": 8, "vocals": True},
        {"name": "Outro", "bars": 4, "vocals": False},
    ]
    expected = (
        "[Intro: 8 bars, instrumental]\n"
        "[Verse 1: 16 bars]\n"
        "[Chorus: 8 bars]\n"
        "[Outro: 4 bars, instrumental]"
    )
    assert format_structure_for_suno(structure) == expected


def test_format_empty_structure_raises():
    """An empty structure should never reach the formatter — caller's
    job to validate. Defensive raise keeps the bug visible."""
    with pytest.raises(ValueError, match="empty"):
        format_structure_for_suno([])


def test_structure_block_for_prompt_wraps_in_header():
    """The full prompt block has a STRUCTURE header so Suno knows what
    follows is a structural directive, not freeform lyrics."""
    structure = [
        {"name": "Intro", "bars": 8, "vocals": False},
        {"name": "Verse", "bars": 16, "vocals": True},
    ]
    block = structure_block_for_prompt(structure)
    assert block.startswith("[STRUCTURE]")
    assert "[Intro: 8 bars, instrumental]" in block
    assert "[Verse: 16 bars]" in block


def test_structure_block_for_prompt_returns_empty_string_for_none():
    """If no structure is resolved (e.g. genre table unseeded for an
    edge case), the block must be empty so the orchestrator's prompt
    assembly degrades gracefully — we never want to inject a malformed
    [STRUCTURE] header with no body."""
    assert structure_block_for_prompt(None) == ""
    assert structure_block_for_prompt([]) == ""
