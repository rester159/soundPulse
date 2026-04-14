"""Artist stats planner — `/api/artist/{cm_id}/stat/{platform}?latest=true`.

Mirrors the track_history planner shape: for each (artist, platform)
pair where the artist has a chartmetric_id, compute freshness from
the generic `chartmetric_entity_fetch_log` and enqueue the stalest
BATCH_SIZE_PER_PLATFORM each run.

PLATFORM_SPECS here covers 6 platforms (spotify, instagram, tiktok,
youtube, twitter, shazam) — the full set Chartmetric exposes artist
stats on. Each row maps 1:1 to a chartmetric_endpoint_config row
for operator-tunable cadence/weight.
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


PLATFORM_SPECS: list[dict[str, Any]] = [
    {
        "endpoint_key": "artist_stat_spotify",
        "platform": "spotify",
        "metrics": ["followers", "monthly_listeners", "popularity"],
    },
    {
        "endpoint_key": "artist_stat_instagram",
        "platform": "instagram",
        "metrics": ["followers"],
    },
    {
        "endpoint_key": "artist_stat_tiktok",
        "platform": "tiktok",
        "metrics": ["followers", "likes"],
    },
    {
        "endpoint_key": "artist_stat_youtube",
        "platform": "youtube",
        "metrics": ["subscribers", "views"],
    },
    {
        "endpoint_key": "artist_stat_twitter",
        "platform": "twitter",
        "metrics": ["followers"],
    },
    {
        "endpoint_key": "artist_stat_shazam",
        "platform": "shazam",
        "metrics": ["shazams"],
    },
]


API_BASE = "https://api.chartmetric.com"
HANDLER_NAME = "artist_stats"
PRODUCER_NAME = "planner_artist_stats"
# Artist stats are secondary — smaller batch, longer cadence than
# track_history. The primary saturation source is track_history;
# artist_stats fills in remaining capacity when tracks run fresh.
PLANNER_INTERVAL_SECONDS = 300.0  # 5 minutes
BATCH_SIZE_PER_PLATFORM = 500
JOB_EXPIRES_IN_HOURS = 12.0


@register("artist_stats", interval_seconds=PLANNER_INTERVAL_SECONDS)
async def plan_artist_stats(db: AsyncSession) -> int:
    enabled = await _enabled_specs(db)
    if not enabled:
        logger.info("[cm-planner-artist-stats] no enabled platforms")
        return 0

    total = 0
    for spec, cfg in enabled:
        total += await _plan_for_platform(db, spec, cfg)
    await db.commit()
    if total:
        logger.info("[cm-planner-artist-stats] enqueued %d jobs", total)
    return total


async def _enabled_specs(
    db: AsyncSession,
) -> list[tuple[dict[str, Any], ChartmetricEndpointConfig]]:
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
    # Left-join artists against the generic fetch log to find the
    # stalest (artist, platform=endpoint_key) pairs. NULLs (never
    # fetched) come first so new artists are always top priority.
    sql = sa_text("""
        SELECT
            a.id::text AS artist_id,
            a.chartmetric_id AS cm_id,
            l.last_fetched_at AS last_fetched_at
        FROM artists a
        LEFT JOIN chartmetric_entity_fetch_log l
            ON l.entity_type = 'artist'
           AND l.entity_id = a.id
           AND l.endpoint_key = :endpoint_key
        WHERE a.chartmetric_id IS NOT NULL
        ORDER BY l.last_fetched_at NULLS FIRST, a.chartmetric_id
        LIMIT :limit
    """)
    result = await db.execute(
        sql,
        {
            "endpoint_key": spec["endpoint_key"],
            "limit": BATCH_SIZE_PER_PLATFORM,
        },
    )
    rows = result.fetchall()
    if not rows:
        return 0

    enqueued = 0
    for row in rows:
        url = f"{API_BASE}/api/artist/{int(row.cm_id)}/stat/{spec['platform']}"
        params = {"latest": "true"}
        freshness = freshness_score(
            row.last_fetched_at,
            cfg.target_interval_hours,
        )
        priority = priority_from_scores(
            freshness=freshness,
            importance=50.0,
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
                "artist_id": row.artist_id,
                "chartmetric_artist_id": int(row.cm_id),
                "platform": spec["platform"],
            },
            expires_in_hours=JOB_EXPIRES_IN_HOURS,
        )
        if job_id is not None:
            enqueued += 1
    return enqueued
