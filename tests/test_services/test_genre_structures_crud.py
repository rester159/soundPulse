"""
Unit tests for the genre_structures CRUD + dotted-genre fallback resolver
(task #109, PRD §70).

Per-genre song structure templates feed Suno prompt injection so generated
songs land within +-1 bar of a known per-genre skeleton (Intro 8, Verse 16,
Chorus 8, ...). This test file covers Phase 1 of the six-phase plan in
planning/NEXT_SESSION_START_HERE.md:

    - upsert succeeds and is idempotent (PK conflict overwrites)
    - lookup by primary_genre returns the row
    - dotted-genre fallback walks parent chain ('pop.k-pop' -> 'pop')
    - lookup of an unknown genre falls back to the 'pop' seed row
    - validation rejects bars <= 0
    - validation rejects empty structure list
    - validation rejects sections missing required keys

Tests against a real DB session (rolled back per-test by conftest's
db_session fixture). Migration 033 must have run for the seed-row tests
to pass.
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.genre_structures_service import (
    InvalidStructureError,
    resolve_genre_structure,
    upsert_genre_structure,
    validate_structure,
)


# --- Fixtures ---------------------------------------------------------------

VALID_POP_STRUCTURE = [
    {"name": "Intro", "bars": 8, "vocals": False},
    {"name": "Verse 1", "bars": 16, "vocals": True},
    {"name": "Pre-chorus", "bars": 4, "vocals": True},
    {"name": "Chorus", "bars": 8, "vocals": True},
    {"name": "Verse 2", "bars": 16, "vocals": True},
    {"name": "Pre-chorus", "bars": 4, "vocals": True},
    {"name": "Chorus", "bars": 8, "vocals": True},
    {"name": "Bridge", "bars": 8, "vocals": True},
    {"name": "Chorus", "bars": 16, "vocals": True},
    {"name": "Outro", "bars": 4, "vocals": False},
]


# --- validate_structure -----------------------------------------------------

def test_validate_structure_accepts_minimal_valid_shape():
    """Three sections, all required fields present, positive bars — passes."""
    structure = [
        {"name": "Intro", "bars": 4, "vocals": False},
        {"name": "Verse", "bars": 16, "vocals": True},
        {"name": "Outro", "bars": 4, "vocals": False},
    ]
    validate_structure(structure)  # must not raise


def test_validate_structure_rejects_empty_list():
    """An empty structure has no skeleton to inject — reject."""
    with pytest.raises(InvalidStructureError, match="empty"):
        validate_structure([])


def test_validate_structure_rejects_zero_bars():
    """A 0-bar section is musically meaningless."""
    bad = [{"name": "Intro", "bars": 0, "vocals": False}]
    with pytest.raises(InvalidStructureError, match="bars"):
        validate_structure(bad)


def test_validate_structure_rejects_negative_bars():
    """Negative bars is nonsense."""
    bad = [{"name": "Intro", "bars": -4, "vocals": False}]
    with pytest.raises(InvalidStructureError, match="bars"):
        validate_structure(bad)


def test_validate_structure_rejects_missing_name():
    bad = [{"bars": 8, "vocals": False}]
    with pytest.raises(InvalidStructureError, match="name"):
        validate_structure(bad)


def test_validate_structure_rejects_missing_bars():
    bad = [{"name": "Intro", "vocals": False}]
    with pytest.raises(InvalidStructureError, match="bars"):
        validate_structure(bad)


def test_validate_structure_rejects_missing_vocals():
    bad = [{"name": "Intro", "bars": 8}]
    with pytest.raises(InvalidStructureError, match="vocals"):
        validate_structure(bad)


def test_validate_structure_rejects_non_list_input():
    with pytest.raises(InvalidStructureError, match="list"):
        validate_structure({"name": "Intro", "bars": 8, "vocals": False})  # type: ignore[arg-type]


# --- upsert_genre_structure -------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_inserts_new_row(db_session: AsyncSession):
    """First upsert for a genre creates a row."""
    await upsert_genre_structure(
        db_session,
        primary_genre="test.brand-new-genre",
        structure=VALID_POP_STRUCTURE,
        notes="test seed",
        updated_by="pytest",
    )
    resolved = await resolve_genre_structure(db_session, "test.brand-new-genre")
    assert resolved.primary_genre == "test.brand-new-genre"
    assert resolved.resolved_from == "test.brand-new-genre"
    assert len(resolved.structure) == len(VALID_POP_STRUCTURE)
    assert resolved.structure[0]["name"] == "Intro"


@pytest.mark.asyncio
async def test_upsert_overwrites_existing_row(db_session: AsyncSession):
    """Second upsert for same genre replaces the structure (PK conflict)."""
    await upsert_genre_structure(
        db_session,
        primary_genre="test.upsert-overwrite",
        structure=[{"name": "Intro", "bars": 8, "vocals": False}],
        notes="v1",
        updated_by="pytest",
    )
    await upsert_genre_structure(
        db_session,
        primary_genre="test.upsert-overwrite",
        structure=VALID_POP_STRUCTURE,
        notes="v2",
        updated_by="pytest",
    )
    resolved = await resolve_genre_structure(db_session, "test.upsert-overwrite")
    assert len(resolved.structure) == len(VALID_POP_STRUCTURE)
    assert resolved.notes == "v2"


@pytest.mark.asyncio
async def test_upsert_rejects_invalid_structure(db_session: AsyncSession):
    """Validation runs at the service boundary — bad input never hits the DB."""
    with pytest.raises(InvalidStructureError):
        await upsert_genre_structure(
            db_session,
            primary_genre="test.rejected",
            structure=[],
            notes=None,
            updated_by="pytest",
        )


# --- resolve_genre_structure (dotted fallback) ------------------------------

@pytest.mark.asyncio
async def test_resolve_walks_dotted_chain_to_parent(db_session: AsyncSession):
    """A dotted genre with no exact row falls back to its parent.

    Uses 'pop.uk-pop' — a real taxonomy entry that's intentionally absent
    from the 033 seed — so the resolver has to walk one level up to 'pop'.
    Picking a seeded leaf (e.g. pop.k-pop) would short-circuit on the seed
    row and never exercise the chain walk.
    """
    resolved = await resolve_genre_structure(db_session, "pop.uk-pop")
    assert resolved.resolved_from == "pop"
    assert resolved.primary_genre == "pop.uk-pop"


@pytest.mark.asyncio
async def test_resolve_unknown_genre_falls_back_to_pop(db_session: AsyncSession):
    """Genre with no chain match falls back to the seeded 'pop' row."""
    resolved = await resolve_genre_structure(db_session, "nonexistent-genre-xyz")
    assert resolved.resolved_from == "pop"
    assert resolved.primary_genre == "nonexistent-genre-xyz"


@pytest.mark.asyncio
async def test_resolve_exact_match_wins_over_parent(db_session: AsyncSession):
    """Both 'pop' and 'pop.k-pop' are seeded by 033 — exact-match path
    returns the leaf, not the parent. The k-pop seed has the diagnostic
    'Dance break' section that isn't in the pop seed; assert it surfaces."""
    resolved = await resolve_genre_structure(db_session, "pop.k-pop")
    assert resolved.resolved_from == "pop.k-pop"
    assert any(s["name"] == "Dance break" for s in resolved.structure)
