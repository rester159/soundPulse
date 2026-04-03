"""Backtesting API endpoints — model validation against historical data."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import require_admin, require_api_key
from api.models.api_key import ApiKey
from api.models.backtest_result import BacktestResult
from api.schemas.backtesting import BacktestRunRequest
from api.services.backtest_service import (
    get_backtest_timeline,
    get_genre_breakdown,
    run_backtest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["backtesting"])


@router.post("/api/v1/backtesting/run", status_code=202)
async def start_backtest(
    request: BacktestRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Trigger a backtest run in the background."""
    from api.database import async_session_factory

    async def _run():
        async with async_session_factory() as session:
            try:
                run_id = await run_backtest(
                    session,
                    months=request.months,
                    horizon=request.horizon,
                    entity_type=request.entity_type,
                    genre=request.genre,
                    top_n=request.top_n,
                )
                logger.info("Backtest completed: run_id=%s", run_id)
            except Exception as e:
                logger.error("Backtest failed: %s", e, exc_info=True)

    background_tasks.add_task(asyncio.ensure_future, _run())

    return {
        "detail": f"Backtest started: {request.months} months, horizon={request.horizon}",
        "months": request.months,
        "horizon": request.horizon,
        "entity_type": request.entity_type,
        "genre": request.genre,
    }


@router.get("/api/v1/backtesting/results")
async def get_results(
    run_id: str | None = Query(None),
    entity_type: str | None = Query(None),
    genre: str | None = Query(None),
    horizon: str = Query("7d"),
    db: AsyncSession = Depends(get_db),
    _key: ApiKey = Depends(require_api_key),
):
    """Get backtest results as a timeline for charting."""
    timeline = await get_backtest_timeline(db, run_id, entity_type, genre, horizon)

    # Compute summary
    if timeline:
        overall_mae = sum(p["mae"] for p in timeline if p["mae"]) / len(timeline)
        overall_precision = sum(p["precision"] for p in timeline if p["precision"]) / len(timeline)
        overall_recall = sum(p["recall"] for p in timeline if p["recall"]) / len(timeline)
        overall_f1 = sum(p["f1"] for p in timeline if p["f1"]) / len(timeline)
        total_samples = sum(p["sample_count"] for p in timeline)
        total_positives = sum(p["positive_count"] for p in timeline)
    else:
        overall_mae = overall_precision = overall_recall = overall_f1 = None
        total_samples = total_positives = 0

    return {
        "data": {
            "timeline": timeline,
            "summary": {
                "overall_mae": round(overall_mae, 4) if overall_mae else None,
                "overall_precision": round(overall_precision, 4) if overall_precision else None,
                "overall_recall": round(overall_recall, 4) if overall_recall else None,
                "overall_f1": round(overall_f1, 4) if overall_f1 else None,
                "total_samples": total_samples,
                "total_positives": total_positives,
                "period_count": len(timeline),
            },
        },
        "meta": {
            "entity_type": entity_type,
            "genre": genre,
            "horizon": horizon,
        },
    }


@router.get("/api/v1/backtesting/runs")
async def list_runs(
    db: AsyncSession = Depends(get_db),
    _key: ApiKey = Depends(require_api_key),
):
    """List all backtest runs."""
    result = await db.execute(
        select(
            BacktestResult.run_id,
            BacktestResult.entity_type,
            BacktestResult.genre_filter,
            BacktestResult.horizon,
            func.count(BacktestResult.id).label("period_count"),
            func.avg(BacktestResult.mae).label("avg_mae"),
            func.min(BacktestResult.created_at).label("created_at"),
        )
        .where(BacktestResult.status == "completed")
        .group_by(
            BacktestResult.run_id,
            BacktestResult.entity_type,
            BacktestResult.genre_filter,
            BacktestResult.horizon,
        )
        .order_by(func.min(BacktestResult.created_at).desc())
        .limit(20)
    )
    rows = result.all()

    return {
        "data": [
            {
                "run_id": row.run_id,
                "entity_type": row.entity_type,
                "genre": row.genre_filter,
                "horizon": row.horizon,
                "period_count": row.period_count,
                "overall_mae": round(float(row.avg_mae), 4) if row.avg_mae else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }


@router.get("/api/v1/backtesting/genres")
async def genre_breakdown(
    run_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _key: ApiKey = Depends(require_api_key),
):
    """Get per-genre accuracy breakdown."""
    genres = await get_genre_breakdown(db, run_id)
    return {"data": genres}
