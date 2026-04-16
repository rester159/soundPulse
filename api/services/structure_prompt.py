"""
Format a resolved structure into the [Section: N bars{, instrumental}]
Suno tag block that prepends the song generation prompt (task #109,
PRD §70).

The Suno convention (per the §24 prompt contract + Kie.ai docs) is one
bracketed directive per line. `instrumental` after the bar count tells
Suno not to write or place vocals for that section.
"""
from __future__ import annotations


_HEADER = "[STRUCTURE]"


def format_structure_for_suno(structure: list[dict]) -> str:
    """Render the bracketed section list. Raises on empty input — callers
    that might receive an empty structure should use `structure_block_for_prompt`
    instead, which returns "" gracefully."""
    if not structure:
        raise ValueError("cannot format empty structure")
    lines = []
    for sec in structure:
        name = sec["name"]
        bars = int(sec["bars"])
        if sec.get("vocals", True):
            lines.append(f"[{name}: {bars} bars]")
        else:
            lines.append(f"[{name}: {bars} bars, instrumental]")
    return "\n".join(lines)


def structure_block_for_prompt(structure: list[dict] | None) -> str:
    """Wrap the formatted block with a `[STRUCTURE]` header. Returns ""
    when structure is None or empty so the orchestrator can unconditionally
    prepend without checking — empty string joins cleanly with the rest
    of the prompt blocks."""
    if not structure:
        return ""
    return f"{_HEADER}\n{format_structure_for_suno(structure)}"
