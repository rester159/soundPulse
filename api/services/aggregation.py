"""Composite score recalculation and aggregation service."""

import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.trending_snapshot import TrendingSnapshot
from api.services.normalization import (
    calculate_momentum,
    calculate_rank_delta,
    calculate_velocity_7d,
    compute_composite_score,
)

logger = logging.getLogger(__name__)


async def recalculate_composite_for_entity(
    db: AsyncSession,
    entity_id: str,
    entity_type: str,
    snapshot_date: date,
) -> float | None:
    """Recalculate composite score for an entity on a given date.

    Only includes platforms with data from the last 48 hours.
    Also computes rank deltas, momentum, and 7-day velocity for each
    snapshot row on the target date.
    """
    cutoff = snapshot_date - timedelta(hours=48)

    result = await db.execute(
        select(TrendingSnapshot).where(
            TrendingSnapshot.entity_id == entity_id,
            TrendingSnapshot.entity_type == entity_type,
            TrendingSnapshot.snapshot_date >= cutoff,
        )
    )
    snapshots = result.scalars().all()

    if not snapshots:
        return None

    # Take the latest snapshot per platform
    latest_by_platform: dict[str, TrendingSnapshot] = {}
    for snap in snapshots:
        existing = latest_by_platform.get(snap.platform)
        if existing is None or snap.snapshot_date > existing.snapshot_date:
            latest_by_platform[snap.platform] = snap

    platform_scores = {p: s.normalized_score for p, s in latest_by_platform.items()}
    composite = compute_composite_score(platform_scores)

    # --- Compute rank delta for each platform snapshot on the target date ---
    for snap in snapshots:
        if snap.snapshot_date == snapshot_date:
            snap.composite_score = composite

            # Rank delta (position change from previous snapshot)
            try:
                rank_delta = await calculate_rank_delta(
                    db,
                    entity_id=str(snap.entity_id),
                    entity_type=snap.entity_type,
                    platform=snap.platform,
                    current_rank=snap.platform_rank,
                    snapshot_date=snap.snapshot_date,
                )
                # Store rank delta in signals_json so downstream consumers can read it
                signals = dict(snap.signals_json) if snap.signals_json else {}
                if rank_delta is not None:
                    signals["rank_delta"] = rank_delta
                snap.signals_json = signals
            except Exception:
                logger.debug(
                    "Failed to compute rank delta for entity=%s platform=%s",
                    entity_id,
                    snap.platform,
                )

    # --- Momentum (rising / falling / stable) ---
    try:
        momentum = await calculate_momentum(
            db,
            entity_id=str(entity_id),
            entity_type=entity_type,
            snapshot_date=snapshot_date,
        )
    except Exception:
        logger.debug("Failed to compute momentum for entity=%s", entity_id)
        momentum = "new"

    # --- 7-day velocity ---
    try:
        velocity = await calculate_velocity_7d(
            db,
            entity_id=str(entity_id),
            entity_type=entity_type,
            snapshot_date=snapshot_date,
        )
    except Exception:
        logger.debug("Failed to compute 7d velocity for entity=%s", entity_id)
        velocity = 0.0

    # Write momentum and velocity to each snapshot on the target date
    for snap in snapshots:
        if snap.snapshot_date == snapshot_date:
            snap.velocity = velocity
            signals = dict(snap.signals_json) if snap.signals_json else {}
            signals["momentum"] = momentum
            signals["velocity_7d"] = velocity
            snap.signals_json = signals

    return composite
