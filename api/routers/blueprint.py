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


@router.get("/api/v1/blueprint/top-opportunities")
async def get_top_opportunities(
    n: int = 5,
    model: str = "suno",
    db: AsyncSession = Depends(get_db),
    _key: ApiKey = Depends(get_api_key_record),
):
    """
    The flagship endpoint: returns the top N breakout opportunities
    with a ready-to-use smart prompt for each.

    Picks the top N genres by opportunity score (v2), then runs the
    smart prompt generator on each in PARALLEL via asyncio.gather.
    Total wall time ≈ single LLM latency, not n × latency.

    Genres without breakout data are filtered out — only genres with
    real intelligence make the list.
    """
    import asyncio
    from api.services.blueprint_service import get_genre_opportunities
    from api.services.smart_prompt import generate_smart_prompt

    n = max(1, min(n, 10))

    # 1. Pull the top genres by opportunity score
    all_opportunities = await get_genre_opportunities(db)

    # 2. Filter to genres with actual breakout activity (avoids LLM
    #    calls on empty data)
    with_breakouts = [
        o for o in all_opportunities if o.get("breakout_count", 0) > 0
    ]
    top_n = with_breakouts[:n]

    if not top_n:
        return {
            "data": {
                "blueprints": [],
                "error": "No genres with breakout activity yet — run the breakout detection sweep first",
            }
        }

    # 3. Generate smart prompts in parallel
    tasks = [
        generate_smart_prompt(db, genre=g["genre"], model=model)
        for g in top_n
    ]
    smart_prompts = await asyncio.gather(*tasks, return_exceptions=True)

    # 4. Combine opportunity metadata with smart prompt output
    blueprints = []
    for opp, sp in zip(top_n, smart_prompts):
        if isinstance(sp, Exception):
            blueprints.append({
                "genre": opp["genre"],
                "genre_name": opp["genre_name"],
                "opportunity_score": opp["opportunity_score"],
                "breakout_count": opp["breakout_count"],
                "error": f"smart prompt failed: {type(sp).__name__}: {sp}",
            })
            continue
        blueprints.append({
            "genre": opp["genre"],
            "genre_name": opp["genre_name"],
            "opportunity_score": opp["opportunity_score"],
            "confidence": sp.get("confidence"),
            "breakout_count": opp["breakout_count"],
            "breakout_rate": opp["breakout_rate"],
            "avg_composite_ratio": opp["avg_composite_ratio"],
            "avg_velocity_ratio": opp["avg_velocity_ratio"],
            "track_count": opp["track_count"],
            "momentum": opp["momentum"],
            "score_breakdown": opp["score_breakdown"],
            "prompt": sp.get("prompt"),
            "rationale": sp.get("rationale"),
            "based_on": sp.get("based_on"),
            "model": model,
        })

    return {
        "data": {
            "blueprints": blueprints,
            "model": model,
            "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }
    }
