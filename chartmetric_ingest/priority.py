"""Priority calculation — data-driven, no hardcoded scraper priorities.

Planners compute (freshness × importance × endpoint_weight) and pass
the result to `priority_from_scores` to produce the integer priority
the queue orders on. Lower value = higher urgency.

Freshness is the only interesting transform: it's a piecewise-linear
score that hits the midpoint at the target interval, saturates to
maximum urgency at 2× target, and stays fresh (ignorable) near 0 age.
"""
from __future__ import annotations

from datetime import datetime, timezone


def freshness_score(
    last_fetched_at: datetime | None,
    target_interval_hours: float,
    *,
    now: datetime | None = None,
) -> float:
    """Return a freshness score in [0, 100].

    0 = maximally stale (most urgent to refetch)
    50 = exactly target_interval_hours since last fetch
    100 = just fetched (not urgent at all)

    Never-fetched rows score 0 so planners naturally prioritize
    brand-new entities over refresh candidates.
    """
    if target_interval_hours <= 0:
        raise ValueError("target_interval_hours must be positive")
    if last_fetched_at is None:
        return 0.0
    now = now or datetime.now(timezone.utc)
    if last_fetched_at.tzinfo is None:
        last_fetched_at = last_fetched_at.replace(tzinfo=timezone.utc)
    age_hours = (now - last_fetched_at).total_seconds() / 3600.0
    raw = 100.0 - 50.0 * (age_hours / target_interval_hours)
    return max(0.0, min(100.0, raw))


def priority_from_scores(
    freshness: float,
    importance: float = 50.0,
    endpoint_weight: float = 1.0,
) -> int:
    """Combine component scores into a queue-ready integer priority.

    Args:
        freshness: [0, 100]; 0 = stale, 100 = fresh.
        importance: [0, 100]; 100 = most important entity. Defaults
            to 50 so planners that don't have an importance signal
            yet get a reasonable midpoint.
        endpoint_weight: multiplier. 1.0 neutral, >1 boosts this
            endpoint over others, <1 deprioritizes.

    Returns:
        Integer in [0, 100] — lower is higher urgency.
    """
    freshness = max(0.0, min(100.0, freshness))
    importance = max(0.0, min(100.0, importance))
    endpoint_weight = max(0.0, endpoint_weight)

    staleness = 100.0 - freshness
    urgency = staleness * (importance / 100.0) * endpoint_weight
    urgency = max(0.0, min(100.0, urgency))
    return int(round(100.0 - urgency))
