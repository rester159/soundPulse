"""
Reference artist lookup — pulls real current-momentum artists from the
existing Chartmetric-scraped `artists` table for a target genre.

Used by the persona_blender to ground new AI artist creation in real
reference data (vs LLM confabulation from pre-training).

This is a minimum-viable slice of PRD §19 T-120. Full reference-artist
research (voice DSP, visual scraping via BlackTip, social voice) lands
later in T-122..T-125.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text as _text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class ReferenceArtist:
    name: str
    chartmetric_id: int | None
    spotify_id: str | None
    genres: list[str]
    recent_trending_count: int
    popularity: int | None


async def get_top_reference_artists(
    db: AsyncSession,
    *,
    target_genre: str,
    limit: int = 5,
) -> list[ReferenceArtist]:
    """
    Return the top N current-momentum artists for a target genre.

    Strategy:
      1. Find all artists whose `genres` array contains target_genre
         OR any prefix-match (e.g. 'caribbean.reggae' matches
         'caribbean.reggae.dancehall')
      2. LEFT JOIN trending_snapshots from the last 30 days to rank by
         "currently hot" — more recent trending appearances = higher rank
      3. Tiebreak on chartmetric_id DESC (newer artists indexed later,
         often newer signings)
      4. Return the top N as dataclasses

    Falls back to any artist matching the top-level token if no exact
    matches exist (e.g. 'caribbean.reggae.roots-reggae' falls back to
    'caribbean.reggae').
    """
    # Try exact + prefix match first. Pre-aggregate trending snapshots in
    # a subquery so we don't have to GROUP BY on the outer artists row
    # (Postgres can't group on json columns — no equality operator).
    result = await db.execute(
        _text("""
            SELECT
                a.id,
                a.name,
                a.chartmetric_id,
                a.spotify_id,
                a.genres,
                COALESCE((a.metadata_json->>'popularity')::int, 0) AS popularity,
                COALESCE(t.recent_trending_count, 0) AS recent_trending_count
            FROM artists a
            LEFT JOIN (
                SELECT entity_id, COUNT(*) AS recent_trending_count
                FROM trending_snapshots
                WHERE entity_type = 'artist'
                  AND snapshot_date >= NOW() - INTERVAL '30 days'
                GROUP BY entity_id
            ) t ON t.entity_id = a.id
            WHERE :target_genre = ANY(a.genres)
               OR EXISTS (
                   SELECT 1 FROM unnest(a.genres) g
                   WHERE g LIKE :prefix OR g = :target_genre
               )
            ORDER BY recent_trending_count DESC NULLS LAST,
                     popularity DESC NULLS LAST,
                     a.chartmetric_id DESC NULLS LAST
            LIMIT :limit
        """),
        {
            "target_genre": target_genre,
            "prefix": f"{target_genre}.%",  # child subgenres
            "limit": limit,
        },
    )
    rows = result.fetchall()

    # Fallback: if nothing found, try the top-level token
    # (e.g. 'caribbean.reggae.dancehall' -> 'caribbean.reggae' -> 'caribbean')
    if not rows and "." in target_genre:
        parent_genre = target_genre.rsplit(".", 1)[0]
        logger.info(
            "[reference-lookup] no matches for %s, falling back to %s",
            target_genre, parent_genre,
        )
        return await get_top_reference_artists(
            db, target_genre=parent_genre, limit=limit,
        )

    return [
        ReferenceArtist(
            name=row[1],
            chartmetric_id=row[2],
            spotify_id=row[3],
            genres=row[4] or [],
            recent_trending_count=row[6] or 0,
            popularity=row[5] or None,
        )
        for row in rows
    ]


def format_references_for_prompt(refs: list[ReferenceArtist]) -> str:
    """Format a reference-artist list as a compact system-prompt block."""
    if not refs:
        return ""
    lines = [
        "REFERENCE ARTISTS — currently top-ranked artists in this genre "
        "based on our internal trending data. Use them as inspiration "
        "for sonic, lyrical, and visual direction, but DO NOT copy any "
        "of them directly — SoundPulse requires differentiation.",
        "",
    ]
    for i, ref in enumerate(refs, 1):
        genre_str = ", ".join(ref.genres[:3]) if ref.genres else "unknown"
        momentum = f"recent trending ×{ref.recent_trending_count}" if ref.recent_trending_count else "catalog"
        lines.append(
            f"  {i}. {ref.name} — {genre_str} ({momentum})"
        )
    return "\n".join(lines)
