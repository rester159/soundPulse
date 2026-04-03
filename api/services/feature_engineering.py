"""Feature engineering service for ML predictions.

Extracts time-series features from trending_snapshots to build
feature vectors used by the prediction model.
"""

import logging
import uuid
from datetime import date, timedelta
from statistics import mean, stdev

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.trending_snapshot import TrendingSnapshot

logger = logging.getLogger(__name__)

# Minimum number of snapshot days required to compute meaningful features.
MIN_HISTORY_DAYS = 1


async def get_entity_features(
    db: AsyncSession,
    entity_id: uuid.UUID,
    entity_type: str,
    as_of: date | None = None,
) -> dict | None:
    """Compute a feature-vector dict for a single entity.

    Returns None when there is not enough history to produce features.
    """
    if as_of is None:
        as_of = date.today()

    # Pull snapshots for this entity ordered by date (oldest first).
    result = await db.execute(
        select(TrendingSnapshot)
        .where(
            TrendingSnapshot.entity_id == entity_id,
            TrendingSnapshot.entity_type == entity_type,
            TrendingSnapshot.snapshot_date <= as_of,
        )
        .order_by(TrendingSnapshot.snapshot_date.asc())
    )
    snapshots = result.scalars().all()

    if not snapshots:
        return None

    # Group by date to get the best rank / composite per day.
    daily: dict[date, list[TrendingSnapshot]] = {}
    for snap in snapshots:
        daily.setdefault(snap.snapshot_date, []).append(snap)

    sorted_dates = sorted(daily.keys())
    if len(sorted_dates) < MIN_HISTORY_DAYS:
        return None

    # ── Per-day aggregated ranks (best rank across platforms per day) ──
    daily_best_ranks: list[int] = []
    daily_composite_scores: list[float] = []

    for d in sorted_dates:
        day_snaps = daily[d]
        ranks = [s.platform_rank for s in day_snaps if s.platform_rank is not None]
        composites = [s.composite_score for s in day_snaps if s.composite_score is not None]
        if ranks:
            daily_best_ranks.append(min(ranks))
        if composites:
            daily_composite_scores.append(max(composites))

    if not daily_best_ranks or len(daily_best_ranks) < MIN_HISTORY_DAYS:
        return None

    # ── Core features ──

    current_rank = daily_best_ranks[-1]
    peak_rank = min(daily_best_ranks)  # Lower is better
    days_since_first = (sorted_dates[-1] - sorted_dates[0]).days or 1

    # Velocity: average rank change per day over last 7 entries
    recent_ranks = daily_best_ranks[-7:]
    velocities: list[float] = []
    for i in range(1, len(recent_ranks)):
        # Negative velocity = improving (rank going down = getting better)
        velocities.append(float(recent_ranks[i - 1] - recent_ranks[i]))
    velocity = mean(velocities) if velocities else 0.0

    # Acceleration: change in velocity (second derivative)
    if len(velocities) >= 2:
        accels = [velocities[i] - velocities[i - 1] for i in range(1, len(velocities))]
        acceleration = mean(accels) if accels else 0.0
    else:
        acceleration = 0.0

    # Cross-platform count: unique platforms with data in the most recent date
    latest_snaps = daily[sorted_dates[-1]]
    cross_platform_count = len({s.platform for s in latest_snaps})

    # Genre momentum: average composite score trend over last 7 days
    recent_composites = daily_composite_scores[-7:]
    if len(recent_composites) >= 2:
        comp_changes = [
            recent_composites[i] - recent_composites[i - 1]
            for i in range(1, len(recent_composites))
        ]
        genre_momentum = mean(comp_changes)
    else:
        genre_momentum = 0.0

    # Rank volatility: standard deviation of recent ranks
    if len(recent_ranks) >= 2:
        rank_volatility = stdev(recent_ranks)
    else:
        rank_volatility = 0.0

    # Latest composite score
    latest_composite = daily_composite_scores[-1] if daily_composite_scores else 0.0

    return {
        "velocity": round(velocity, 4),
        "acceleration": round(acceleration, 4),
        "cross_platform_count": cross_platform_count,
        "genre_momentum": round(genre_momentum, 4),
        "days_since_first": days_since_first,
        "peak_rank": peak_rank,
        "current_rank": current_rank,
        "rank_volatility": round(rank_volatility, 4),
        "latest_composite": round(latest_composite, 4),
    }


# ── Ordered list of feature names (must match training) ──
FEATURE_NAMES: list[str] = [
    "velocity",
    "acceleration",
    "cross_platform_count",
    "genre_momentum",
    "days_since_first",
    "peak_rank",
    "current_rank",
    "rank_volatility",
    "latest_composite",
]


def features_to_vector(features: dict) -> list[float]:
    """Convert a feature dict to an ordered numeric vector."""
    return [float(features[f]) for f in FEATURE_NAMES]


async def get_entities_with_history(
    db: AsyncSession,
    min_days: int = 14,
) -> list[dict]:
    """Return entity_id / entity_type pairs that have at least *min_days* of snapshot history.

    Used by the training pipeline to discover training candidates.
    """
    stmt = (
        select(
            TrendingSnapshot.entity_id,
            TrendingSnapshot.entity_type,
            func.count(func.distinct(TrendingSnapshot.snapshot_date)).label("day_count"),
        )
        .group_by(TrendingSnapshot.entity_id, TrendingSnapshot.entity_type)
        .having(func.count(func.distinct(TrendingSnapshot.snapshot_date)) >= min_days)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {"entity_id": row.entity_id, "entity_type": row.entity_type, "day_count": row.day_count}
        for row in rows
    ]


async def did_reach_top_n(
    db: AsyncSession,
    entity_id: uuid.UUID,
    entity_type: str,
    after_date: date,
    within_days: int = 14,
    top_n: int = 20,
) -> bool:
    """Check if entity reached top *top_n* within *within_days* after *after_date*."""
    end_date = after_date + timedelta(days=within_days)
    result = await db.execute(
        select(TrendingSnapshot.platform_rank)
        .where(
            TrendingSnapshot.entity_id == entity_id,
            TrendingSnapshot.entity_type == entity_type,
            TrendingSnapshot.snapshot_date > after_date,
            TrendingSnapshot.snapshot_date <= end_date,
            TrendingSnapshot.platform_rank.isnot(None),
            TrendingSnapshot.platform_rank <= top_n,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None
