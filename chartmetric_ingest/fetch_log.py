"""Helpers for `chartmetric_entity_fetch_log` — write, read, and stale-query.

The fetch log is the generic "when was this entity last fetched via
this endpoint?" tracker used by planners that can't read freshness
from a data table (e.g. artist_stats writes into JSONB, not a
time-series). Handlers upsert on successful parse; planners left-
join to find stale rows.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.chartmetric_queue import ChartmetricEntityFetchLog


async def mark_fetched(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: str | uuid.UUID,
    endpoint_key: str,
    status: int | None = 200,
) -> None:
    """Upsert the fetch-log row. Caller owns the transaction/commit."""
    if isinstance(entity_id, str):
        entity_id = uuid.UUID(entity_id)
    stmt = pg_insert(ChartmetricEntityFetchLog).values(
        entity_type=entity_type,
        entity_id=entity_id,
        endpoint_key=endpoint_key,
        last_fetched_at=datetime.now(timezone.utc),
        last_status=status,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="pk_cm_entity_fetch_log",
        set_={
            "last_fetched_at": stmt.excluded.last_fetched_at,
            "last_status": stmt.excluded.last_status,
        },
    )
    await db.execute(stmt)
