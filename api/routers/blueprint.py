"""Blueprint generation API — Song DNA analysis and prompt creation."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import get_api_key_record
from api.models.api_key import ApiKey
from api.schemas.blueprint import BlueprintRequest
from api.services.blueprint_service import generate_blueprint, get_genre_opportunities

logger = logging.getLogger(__name__)

router = APIRouter(tags=["blueprint"])


@router.get("/api/v1/blueprint/genres")
async def genre_opportunities(
    db: AsyncSession = Depends(get_db),
    _key: ApiKey = Depends(get_api_key_record),
):
    """Get genres ranked by opportunity score (trending velocity x inverse saturation)."""
    genres = await get_genre_opportunities(db)
    return {"data": genres}


@router.post("/api/v1/blueprint/generate")
async def create_blueprint(
    request: BlueprintRequest,
    db: AsyncSession = Depends(get_db),
    _key: ApiKey = Depends(get_api_key_record),
):
    """Generate a Song DNA blueprint and model-specific prompt for a genre."""
    result = await generate_blueprint(db, genre=request.genre, model=request.model)
    return {"data": result}


@router.post("/api/v1/blueprint/generate-v2")
async def create_blueprint_v2(
    request: BlueprintRequest,
    db: AsyncSession = Depends(get_db),
    _key: ApiKey = Depends(get_api_key_record),
):
    """
    Generate a smart, breakout-informed song prompt for a genre.

    Uses the Breakout Analysis Engine (Layers 1-6) to synthesize
    breakout intelligence + feature deltas + gap zones + lyrical
    themes into a production-ready prompt for Suno/Udio.

    Falls back to v1 if no breakout data exists for the genre yet.
    See planning/PRD/breakoutengine_prd.md for the architecture.
    """
    from api.services.smart_prompt import generate_smart_prompt
    result = await generate_smart_prompt(db, genre=request.genre, model=request.model)
    return {"data": result}
