from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.trending_snapshot import TrendingSnapshot
from shared.constants import PLATFORM_WEIGHTS


async def normalize_score(
    db: AsyncSession,
    platform: str,
    entity_type: str,
    raw_score: float | None,
    rank: int | None = None,
) -> float:
    """Normalize raw platform score to 0-100 scale using rolling 90-day percentiles."""
    if raw_score is None:
        if rank is not None:
            return max(0.0, 100.0 - (rank * 2.0))
        return 0.0

    cutoff = date.today() - timedelta(days=90)

    result = await db.execute(
        select(
            func.percentile_cont(0.05).within_group(TrendingSnapshot.platform_score),
            func.percentile_cont(0.99).within_group(TrendingSnapshot.platform_score),
        ).where(
            TrendingSnapshot.platform == platform,
            TrendingSnapshot.entity_type == entity_type,
            TrendingSnapshot.platform_score.isnot(None),
            TrendingSnapshot.snapshot_date >= cutoff,
        )
    )
    row = result.one_or_none()

    if row is None or row[0] is None or row[1] is None:
        # Not enough historical data — use simple scaling
        return min(100.0, max(0.0, raw_score / max(raw_score, 1) * 50.0))

    p5, p99 = float(row[0]), float(row[1])
    if p99 <= p5:
        return 50.0

    normalized = ((raw_score - p5) / (p99 - p5)) * 100.0
    return min(100.0, max(0.0, round(normalized, 1)))


def compute_composite_score(platform_scores: dict[str, float]) -> float:
    """Weighted average of available platform scores, normalized to available platforms."""
    available = {p: s for p, s in platform_scores.items() if s is not None}
    if not available:
        return 0.0
    total_weight = sum(PLATFORM_WEIGHTS.get(p, 0.1) for p in available)
    if total_weight == 0:
        return 0.0
    return round(
        sum(PLATFORM_WEIGHTS.get(p, 0.1) * s / total_weight for p, s in available.items()), 1
    )


def calculate_velocity(scores: list[float | None]) -> float:
    """Linear regression slope of recent scores."""
    filled = [s for s in scores if s is not None]
    if len(filled) < 3:
        return 0.0
    import numpy as np

    x = np.arange(len(filled))
    coeffs = np.polyfit(x, filled, 1)
    return round(float(coeffs[0]), 2)


# ---------------------------------------------------------------------------
# Rank delta — position change from previous snapshot
# ---------------------------------------------------------------------------

async def calculate_rank_delta(
    db: AsyncSession,
    entity_id: str,
    entity_type: str,
    platform: str,
    current_rank: int | None,
    snapshot_date: date,
) -> int | None:
    """Return the change in rank from the most recent prior snapshot.

    A *negative* delta means the track moved UP (e.g. 5 -> 3 = -2).
    A *positive* delta means the track moved DOWN (e.g. 3 -> 5 = +2).
    Returns ``None`` when there is no previous rank to compare against.
    """
    if current_rank is None:
        return None

    result = await db.execute(
        select(TrendingSnapshot.platform_rank)
        .where(
            TrendingSnapshot.entity_id == entity_id,
            TrendingSnapshot.entity_type == entity_type,
            TrendingSnapshot.platform == platform,
            TrendingSnapshot.snapshot_date < snapshot_date,
            TrendingSnapshot.platform_rank.isnot(None),
        )
        .order_by(TrendingSnapshot.snapshot_date.desc())
        .limit(1)
    )
    previous_rank = result.scalar_one_or_none()

    if previous_rank is None:
        return None

    return current_rank - previous_rank


# ---------------------------------------------------------------------------
# Momentum — rising / falling / stable classification
# ---------------------------------------------------------------------------

MOMENTUM_RISING = "rising"
MOMENTUM_FALLING = "falling"
MOMENTUM_STABLE = "stable"
MOMENTUM_NEW = "new"


async def calculate_momentum(
    db: AsyncSession,
    entity_id: str,
    entity_type: str,
    snapshot_date: date,
    lookback_days: int = 3,
) -> str:
    """Determine whether an entity is rising, falling, or stable.

    Examines composite scores over the last ``lookback_days`` snapshots and
    computes a simple trend direction.

    Returns one of: ``"rising"``, ``"falling"``, ``"stable"``, ``"new"``.
    """
    cutoff = snapshot_date - timedelta(days=lookback_days)

    result = await db.execute(
        select(
            TrendingSnapshot.snapshot_date,
            TrendingSnapshot.composite_score,
        )
        .where(
            TrendingSnapshot.entity_id == entity_id,
            TrendingSnapshot.entity_type == entity_type,
            TrendingSnapshot.composite_score.isnot(None),
            TrendingSnapshot.snapshot_date >= cutoff,
            TrendingSnapshot.snapshot_date <= snapshot_date,
        )
        .order_by(TrendingSnapshot.snapshot_date.asc())
        .distinct(TrendingSnapshot.snapshot_date)
    )
    rows = result.all()

    scores = [float(row[1]) for row in rows if row[1] is not None]

    if len(scores) < 2:
        return MOMENTUM_NEW

    # Compare the average of the recent half vs. the earlier half
    mid = len(scores) // 2
    earlier_avg = sum(scores[:mid]) / mid
    later_avg = sum(scores[mid:]) / len(scores[mid:])

    pct_change = (later_avg - earlier_avg) / max(earlier_avg, 1.0) * 100.0

    if pct_change >= 5.0:
        return MOMENTUM_RISING
    if pct_change <= -5.0:
        return MOMENTUM_FALLING
    return MOMENTUM_STABLE


# ---------------------------------------------------------------------------
# 7-day velocity — rate of change over a 7-day window
# ---------------------------------------------------------------------------

async def calculate_velocity_7d(
    db: AsyncSession,
    entity_id: str,
    entity_type: str,
    snapshot_date: date,
) -> float:
    """Compute the velocity (rate of composite-score change) over the last 7 days.

    Uses a least-squares linear regression over daily composite scores,
    weighted by platform weights from ``shared.constants``.  The slope
    represents how many composite-score points the entity gains or loses
    per day.
    """
    cutoff = snapshot_date - timedelta(days=7)

    result = await db.execute(
        select(
            TrendingSnapshot.snapshot_date,
            TrendingSnapshot.composite_score,
        )
        .where(
            TrendingSnapshot.entity_id == entity_id,
            TrendingSnapshot.entity_type == entity_type,
            TrendingSnapshot.composite_score.isnot(None),
            TrendingSnapshot.snapshot_date >= cutoff,
            TrendingSnapshot.snapshot_date <= snapshot_date,
        )
        .order_by(TrendingSnapshot.snapshot_date.asc())
        .distinct(TrendingSnapshot.snapshot_date)
    )
    rows = result.all()

    # Collect one composite score per day (take the latest if duplicates exist)
    daily_scores: dict[date, float] = {}
    for row in rows:
        d, score = row[0], row[1]
        if score is not None:
            daily_scores[d] = float(score)

    if len(daily_scores) < 3:
        return 0.0

    import numpy as np

    sorted_dates = sorted(daily_scores.keys())
    base_date = sorted_dates[0]
    x = np.array([(d - base_date).days for d in sorted_dates], dtype=float)
    y = np.array([daily_scores[d] for d in sorted_dates], dtype=float)

    coeffs = np.polyfit(x, y, 1)
    return round(float(coeffs[0]), 2)
