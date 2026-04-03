"""
Backtesting service — evaluates prediction accuracy against historical data.

For each monthly evaluation point, computes features from data available before
that date, generates predictions, and compares against what actually happened.
"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import date, timedelta
from typing import Any

import numpy as np
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.backtest_result import BacktestResult
from api.models.trending_snapshot import TrendingSnapshot
from api.models.track import Track
from api.models.artist import Artist

logger = logging.getLogger(__name__)

# Horizon string to days mapping
HORIZON_DAYS = {"7d": 7, "14d": 14, "30d": 30, "90d": 90}


async def run_backtest(
    db: AsyncSession,
    months: int = 24,
    horizon: str = "7d",
    entity_type: str | None = None,
    genre: str | None = None,
    top_n: int = 50,
) -> str:
    """
    Run a full backtest over the specified number of months.

    For each monthly evaluation date:
    1. Find entities with data before that date
    2. Compute a simple predicted score from recent trend data
    3. Check if entity actually broke into top_n within horizon_days
    4. Aggregate metrics (MAE, precision, recall, F1)

    Returns the run_id for querying results.
    """
    run_id = str(uuid.uuid4())
    horizon_days = HORIZON_DAYS.get(horizon, 7)

    # Find the date range of available data
    result = await db.execute(
        select(func.min(TrendingSnapshot.snapshot_date), func.max(TrendingSnapshot.snapshot_date))
    )
    row = result.one_or_none()
    if not row or not row[0] or not row[1]:
        logger.warning("No snapshot data available for backtesting")
        return run_id

    data_start, data_end = row[0], row[1]
    logger.info("Backtest data range: %s to %s", data_start, data_end)

    # Generate monthly evaluation dates
    eval_dates = []
    current = data_start + timedelta(days=30)  # need at least 30 days of history
    while current <= data_end - timedelta(days=horizon_days):
        eval_dates.append(current)
        current += timedelta(days=30)

    # Limit to requested months
    if len(eval_dates) > months:
        eval_dates = eval_dates[-months:]

    logger.info("Backtest: %d evaluation periods, horizon=%s, top_n=%d", len(eval_dates), horizon, top_n)

    for eval_date in eval_dates:
        try:
            result_row = await _evaluate_period(
                db, run_id, eval_date, horizon_days, top_n, entity_type, genre, horizon
            )
            if result_row:
                db.add(result_row)
                await db.commit()
                logger.info(
                    "Backtest %s: samples=%d, mae=%.3f, precision=%.3f",
                    eval_date, result_row.sample_count, result_row.mae or 0, result_row.precision_score or 0,
                )
        except Exception as e:
            logger.error("Backtest error for %s: %s", eval_date, e)
            await db.rollback()

    return run_id


async def _evaluate_period(
    db: AsyncSession,
    run_id: str,
    eval_date: date,
    horizon_days: int,
    top_n: int,
    entity_type: str | None,
    genre: str | None,
    horizon: str,
) -> BacktestResult | None:
    """Evaluate prediction accuracy for a single period."""

    # Get entities that have data before eval_date with enough history
    lookback_start = eval_date - timedelta(days=30)

    query = (
        select(
            TrendingSnapshot.entity_id,
            TrendingSnapshot.entity_type,
            func.count(TrendingSnapshot.id).label("snapshot_count"),
            func.avg(TrendingSnapshot.composite_score).label("avg_score"),
            func.max(TrendingSnapshot.composite_score).label("max_score"),
        )
        .where(TrendingSnapshot.snapshot_date.between(lookback_start, eval_date))
        .group_by(TrendingSnapshot.entity_id, TrendingSnapshot.entity_type)
        .having(func.count(TrendingSnapshot.id) >= 2)
    )

    if entity_type:
        query = query.where(TrendingSnapshot.entity_type == entity_type)

    result = await db.execute(query)
    entities = result.all()

    if not entities:
        return None

    # For genre filtering, get entity genres
    genre_filtered = []
    for ent in entities:
        if genre:
            if ent.entity_type == "track":
                track_result = await db.execute(
                    select(Track.genres).where(Track.id == ent.entity_id)
                )
                track_row = track_result.one_or_none()
                if track_row and track_row[0]:
                    if any(g.startswith(genre) for g in track_row[0]):
                        genre_filtered.append(ent)
            elif ent.entity_type == "artist":
                artist_result = await db.execute(
                    select(Artist.genres).where(Artist.id == ent.entity_id)
                )
                artist_row = artist_result.one_or_none()
                if artist_row and artist_row[0]:
                    if any(g.startswith(genre) for g in artist_row[0]):
                        genre_filtered.append(ent)
        else:
            genre_filtered.append(ent)

    if not genre_filtered:
        return None

    # For each entity: predict and check actual outcome
    predictions = []
    actuals = []
    details = []

    for ent in genre_filtered[:200]:  # Cap at 200 entities per period for performance
        # Simple prediction: use recent momentum as probability proxy
        predicted_prob = _compute_prediction(ent.avg_score, ent.max_score, ent.snapshot_count)

        # Check actual outcome: did entity appear in top_n within horizon?
        actual = await _check_actual_outcome(
            db, ent.entity_id, ent.entity_type, eval_date, horizon_days, top_n
        )

        predictions.append(predicted_prob)
        actuals.append(float(actual))
        details.append({
            "entity_id": str(ent.entity_id),
            "entity_type": ent.entity_type,
            "predicted_prob": round(predicted_prob, 4),
            "actual_outcome": actual,
            "error": round(abs(predicted_prob - float(actual)), 4),
        })

    if not predictions:
        return None

    # Compute aggregate metrics
    preds_arr = np.array(predictions)
    actuals_arr = np.array(actuals)

    mae = float(np.mean(np.abs(preds_arr - actuals_arr)))
    rmse = float(np.sqrt(np.mean((preds_arr - actuals_arr) ** 2)))

    # Binary classification metrics (threshold at 0.5)
    pred_binary = (preds_arr >= 0.5).astype(float)
    true_positives = float(np.sum((pred_binary == 1) & (actuals_arr == 1)))
    false_positives = float(np.sum((pred_binary == 1) & (actuals_arr == 0)))
    false_negatives = float(np.sum((pred_binary == 0) & (actuals_arr == 1)))

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return BacktestResult(
        run_id=run_id,
        evaluation_date=eval_date,
        entity_type=entity_type,
        genre_filter=genre,
        horizon=horizon,
        mae=mae,
        rmse=rmse,
        precision_score=precision,
        recall_score=recall,
        f1_score=f1,
        sample_count=len(predictions),
        positive_count=int(sum(actuals)),
        predicted_avg=float(np.mean(preds_arr)),
        actual_rate=float(np.mean(actuals_arr)),
        model_version="rule-v1.0",
        status="completed",
        details_json={"entities": details[:50]},  # Store top 50 for detail view
    )


def _compute_prediction(avg_score: float | None, max_score: float | None, snapshot_count: int) -> float:
    """
    Simple rule-based prediction: probability of breaking into top charts.

    Uses recent average score, peak score, and data density as signals.
    This will be replaced by ML ensemble once trained.
    """
    if avg_score is None:
        return 0.1

    # Normalize score to 0-1 probability
    score_signal = min(1.0, (avg_score or 0) / 100.0)
    peak_signal = min(1.0, (max_score or 0) / 100.0)
    density_signal = min(1.0, snapshot_count / 20.0)

    # Weighted combination
    prob = 0.4 * score_signal + 0.4 * peak_signal + 0.2 * density_signal
    return max(0.01, min(0.99, prob))


async def _check_actual_outcome(
    db: AsyncSession,
    entity_id: str,
    entity_type: str,
    eval_date: date,
    horizon_days: int,
    top_n: int,
) -> int:
    """Check if entity appeared in top_n chart positions within horizon after eval_date."""
    future_start = eval_date + timedelta(days=1)
    future_end = eval_date + timedelta(days=horizon_days)

    result = await db.execute(
        select(func.min(TrendingSnapshot.platform_rank))
        .where(
            TrendingSnapshot.entity_id == entity_id,
            TrendingSnapshot.entity_type == entity_type,
            TrendingSnapshot.snapshot_date.between(future_start, future_end),
            TrendingSnapshot.platform_rank.isnot(None),
        )
    )
    best_rank = result.scalar()
    return 1 if best_rank is not None and best_rank <= top_n else 0


async def get_backtest_timeline(
    db: AsyncSession,
    run_id: str | None = None,
    entity_type: str | None = None,
    genre: str | None = None,
    horizon: str = "7d",
) -> list[dict]:
    """Get backtest results as a timeline for charting."""
    query = select(BacktestResult).where(BacktestResult.status == "completed")

    if run_id:
        query = query.where(BacktestResult.run_id == run_id)
    else:
        # Get the most recent run matching filters
        sub = (
            select(BacktestResult.run_id)
            .where(BacktestResult.status == "completed")
        )
        if entity_type:
            sub = sub.where(BacktestResult.entity_type == entity_type)
        if genre:
            sub = sub.where(BacktestResult.genre_filter == genre)
        sub = sub.where(BacktestResult.horizon == horizon)
        sub = sub.order_by(BacktestResult.created_at.desc()).limit(1)

        result = await db.execute(sub)
        latest_run_id = result.scalar()
        if not latest_run_id:
            return []
        query = query.where(BacktestResult.run_id == latest_run_id)

    query = query.order_by(BacktestResult.evaluation_date.asc())
    result = await db.execute(query)
    rows = result.scalars().all()

    return [
        {
            "evaluation_date": row.evaluation_date.isoformat(),
            "mae": round(row.mae, 4) if row.mae else None,
            "rmse": round(row.rmse, 4) if row.rmse else None,
            "precision": round(row.precision_score, 4) if row.precision_score else None,
            "recall": round(row.recall_score, 4) if row.recall_score else None,
            "f1": round(row.f1_score, 4) if row.f1_score else None,
            "sample_count": row.sample_count,
            "positive_count": row.positive_count,
            "predicted_avg": round(row.predicted_avg, 4) if row.predicted_avg else None,
            "actual_rate": round(row.actual_rate, 4) if row.actual_rate else None,
            "model_version": row.model_version,
        }
        for row in rows
    ]


async def get_genre_breakdown(db: AsyncSession, run_id: str | None = None) -> list[dict]:
    """Get per-genre accuracy breakdown from backtest results."""
    query = (
        select(
            BacktestResult.genre_filter,
            func.avg(BacktestResult.mae).label("avg_mae"),
            func.avg(BacktestResult.precision_score).label("avg_precision"),
            func.avg(BacktestResult.recall_score).label("avg_recall"),
            func.avg(BacktestResult.f1_score).label("avg_f1"),
            func.sum(BacktestResult.sample_count).label("total_samples"),
        )
        .where(BacktestResult.status == "completed")
        .group_by(BacktestResult.genre_filter)
        .order_by(func.sum(BacktestResult.sample_count).desc())
    )

    if run_id:
        query = query.where(BacktestResult.run_id == run_id)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "genre": row.genre_filter or "all",
            "mae": round(float(row.avg_mae), 4) if row.avg_mae else None,
            "precision": round(float(row.avg_precision), 4) if row.avg_precision else None,
            "recall": round(float(row.avg_recall), 4) if row.avg_recall else None,
            "f1": round(float(row.avg_f1), 4) if row.avg_f1 else None,
            "sample_count": int(row.total_samples) if row.total_samples else 0,
        }
        for row in rows
    ]
