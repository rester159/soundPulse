"""
Deferred composite-score recalc sweep.

The bulk ingest endpoint (`POST /api/v1/trending/bulk`) inserts snapshots
with `normalized_score = 0.0` and skips the `recalculate_composite_for_entity`
call. This sweep finds those rows, normalizes them, then recalculates the
composite score for each affected (entity_id, snapshot_date) pair.

Why deferred:
  - The normalization query hits a 90-day rolling percentile aggregate
    against `trending_snapshots`. Doing it inline in the bulk path turns a
    fast batch upsert into N round-trips.
  - The composite recalc loads all of an entity's snapshots from the last
    48 hours, then writes back to several rows including momentum + velocity.
    Inline = thrash.

Idempotency:
  - The sweep targets rows where `normalized_score = 0` AND the marker
    `signals_json->>'normalized_at'` is NULL. After processing, the marker
    is set so the row is not picked up again.
  - Each batch is one DB transaction.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.trending_snapshot import TrendingSnapshot
from api.services.aggregation import recalculate_composite_for_entity
from api.services.normalization import normalize_score

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 1000


async def sweep_zero_normalized_snapshots(
    db: AsyncSession,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, int]:
    """
    Process up to `batch_size` snapshots that need normalization + composite recalc.

    Returns stats dict.
    """
    started = datetime.now(timezone.utc)

    # Find candidates: rows where normalized_score is 0, we have something to
    # score with (raw_score or rank), and they haven't been processed yet
    stmt = (
        select(TrendingSnapshot)
        .where(
            TrendingSnapshot.normalized_score == 0,
            or_(
                TrendingSnapshot.platform_score.isnot(None),
                TrendingSnapshot.platform_rank.isnot(None),
            ),
            text("signals_json->>'normalized_at' IS NULL"),
        )
        .order_by(TrendingSnapshot.created_at.asc())
        .limit(batch_size)
    )
    result = await db.execute(stmt)
    snapshots = result.scalars().all()

    if not snapshots:
        return {
            "snapshots_processed": 0,
            "composites_recalculated": 0,
            "errors": 0,
            "elapsed_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        }

    snap_processed = 0
    snap_failed = 0

    # Step 1: normalize each snapshot
    for snap in snapshots:
        try:
            new_score = await normalize_score(
                db,
                snap.platform,
                snap.entity_type,
                snap.platform_score,
                snap.platform_rank,
            )
            snap.normalized_score = new_score
            # Mark as processed so we don't reprocess on the next sweep
            snap.signals_json = {
                **(snap.signals_json or {}),
                "normalized_at": datetime.now(timezone.utc).isoformat(),
                "normalized_via": "sweep",
            }
            snap_processed += 1
        except Exception as exc:
            snap_failed += 1
            logger.warning(
                "[composite-sweep] failed to normalize snapshot %s: %s",
                snap.id, exc,
            )

    await db.flush()

    # Step 2: recompute composite for each unique (entity_id, entity_type, snapshot_date)
    affected_keys: set[tuple[str, str, Any]] = set()
    for snap in snapshots:
        if snap.normalized_score and snap.normalized_score > 0:
            affected_keys.add(
                (str(snap.entity_id), snap.entity_type, snap.snapshot_date)
            )

    composites_done = 0
    composite_failed = 0
    for entity_id, entity_type, snap_date in affected_keys:
        try:
            await recalculate_composite_for_entity(db, entity_id, entity_type, snap_date)
            composites_done += 1
        except Exception as exc:
            composite_failed += 1
            logger.warning(
                "[composite-sweep] failed to recalc composite entity=%s type=%s date=%s: %s",
                entity_id, entity_type, snap_date, exc,
            )

    await db.commit()

    elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    result_stats = {
        "snapshots_processed": snap_processed,
        "snapshots_failed": snap_failed,
        "composites_recalculated": composites_done,
        "composites_failed": composite_failed,
        "unique_entity_dates": len(affected_keys),
        "elapsed_ms": elapsed_ms,
    }
    logger.info("[composite-sweep] %s", result_stats)
    return result_stats


async def count_pending_normalization(db: AsyncSession) -> dict[str, int]:
    """Status check: how many snapshots are waiting?"""
    pending = (await db.execute(text("""
        SELECT COUNT(*) FROM trending_snapshots
        WHERE normalized_score = 0
          AND (platform_score IS NOT NULL OR platform_rank IS NOT NULL)
          AND (signals_json->>'normalized_at') IS NULL
    """))).scalar() or 0
    no_score = (await db.execute(text("""
        SELECT COUNT(*) FROM trending_snapshots
        WHERE normalized_score = 0
          AND platform_score IS NULL
          AND platform_rank IS NULL
    """))).scalar() or 0
    return {
        "snapshots_pending_normalization": int(pending),
        "snapshots_unscoreable": int(no_score),
    }
