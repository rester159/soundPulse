"""Blueprint generation API — Song DNA analysis and prompt creation."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import require_api_key
from api.models.api_key import ApiKey
from api.schemas.blueprint import BlueprintRequest
from api.services.blueprint_service import generate_blueprint, get_genre_opportunities

logger = logging.getLogger(__name__)

router = APIRouter(tags=["blueprint"])


@router.get("/api/v1/blueprint/genres")
async def genre_opportunities(
    db: AsyncSession = Depends(get_db),
    _key: ApiKey = Depends(require_api_key),
):
    """Get genres ranked by opportunity score (trending velocity x inverse saturation)."""
    genres = await get_genre_opportunities(db)
    return {"data": genres}


@router.post("/api/v1/blueprint/generate")
async def create_blueprint(
    request: BlueprintRequest,
    db: AsyncSession = Depends(get_db),
    _key: ApiKey = Depends(require_api_key),
):
    """Generate a Song DNA blueprint and model-specific prompt for a genre."""
    result = await generate_blueprint(db, genre=request.genre, model=request.model)
    return {"data": result}
