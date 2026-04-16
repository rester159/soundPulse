"""
Genre structures service — validation, upsert, and dotted-genre fallback
resolver for task #109 (PRD §70).

Mirrors the resolution pattern in api/services/genre_traits_service.py:
walk the dotted chain from most specific to least specific, then fall back
to the 'pop' row if nothing matches. The plan in NEXT_SESSION_START_HERE.md
locks 'pop' as the universal fallback.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.genre_structure import GenreStructure

logger = logging.getLogger(__name__)


REQUIRED_SECTION_KEYS = {"name", "bars", "vocals"}
FALLBACK_GENRE = "pop"


class InvalidStructureError(ValueError):
    """Raised when a structure payload fails shape/value validation."""


@dataclass
class ResolvedStructure:
    """Resolution wrapper. `primary_genre` is what the caller asked for;
    `resolved_from` is the DB row's PK that actually answered (may differ
    after a parent-chain fallback)."""
    primary_genre: str
    resolved_from: str
    structure: list[dict]
    notes: str | None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_structure(structure: Any) -> None:
    """Validate a structure payload before it ever hits the DB.

    Rules:
      - structure must be a non-empty list
      - every section must be a dict with keys {name, bars, vocals}
      - bars must be a positive integer
      - vocals must be a bool
      - name must be a non-empty string
    Raises InvalidStructureError on any violation.
    """
    if not isinstance(structure, list):
        raise InvalidStructureError(
            f"structure must be a list, got {type(structure).__name__}"
        )
    if len(structure) == 0:
        raise InvalidStructureError("structure must not be empty")
    for idx, section in enumerate(structure):
        if not isinstance(section, dict):
            raise InvalidStructureError(
                f"section {idx} must be a dict, got {type(section).__name__}"
            )
        missing = REQUIRED_SECTION_KEYS - section.keys()
        if missing:
            # surface each missing key by name in the message so the test
            # regex can match on 'name', 'bars', or 'vocals' explicitly
            raise InvalidStructureError(
                f"section {idx} missing required key(s): {sorted(missing)}"
            )
        name = section["name"]
        bars = section["bars"]
        vocals = section["vocals"]
        if not isinstance(name, str) or not name.strip():
            raise InvalidStructureError(
                f"section {idx} 'name' must be a non-empty string"
            )
        if not isinstance(bars, int) or isinstance(bars, bool) or bars <= 0:
            raise InvalidStructureError(
                f"section {idx} 'bars' must be a positive int (got {bars!r})"
            )
        if not isinstance(vocals, bool):
            raise InvalidStructureError(
                f"section {idx} 'vocals' must be a bool (got {vocals!r})"
            )


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


async def upsert_genre_structure(
    db: AsyncSession,
    *,
    primary_genre: str,
    structure: list[dict],
    notes: str | None,
    updated_by: str | None,
) -> None:
    """Insert or replace a genre_structures row.

    Validation runs first; bad input never touches the DB. Idempotent on
    primary_genre PK conflict (same key updates structure/notes/updated_*).
    """
    if not isinstance(primary_genre, str) or not primary_genre.strip():
        raise InvalidStructureError("primary_genre must be a non-empty string")
    validate_structure(structure)

    stmt = pg_insert(GenreStructure).values(
        primary_genre=primary_genre,
        structure=structure,
        notes=notes,
        updated_by=updated_by,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[GenreStructure.primary_genre],
        set_={
            "structure": stmt.excluded.structure,
            "notes": stmt.excluded.notes,
            "updated_by": stmt.excluded.updated_by,
            # updated_at is bumped by the model's onupdate trigger when an
            # ORM session flushes, but pg_insert.on_conflict_do_update
            # doesn't fire that path — set it explicitly via NOW()
            "updated_at": stmt.excluded.updated_at,
        },
    )
    await db.execute(stmt)
    await db.flush()


# ---------------------------------------------------------------------------
# Resolve (dotted chain + 'pop' fallback)
# ---------------------------------------------------------------------------


def _candidate_genre_ids(genre_id: str) -> list[str]:
    """
    Build the fallback chain for a dotted genre string.

    'caribbean.reggae.dancehall' -> [
        'caribbean.reggae.dancehall',
        'caribbean.reggae',
        'caribbean',
    ]
    'pop.k-pop' -> ['pop.k-pop', 'pop']
    'rock' -> ['rock']
    """
    if not genre_id:
        return []
    parts = genre_id.split(".")
    return [".".join(parts[: i + 1]) for i in range(len(parts) - 1, -1, -1)]


async def resolve_genre_structure(
    db: AsyncSession,
    primary_genre: str,
) -> ResolvedStructure:
    """Return the genre_structures row that best matches the given genre.

    Order:
      1. exact match on primary_genre
      2. walk dotted chain: 'pop.k-pop' -> 'pop'
      3. fall back to FALLBACK_GENRE ('pop') if seeded
      4. raise if even pop is missing — the 033 seed must have run
    """
    if not primary_genre or not isinstance(primary_genre, str):
        raise InvalidStructureError("primary_genre must be a non-empty string")

    candidates = _candidate_genre_ids(primary_genre)
    # ensure FALLBACK_GENRE is always considered last
    if FALLBACK_GENRE not in candidates:
        candidates.append(FALLBACK_GENRE)

    for candidate in candidates:
        row = (
            await db.execute(
                select(GenreStructure).where(
                    GenreStructure.primary_genre == candidate
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            return ResolvedStructure(
                primary_genre=primary_genre,
                resolved_from=candidate,
                structure=list(row.structure or []),
                notes=row.notes,
            )

    # If we get here, even 'pop' is missing — the seed migration didn't run.
    # Fail loud rather than silently returning a hardcoded fallback; a
    # missing 'pop' row is a deployment bug, not a runtime fallback case.
    raise RuntimeError(
        "genre_structures table has no row for fallback "
        f"'{FALLBACK_GENRE}' — migration 033 seed did not run"
    )
