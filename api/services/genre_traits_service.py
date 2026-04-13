"""
Genre traits resolver — dotted-genre aware fallback lookup.

A genre like 'pop.k-pop' should first try an exact row, then 'pop.k-pop'
→ 'pop', then finally a default system profile. Same pattern as the
genre taxonomy: most specific match wins, walk up if not found.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.genre_traits import GenreTraits

logger = logging.getLogger(__name__)


@dataclass
class ResolvedTraits:
    """Wraps a GenreTraits row as a plain dict-like object the rest of
    the pipeline can read. Using a dataclass means smart_prompt.py
    doesn't have to care whether the resolution fell back or hit
    exactly."""
    genre_id: str
    resolved_from: str  # the DB row's genre_id (may be a parent)
    edginess: int
    meme_density: int
    earworm_demand: int
    sonic_experimentation: int
    lyrical_complexity: int
    vocal_processing: int
    tempo_range_bpm: list[int]
    key_mood: str
    default_edge_profile: str
    vocabulary_era: str
    pop_culture_sources: list[str]
    instrumentation_palette: list[str]
    structural_conventions: str | None
    notes: str | None
    is_system_default: bool


# Hardcoded ultimate fallback if NOTHING matches — matches the migration
# defaults. Used only when the DB has zero rows (e.g. migration never ran).
_FALLBACK = ResolvedTraits(
    genre_id="__fallback__",
    resolved_from="__fallback__",
    edginess=50,
    meme_density=30,
    earworm_demand=70,
    sonic_experimentation=40,
    lyrical_complexity=50,
    vocal_processing=40,
    tempo_range_bpm=[80, 120],
    key_mood="mixed",
    default_edge_profile="flirty_edge",
    vocabulary_era="timeless",
    pop_culture_sources=[],
    instrumentation_palette=[],
    structural_conventions=None,
    notes=None,
    is_system_default=True,
)


def _candidate_genre_ids(genre_id: str) -> list[str]:
    """
    Build the fallback chain for a dotted genre string.

    'caribbean.reggae.dancehall' → [
        'caribbean.reggae.dancehall',
        'caribbean.reggae',
        'caribbean',
    ]
    'pop.k-pop' → ['pop.k-pop', 'pop']
    'rap' → ['rap']
    """
    if not genre_id:
        return []
    parts = genre_id.split(".")
    return [".".join(parts[: i + 1]) for i in range(len(parts) - 1, -1, -1)]


async def resolve_genre_traits(
    db: AsyncSession,
    genre_id: str,
) -> ResolvedTraits:
    """
    Return the genre_traits row that best matches the given genre id.
    Walks up the dotted chain until it finds a match. Returns the
    module-level fallback if nothing matches.
    """
    if not genre_id:
        return _FALLBACK

    candidates = _candidate_genre_ids(genre_id)
    for candidate in candidates:
        row = (
            await db.execute(
                select(GenreTraits).where(GenreTraits.genre_id == candidate)
            )
        ).scalar_one_or_none()
        if row is not None:
            return ResolvedTraits(
                genre_id=genre_id,
                resolved_from=candidate,
                edginess=row.edginess,
                meme_density=row.meme_density,
                earworm_demand=row.earworm_demand,
                sonic_experimentation=row.sonic_experimentation,
                lyrical_complexity=row.lyrical_complexity,
                vocal_processing=row.vocal_processing,
                tempo_range_bpm=list(row.tempo_range_bpm or []),
                key_mood=row.key_mood,
                default_edge_profile=row.default_edge_profile,
                vocabulary_era=row.vocabulary_era,
                pop_culture_sources=list(row.pop_culture_sources or []),
                instrumentation_palette=list(row.instrumentation_palette or []),
                structural_conventions=row.structural_conventions,
                notes=row.notes,
                is_system_default=row.is_system_default,
            )

    logger.info(
        "[genre-traits] no match for '%s' — using default fallback", genre_id
    )
    return _FALLBACK


def format_traits_for_smart_prompt(traits: ResolvedTraits) -> str:
    """Format a ResolvedTraits block as a directive for the smart_prompt
    LLM. Drops the numbers in context so the model can reason about them
    ('edginess 85 so go hard on named-target takes, meme_density 20 so
    skip TikTok slang')."""
    lines = [
        "GENRE TRAIT PROFILE (from genre_traits table, see §10 Layer 7 + §X genre dimensions):",
        f"  genre_id            = {traits.genre_id} (resolved from {traits.resolved_from})",
        f"  edginess            = {traits.edginess}/100 — how opinionated lyrics should be",
        f"  meme_density        = {traits.meme_density}/100 — how much TikTok/internet slang to inject",
        f"  earworm_demand      = {traits.earworm_demand}/100 — how strict the hook isolation rule is",
        f"  sonic_experimentation = {traits.sonic_experimentation}/100 — how far to push the sonic gap",
        f"  lyrical_complexity  = {traits.lyrical_complexity}/100 — simple pop hook vs dense rap",
        f"  vocal_processing    = {traits.vocal_processing}/100 — none (folk) → heavy (hyperpop)",
        f"  default_edge_profile= {traits.default_edge_profile}",
        f"  vocabulary_era      = {traits.vocabulary_era}",
        f"  tempo window        = {traits.tempo_range_bpm[0] if traits.tempo_range_bpm else '?'}-{traits.tempo_range_bpm[1] if len(traits.tempo_range_bpm) > 1 else '?'} BPM",
    ]
    if traits.pop_culture_sources:
        lines.append(
            f"  preferred pop-culture reference types: {', '.join(traits.pop_culture_sources)}"
        )
    if traits.instrumentation_palette:
        lines.append(
            f"  instrument palette: {', '.join(traits.instrumentation_palette)}"
        )
    if traits.structural_conventions:
        lines.append(f"  structural conventions: {traits.structural_conventions}")
    if traits.notes:
        lines.append(f"  genre notes: {traits.notes}")
    lines.append("")
    lines.append(
        "Respect these dimensions tightly. High meme_density + gen_z era "
        "= lean into Sabrina Carpenter / TikTok slang references. Low "
        "meme_density + outlaw_classic = use concrete storytelling "
        "imagery (truck, whiskey, specific places) but NEVER internet "
        "slang. Low earworm_demand = you can get away with a verse-"
        "heavy structure. High vocal_processing = autotune / chops / "
        "pitched harmonies are welcome."
    )
    return "\n".join(lines)
