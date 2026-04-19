"""
Admin CRUD endpoints for the per-genre `genre_structures` table + the
artist-level `structure_template` / `genre_structure_override` patch
(task #109 Phase 3, PRD §70).

All routes are admin-gated. Validation goes through the same
`api.services.genre_structures_service.validate_structure` that the
seed migration runs against, so manual edits land under the same
guarantees as the seed.
"""
from __future__ import annotations

import logging
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import require_admin
from api.models.ai_artist import AIArtist
from api.models.api_key import ApiKey
from api.models.genre_structure import GenreStructure
from api.services.genre_structures_service import (
    InvalidStructureError,
    upsert_genre_structure,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin", "genre-structures"])


# ----- Schemas --------------------------------------------------------------


class GenreStructureSection(BaseModel):
    name: str = Field(..., min_length=1)
    bars: int = Field(..., gt=0)
    vocals: bool


class GenreStructureUpsertBody(BaseModel):
    structure: list[GenreStructureSection] = Field(..., min_length=1)
    notes: str | None = None
    updated_by: str | None = None


class GenreStructureOut(BaseModel):
    primary_genre: str
    structure: list[dict]
    notes: str | None
    updated_at: str
    updated_by: str | None

    model_config = ConfigDict(from_attributes=True)


class ArtistStructurePatchBody(BaseModel):
    """Partial update — both fields optional. Send only what you want
    to change. To CLEAR a custom template send `structure_template: null`."""
    # Pydantic treats Optional + missing as 'not sent' via model_fields_set;
    # we use that to distinguish 'omit' from 'explicit null' below.
    structure_template: list[GenreStructureSection] | None = None
    genre_structure_override: bool | None = None


# ----- Helpers --------------------------------------------------------------


def _to_out(row: GenreStructure) -> GenreStructureOut:
    return GenreStructureOut(
        primary_genre=row.primary_genre,
        structure=list(row.structure or []),
        notes=row.notes,
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
        updated_by=row.updated_by,
    )


# ----- Genre structures CRUD ------------------------------------------------


@router.get("/api/v1/admin/genre-structures")
async def list_genre_structures(
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    rows = (await db.execute(
        select(GenreStructure).order_by(GenreStructure.primary_genre)
    )).scalars().all()
    return {"items": [_to_out(r) for r in rows], "count": len(rows)}


@router.get("/api/v1/admin/genre-structures/{primary_genre:path}")
async def get_genre_structure(
    primary_genre: str,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    row = (await db.execute(
        select(GenreStructure).where(GenreStructure.primary_genre == primary_genre)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"genre_structure not found: {primary_genre!r}")
    return _to_out(row)


@router.get("/api/v1/admin/structures-for-genre/{primary_genre:path}")
async def list_structures_for_genre(
    primary_genre: str,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Return every genre_structure whose primary_genre is on the
    dotted-chain ancestry of the requested genre. Powers the SongLab
    structure dropdown — the most-specific match is the default; the
    user can swap to a parent's structure if they prefer."""
    from api.services.genre_structures_service import _candidate_genre_ids
    candidates = _candidate_genre_ids(primary_genre)
    if not candidates:
        return {"items": []}
    rows = (await db.execute(
        select(GenreStructure).where(GenreStructure.primary_genre.in_(candidates))
    )).scalars().all()
    # Order most-specific-first so the UI default matches the resolver.
    rank = {gid: i for i, gid in enumerate(candidates)}
    rows = sorted(rows, key=lambda r: rank.get(r.primary_genre, 999))
    return {"items": [_to_out(r) for r in rows], "count": len(rows)}


@router.put("/api/v1/admin/genre-structures/{primary_genre:path}")
async def upsert_genre_structure_endpoint(
    primary_genre: str,
    body: GenreStructureUpsertBody,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    structure_payload = [s.model_dump() for s in body.structure]
    try:
        await upsert_genre_structure(
            db,
            primary_genre=primary_genre,
            structure=structure_payload,
            notes=body.notes,
            updated_by=body.updated_by or "admin_api",
        )
    except InvalidStructureError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await db.commit()
    row = (await db.execute(
        select(GenreStructure).where(GenreStructure.primary_genre == primary_genre)
    )).scalar_one()
    return _to_out(row)


@router.delete("/api/v1/admin/genre-structures/{primary_genre:path}")
async def delete_genre_structure(
    primary_genre: str,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    result = await db.execute(
        delete(GenreStructure).where(GenreStructure.primary_genre == primary_genre)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"genre_structure not found: {primary_genre!r}")
    await db.commit()
    return {"deleted": primary_genre}


# ----- Artist structure patch -----------------------------------------------


@router.patch("/api/v1/admin/artists/{artist_id}/structure")
async def patch_artist_structure(
    artist_id: str,
    body: ArtistStructurePatchBody,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Update the per-artist structure_template / genre_structure_override.

    Field-level partial: send only what changes. `structure_template:
    null` clears any existing custom template (artist follows genre row
    after that). Validation matches the seed migration's contract.
    """
    try:
        artist_uuid = _uuid.UUID(artist_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid artist_id (must be UUID)")
    artist = (await db.execute(
        select(AIArtist).where(AIArtist.artist_id == artist_uuid)
    )).scalar_one_or_none()
    if artist is None:
        raise HTTPException(status_code=404, detail="artist not found")

    fields_set = body.model_fields_set
    if "structure_template" in fields_set:
        if body.structure_template is None:
            artist.structure_template = None
        else:
            payload = [s.model_dump() for s in body.structure_template]
            # Re-run service-level validator to keep behavior identical
            # to the genre upsert path (and to the seed migration).
            from api.services.genre_structures_service import validate_structure
            try:
                validate_structure(payload)
            except InvalidStructureError as exc:
                raise HTTPException(status_code=422, detail=str(exc))
            artist.structure_template = payload
    if "genre_structure_override" in fields_set:
        artist.genre_structure_override = bool(body.genre_structure_override)

    await db.commit()
    return {
        "artist_id": str(artist.artist_id),
        "structure_template": artist.structure_template,
        "genre_structure_override": artist.genre_structure_override,
    }
