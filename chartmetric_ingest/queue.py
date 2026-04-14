"""Chartmetric request queue — enqueue / claim / complete.

All three operations are DB-native: dedup is enforced by the partial
unique index on `(dedup_key) WHERE completed_at IS NULL`, and claim is
a `SELECT ... FOR UPDATE SKIP LOCKED` so multiple fetchers could race
for work without duplicate dispatch if we ever add them. Single
fetcher is the current deployment.

Producers never hold a claim across the fetch, so claim rows don't
become stale if a planner is slow. Only the fetcher claims.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from api.models.chartmetric_queue import ChartmetricRequestQueue

logger = logging.getLogger(__name__)


@dataclass
class ClaimedJob:
    """Detached snapshot of a claimed queue row.

    We can't return the ORM instance after commit because the session
    expires it. Planners get exactly the fields they need.
    """
    id: int
    url: str
    params: dict[str, Any]
    producer: str
    handler: str
    handler_context: dict[str, Any]
    attempt_count: int


def dedup_key_for(url: str, params: dict[str, Any] | None) -> str:
    """Deterministic short hash over (url, sorted(params)).

    Used by the partial unique index to coalesce identical pending
    jobs. Not cryptographic — just a stable fingerprint.
    """
    canonical = url + "?" + json.dumps(params or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


async def enqueue(
    db: AsyncSession,
    *,
    url: str,
    params: dict[str, Any] | None = None,
    producer: str,
    handler: str,
    priority: int,
    handler_context: dict[str, Any] | None = None,
    expires_in_hours: float = 24.0,
) -> int | None:
    """Insert a job or merge into an existing pending one.

    Returns the row id of the pending job after the operation (whether
    newly inserted or merged). Returns None only if the DB rejects the
    insert for a reason other than the pending-dedup conflict — which
    callers should treat as a bug, not a normal path.

    Merge semantics on dedup hit:
      - priority becomes LEAST(old, new) so re-emits can only raise
        urgency, never lower it
      - expires_at becomes GREATEST(old, new) so re-emits extend the
        deadline

    The caller owns the transaction — we do not commit here. This
    lets planners batch many enqueues in a single DB transaction.
    """
    params = params or {}
    handler_context = handler_context or {}
    priority = max(0, min(100, int(priority)))
    dedup_key = dedup_key_for(url, params)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

    stmt = pg_insert(ChartmetricRequestQueue).values(
        dedup_key=dedup_key,
        priority=priority,
        url=url,
        params=params,
        producer=producer,
        handler=handler,
        handler_context=handler_context,
        expires_at=expires_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["dedup_key"],
        index_where=ChartmetricRequestQueue.completed_at.is_(None),
        set_={
            "priority": func.least(
                stmt.excluded.priority,
                ChartmetricRequestQueue.priority,
            ),
            "expires_at": func.greatest(
                stmt.excluded.expires_at,
                ChartmetricRequestQueue.expires_at,
            ),
        },
    ).returning(ChartmetricRequestQueue.id)

    result = await db.execute(stmt)
    row = result.first()
    return int(row[0]) if row else None


async def claim_next(db: AsyncSession) -> ClaimedJob | None:
    """Atomically claim the highest-priority ready job.

    Uses `SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1` so the claim is
    race-free against any other fetcher instance. On success, stamps
    `started_at` + bumps `attempt_count` and commits.

    A job is "ready" when completed_at IS NULL AND started_at IS NULL
    AND (expires_at IS NULL OR expires_at > now()).
    """
    stmt = (
        select(ChartmetricRequestQueue)
        .where(
            ChartmetricRequestQueue.completed_at.is_(None),
            ChartmetricRequestQueue.started_at.is_(None),
            or_(
                ChartmetricRequestQueue.expires_at.is_(None),
                ChartmetricRequestQueue.expires_at > func.now(),
            ),
        )
        .order_by(
            ChartmetricRequestQueue.priority.asc(),
            ChartmetricRequestQueue.created_at.asc(),
        )
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None

    row.started_at = datetime.now(timezone.utc)
    row.attempt_count = (row.attempt_count or 0) + 1

    claimed = ClaimedJob(
        id=int(row.id),
        url=row.url,
        params=dict(row.params or {}),
        producer=row.producer,
        handler=row.handler,
        handler_context=dict(row.handler_context or {}),
        attempt_count=int(row.attempt_count),
    )
    await db.commit()
    return claimed


async def complete(
    db: AsyncSession,
    job_id: int,
    *,
    status: int | None,
    error: str | None = None,
) -> None:
    """Mark a claimed job terminal. Called by the fetcher regardless of success.

    Success path passes the HTTP status and no error. Failure passes
    the HTTP status (or None on transport failure) and an error
    string. Either way the pending-dedup index releases so a future
    planner cycle can re-emit.
    """
    await db.execute(
        update(ChartmetricRequestQueue)
        .where(ChartmetricRequestQueue.id == job_id)
        .values(
            completed_at=func.now(),
            response_status=status,
            last_error=(error or "")[:2000] if error else None,
        )
    )
    await db.commit()


async def release_stuck(
    db: AsyncSession,
    *,
    older_than_minutes: int = 10,
) -> int:
    """Un-claim jobs whose fetcher died mid-request.

    A job that's been `started_at` for more than `older_than_minutes`
    without completing is almost certainly abandoned — the fetcher
    crashed or the container was replaced. Reset `started_at` so the
    next claim picks it up. Bumped `attempt_count` survives so we can
    still walk off permanently broken jobs.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
    result = await db.execute(
        update(ChartmetricRequestQueue)
        .where(
            ChartmetricRequestQueue.completed_at.is_(None),
            ChartmetricRequestQueue.started_at.is_not(None),
            ChartmetricRequestQueue.started_at < cutoff,
        )
        .values(started_at=None)
    )
    await db.commit()
    return int(result.rowcount or 0)
