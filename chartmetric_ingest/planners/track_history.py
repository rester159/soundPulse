"""Track history planner — emits per-track `/stat/{platform}` fetch jobs.

For each (track, platform) pair where the track has a chartmetric_id:
  1. Compute staleness from MAX(track_stat_history.pulled_at)
  2. Derive priority from freshness + platform weight (from
     chartmetric_endpoint_config)
  3. Enqueue a fetch job; dedup on URL+params means re-emits of still-
     pending jobs just bump priority/expiry without duplicating

Platform set lives in `PLATFORM_SPECS` and is the single source of
truth for both the planner (which request to emit) and the
`handlers/track_history.py` handler (which metrics to persist).
Adding a platform is one edit here — no migration, no handler
change, no fetcher change.

Per-run enqueue cap
-------------------
The planner doesn't try to fill the queue forever. Each run enqueues
up to `BATCH_SIZE_PER_PLATFORM` of the stalest candidates for every
enabled platform. The queue's pending-dedup index means rerunning
before the fetcher drains the previous batch just refreshes priority
on the existing rows.

Generality note
---------------
PLATFORM_SPECS looks like a "hardcoded list" but it isn't instance-
or tenant-specific: it's the contract between Chartmetric's
`/track/{id}/stat/{platform}` endpoint family and our
`track_stat_history` table schema. Every (platform, metric) here
maps 1:1 to a column Chartmetric returns under `obj.<metric>`. It's
runtime-tunable via `chartmetric_endpoint_config.enabled` — flipping
`enabled=False` on `track_stat_shazam` makes the planner skip that
platform without a redeploy.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.chartmetric_queue import ChartmetricEndpointConfig
from chartmetric_ingest import queue as cmq_queue
from chartmetric_ingest.planners import register
from chartmetric_ingest.priority import freshness_score, priority_from_scores

logger = logging.getLogger(__name__)


# Single source of truth for "what per-track platform stats does
# chartmetric_ingest pull?" Each platform has an endpoint_key that
# matches a row in chartmetric_endpoint_config, the Chartmetric path
# segment, and the list of metric keys the handler will persist.
PLATFORM_SPECS: list[dict[str, Any]] = [
    {
        "endpoint_key": "track_stat_spotify",
        "platform": "spotify",
        "metrics": ["streams", "popularity", "playlist_reach"],
    },
    {
        "endpoint_key": "track_stat_tiktok",
        "platform": "tiktok",
        "metrics": ["video_count", "view_count"],
    },
    {
        "endpoint_key": "track_stat_shazam",
        "platform": "shazam",
        "metrics": ["count"],
    },
]


API_BASE = "https://api.chartmetric.com"
HANDLER_NAME = "track_history"
PRODUCER_NAME = "planner_track_history"
# Sized to keep the queue saturated against the 1.8 req/s fetcher:
#   runs/hour = 3600 / PLANNER_INTERVAL_SECONDS
#   emission/hour = BATCH_SIZE_PER_PLATFORM * 3 platforms * runs/hour
# Must exceed 6,480 req/hour (the fetcher drain rate) with margin
# so dedup-merged re-emits don't accidentally starve the queue.
PLANNER_INTERVAL_SECONDS = 180.0   # 3 minutes
BATCH_SIZE_PER_PLATFORM = 1500     # 1500 * 3 * 20 = 90k/hr emission ceiling
JOB_EXPIRES_IN_HOURS = 6.0


@register("track_history", interval_seconds=PLANNER_INTERVAL_SECONDS)
async def plan_track_history(db: AsyncSession) -> int:
    """Enqueue the stalest (track, platform) pairs up to BATCH_SIZE each."""
    enabled_specs = await _enabled_specs(db)
    if not enabled_specs:
        logger.info("[cm-planner-track-history] no enabled platforms — skipping")
        return 0

    total_enqueued = 0
    for spec, cfg in enabled_specs:
        enqueued = await _plan_for_platform(db, spec, cfg)
        total_enqueued += enqueued
    await db.commit()
    if total_enqueued:
        logger.info(
            "[cm-planner-track-history] enqueued %d jobs across %d platforms",
            total_enqueued, len(enabled_specs),
        )
    return total_enqueued


async def _enabled_specs(
    db: AsyncSession,
) -> list[tuple[dict[str, Any], ChartmetricEndpointConfig]]:
    """Join PLATFORM_SPECS against the DB config table and keep enabled rows."""
    keys = [s["endpoint_key"] for s in PLATFORM_SPECS]
    result = await db.execute(
        select(ChartmetricEndpointConfig).where(
            ChartmetricEndpointConfig.endpoint_key.in_(keys),
            ChartmetricEndpointConfig.enabled.is_(True),
        )
    )
    cfg_by_key = {row.endpoint_key: row for row in result.scalars()}
    out: list[tuple[dict[str, Any], ChartmetricEndpointConfig]] = []
    for spec in PLATFORM_SPECS:
        cfg = cfg_by_key.get(spec["endpoint_key"])
        if cfg is not None:
            out.append((spec, cfg))
    return out


async def _plan_for_platform(
    db: AsyncSession,
    spec: dict[str, Any],
    cfg: ChartmetricEndpointConfig,
) -> int:
    """Find the stalest tracks for this platform and enqueue them."""
    # One query per platform: join tracks to track_stat_history's latest
    # pulled_at for this specific platform, order by staleness (NULLs
    # first = never pulled = highest urgency), cap at BATCH_SIZE.
    sql = sa_text("""
        SELECT
            t.id::text AS track_id,
            t.chartmetric_id AS cm_id,
            MAX(h.pulled_at) AS last_pulled_at
        FROM tracks t
        LEFT JOIN track_stat_history h
            ON h.track_id = t.id AND h.platform = :platform
        WHERE t.chartmetric_id IS NOT NULL
        GROUP BY t.id, t.chartmetric_id
        ORDER BY MAX(h.pulled_at) NULLS FIRST, t.chartmetric_id
        LIMIT :limit
    """)
    result = await db.execute(
        sql,
        {"platform": spec["platform"], "limit": BATCH_SIZE_PER_PLATFORM},
    )
    rows = result.fetchall()
    if not rows:
        return 0

    enqueued = 0
    for row in rows:
        url = f"{API_BASE}/api/track/{int(row.cm_id)}/stat/{spec['platform']}"
        params = {"latest": "true"}
        freshness = freshness_score(
            row.last_pulled_at,
            cfg.target_interval_hours,
        )
        priority = priority_from_scores(
            freshness=freshness,
            importance=50.0,  # track importance signal goes here once we have one
            endpoint_weight=cfg.priority_weight,
        )
        job_id = await cmq_queue.enqueue(
            db,
            url=url,
            params=params,
            producer=PRODUCER_NAME,
            handler=HANDLER_NAME,
            priority=priority,
            handler_context={
                "track_id": row.track_id,
                "chartmetric_track_id": int(row.cm_id),
                "platform": spec["platform"],
            },
            expires_in_hours=JOB_EXPIRES_IN_HOURS,
        )
        if job_id is not None:
            enqueued += 1
    return enqueued
