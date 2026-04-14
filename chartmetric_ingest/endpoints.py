"""Default endpoint config — seeded on every boot, idempotent.

These are the `chartmetric_endpoint_config` rows the planners expect
to exist. On startup the runner calls `seed_endpoint_configs` which
does INSERT ... ON CONFLICT DO NOTHING so operator edits to
`target_interval_hours` / `priority_weight` / `enabled` are never
clobbered — only new keys are added.

Adding a new endpoint type is a three-step edit:
  1. Append a row here
  2. Write a planner (chartmetric_ingest/planners/<name>.py)
  3. Write a handler (chartmetric_ingest/handlers/<name>.py)

No schema migration. No scheduler wiring. The runner picks up the
new planner automatically via the PLANNER_REGISTRY bootstrap.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.chartmetric_queue import ChartmetricEndpointConfig

logger = logging.getLogger(__name__)


DEFAULT_ENDPOINT_CONFIGS: list[dict[str, Any]] = [
    # Per-track daily time-series from /api/track/{cm_id}/stat/{platform}.
    # target_interval_hours = how often we want each track refreshed.
    # Three rows, one per platform the handler parses.
    {
        "endpoint_key": "track_stat_spotify",
        "target_interval_hours": 24.0,
        "priority_weight": 1.0,
        "notes": "Per-track Spotify streams/popularity/playlist_reach",
    },
    {
        "endpoint_key": "track_stat_tiktok",
        "target_interval_hours": 24.0,
        "priority_weight": 1.0,
        "notes": "Per-track TikTok video_count/view_count",
    },
    {
        "endpoint_key": "track_stat_shazam",
        "target_interval_hours": 24.0,
        "priority_weight": 0.8,
        "notes": "Per-track Shazam count (lower weight)",
    },
]


async def seed_endpoint_configs(db: AsyncSession) -> int:
    """Upsert defaults; existing rows keep operator overrides.

    Returns the count of rows newly inserted.
    """
    if not DEFAULT_ENDPOINT_CONFIGS:
        return 0

    existing = await db.execute(select(ChartmetricEndpointConfig.endpoint_key))
    existing_keys = {row[0] for row in existing.all()}
    to_insert = [c for c in DEFAULT_ENDPOINT_CONFIGS if c["endpoint_key"] not in existing_keys]
    if not to_insert:
        return 0

    stmt = (
        pg_insert(ChartmetricEndpointConfig)
        .values(to_insert)
        .on_conflict_do_nothing(index_elements=["endpoint_key"])
    )
    await db.execute(stmt)
    await db.commit()
    logger.info(
        "[cm-endpoints] seeded %d new endpoint configs: %s",
        len(to_insert),
        [c["endpoint_key"] for c in to_insert],
    )
    return len(to_insert)
