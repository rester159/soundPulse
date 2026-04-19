"""
Admin CRUD for the rights_holders table (migration 036).

One polymorphic endpoint set handles all three kinds (publisher, writer,
composer) — the UI filters by ?kind= when listing. Same shape on
create/update; the kind field is fixed at create time and not editable
afterward (a writer doesn't morph into a publisher).
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
from api.models.api_key import ApiKey
from api.models.rights_holder import RightsHolder

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin", "rights-holders"])

VALID_KINDS = {"publisher", "writer", "composer"}


class RightsHolderCreate(BaseModel):
    kind: str = Field(..., description="publisher | writer | composer")
    legal_name: str = Field(..., min_length=1)
    stage_name: str | None = None
    ipi_number: str | None = None
    isni: str | None = None
    pro_affiliation: str | None = None  # ASCAP / BMI / SESAC / GMR / PRS / etc.
    publisher_company_name: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    tax_id: str | None = None
    default_split_percent: float | None = None
    notes: str | None = None


class RightsHolderUpdate(BaseModel):
    """Partial update — kind is intentionally NOT editable."""
    legal_name: str | None = None
    stage_name: str | None = None
    ipi_number: str | None = None
    isni: str | None = None
    pro_affiliation: str | None = None
    publisher_company_name: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    tax_id: str | None = None
    default_split_percent: float | None = None
    notes: str | None = None


class RightsHolderOut(BaseModel):
    id: str
    kind: str
    legal_name: str
    stage_name: str | None
    ipi_number: str | None
    isni: str | None
    pro_affiliation: str | None
    publisher_company_name: str | None
    email: str | None
    phone: str | None
    address: str | None
    tax_id: str | None
    default_split_percent: float | None
    notes: str | None
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


def _to_out(row: RightsHolder) -> dict:
    return {
        "id": str(row.id),
        "kind": row.kind,
        "legal_name": row.legal_name,
        "stage_name": row.stage_name,
        "ipi_number": row.ipi_number,
        "isni": row.isni,
        "pro_affiliation": row.pro_affiliation,
        "publisher_company_name": row.publisher_company_name,
        "email": row.email,
        "phone": row.phone,
        "address": row.address,
        "tax_id": row.tax_id,
        "default_split_percent": row.default_split_percent,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }


@router.get("/api/v1/admin/rights-holders")
async def list_rights_holders(
    kind: str | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    stmt = select(RightsHolder).order_by(RightsHolder.kind, RightsHolder.legal_name)
    if kind:
        if kind not in VALID_KINDS:
            raise HTTPException(400, detail=f"kind must be one of {sorted(VALID_KINDS)}")
        stmt = stmt.where(RightsHolder.kind == kind)
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "items": [_to_out(r) for r in rows],
        "count": len(rows),
        "by_kind": {
            k: sum(1 for r in rows if r.kind == k) for k in VALID_KINDS
        } if not kind else None,
    }


@router.get("/api/v1/admin/rights-holders/{holder_id}")
async def get_rights_holder(
    holder_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    try:
        hid = _uuid.UUID(holder_id)
    except ValueError:
        raise HTTPException(400, detail="invalid holder_id (must be UUID)")
    row = (await db.execute(
        select(RightsHolder).where(RightsHolder.id == hid)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, detail="rights holder not found")
    return _to_out(row)


@router.post("/api/v1/admin/rights-holders")
async def create_rights_holder(
    body: RightsHolderCreate,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    if body.kind not in VALID_KINDS:
        raise HTTPException(400, detail=f"kind must be one of {sorted(VALID_KINDS)}")
    if body.default_split_percent is not None and not (0 <= body.default_split_percent <= 100):
        raise HTTPException(400, detail="default_split_percent must be 0-100")
    row = RightsHolder(
        kind=body.kind,
        legal_name=body.legal_name.strip(),
        stage_name=(body.stage_name or "").strip() or None,
        ipi_number=(body.ipi_number or "").strip() or None,
        isni=(body.isni or "").strip() or None,
        pro_affiliation=(body.pro_affiliation or "").strip() or None,
        publisher_company_name=(body.publisher_company_name or "").strip() or None,
        email=(body.email or "").strip() or None,
        phone=(body.phone or "").strip() or None,
        address=(body.address or "").strip() or None,
        tax_id=(body.tax_id or "").strip() or None,
        default_split_percent=body.default_split_percent,
        notes=(body.notes or "").strip() or None,
    )
    db.add(row)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(409, detail=f"create failed: {exc}")
    await db.refresh(row)
    return _to_out(row)


@router.patch("/api/v1/admin/rights-holders/{holder_id}")
async def update_rights_holder(
    holder_id: str,
    body: RightsHolderUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    try:
        hid = _uuid.UUID(holder_id)
    except ValueError:
        raise HTTPException(400, detail="invalid holder_id (must be UUID)")
    row = (await db.execute(
        select(RightsHolder).where(RightsHolder.id == hid)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, detail="rights holder not found")

    fields_set = body.model_fields_set
    if not fields_set:
        raise HTTPException(400, detail="no editable fields in body")

    for key in fields_set:
        v = getattr(body, key)
        if key == "legal_name":
            if v is None or not str(v).strip():
                raise HTTPException(400, detail="legal_name cannot be cleared")
            setattr(row, key, str(v).strip())
        elif key == "default_split_percent":
            if v is not None and not (0 <= v <= 100):
                raise HTTPException(400, detail="default_split_percent must be 0-100")
            setattr(row, key, v)
        else:
            # Other text fields — None or trimmed string
            if v is None:
                setattr(row, key, None)
            else:
                s = str(v).strip()
                setattr(row, key, s if s else None)

    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(409, detail=f"update failed: {exc}")
    await db.refresh(row)
    return {**_to_out(row), "fields_updated": sorted(fields_set)}


@router.delete("/api/v1/admin/rights-holders/{holder_id}")
async def delete_rights_holder(
    holder_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    try:
        hid = _uuid.UUID(holder_id)
    except ValueError:
        raise HTTPException(400, detail="invalid holder_id (must be UUID)")
    result = await db.execute(
        delete(RightsHolder).where(RightsHolder.id == hid)
    )
    if result.rowcount == 0:
        raise HTTPException(404, detail="rights holder not found")
    await db.commit()
    return {"deleted": holder_id}
