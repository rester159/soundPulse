"""
Cross-replica Chartmetric token bucket (task #8 / Phase B fix for L016
multi-replica fan-out).

Single-row Postgres-coordinated token bucket. Each fetcher (regardless
of which Railway replica it runs on) calls `acquire()` before dispatch;
the SELECT ... FOR UPDATE in the acquire loop serializes the bucket
update, so the combined dispatch rate is strictly bounded by
`rate_per_sec` no matter how many replicas are running.

Composition with the in-process bucket: the global bucket is the
authoritative budget. The in-process bucket (chartmetric_ingest.quota.
ChartmetricQuota -> TokenBucket) stays as a defense-in-depth layer that
also handles the on_429 adaptive multiplier per-replica. Order of
operations in ChartmetricQuota.acquire() is now:
  1. await global_bucket.acquire(db_factory)   # cross-replica budget
  2. await self._bucket.acquire()              # in-process backstop +
                                                  adaptive multiplier
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)


# Polling fallback: if the SELECT FOR UPDATE somehow returns a token
# count that's too low to consume but the computed wait is implausibly
# small (clock skew, etc), cap the sleep at this value so we don't
# tight-loop or sleep forever.
MIN_RETRY_SECONDS = 0.05
MAX_RETRY_SECONDS = 5.0


class GlobalChartmetricBucket:
    """Postgres-backed token bucket. Stateless — every acquire() opens
    its own session. Safe to share across coroutines and across replicas.
    """

    def __init__(self, session_factory: async_sessionmaker):
        self._session_factory = session_factory

    async def acquire(self, *, amount: float = 1.0) -> None:
        """Block until `amount` tokens are available globally, then
        consume them. Wait happens OUTSIDE the DB lock so other
        consumers can make progress.
        """
        if amount <= 0:
            return
        while True:
            wait_seconds = await self._try_consume(amount)
            if wait_seconds is None:
                return  # consumed
            sleep_for = max(MIN_RETRY_SECONDS, min(MAX_RETRY_SECONDS, wait_seconds))
            await asyncio.sleep(sleep_for)

    async def _try_consume(self, amount: float) -> float | None:
        """Single attempt: if tokens available, consume and return None.
        Otherwise return seconds to wait before retrying.

        Held lock window is ONE DB roundtrip + a tiny computation. The
        caller does the actual sleep outside this method, so other
        replicas / coroutines can advance during the wait.
        """
        async with self._session_factory() as db:
            row = (await db.execute(
                text(
                    "SELECT tokens, last_refill_at, rate_per_sec, burst "
                    "FROM chartmetric_global_bucket WHERE id = 1 FOR UPDATE"
                )
            )).one_or_none()
            if row is None:
                # Migration 035 didn't run — fail loud rather than
                # silently dispatching at unbounded rate.
                raise RuntimeError(
                    "chartmetric_global_bucket has no row id=1 — "
                    "migration 035 did not run"
                )
            tokens = float(row.tokens)
            last_refill_at: datetime = row.last_refill_at
            rate = float(row.rate_per_sec)
            burst = float(row.burst)

            now = datetime.now(timezone.utc)
            if last_refill_at.tzinfo is None:
                last_refill_at = last_refill_at.replace(tzinfo=timezone.utc)
            elapsed = max(0.0, (now - last_refill_at).total_seconds())
            new_tokens = min(burst, tokens + elapsed * rate)

            if new_tokens >= amount:
                # Consume + persist. Always update last_refill_at to now
                # so a future caller sees the most-recent refill anchor.
                # clock_timestamp() (real wall time) for updated_at;
                # NOW() returns transaction-start which would mis-record
                # under high-concurrency single-replica testing.
                await db.execute(
                    text(
                        "UPDATE chartmetric_global_bucket "
                        "SET tokens = :t, last_refill_at = :n, "
                        "    updated_at = clock_timestamp() "
                        "WHERE id = 1"
                    ),
                    {"t": new_tokens - amount, "n": now},
                )
                await db.commit()
                return None

            # Not enough tokens. Persist the refill (so we don't keep
            # recomputing the same elapsed window on retry) and release
            # the lock by committing. Compute how long until enough
            # tokens will be available at the current rate.
            await db.execute(
                text(
                    "UPDATE chartmetric_global_bucket "
                    "SET tokens = :t, last_refill_at = :n, "
                    "    updated_at = clock_timestamp() "
                    "WHERE id = 1"
                ),
                {"t": new_tokens, "n": now},
            )
            await db.commit()
            deficit = amount - new_tokens
            return deficit / rate

    async def set_rate(self, rate_per_sec: float, *, burst: float | None = None) -> None:
        """Change the cross-replica rate (and optionally burst). Used by
        on_429 paths or operator overrides. Holds the FOR UPDATE lock
        for one roundtrip."""
        if rate_per_sec <= 0:
            raise ValueError("rate_per_sec must be positive")
        async with self._session_factory() as db:
            params = {"r": float(rate_per_sec)}
            if burst is not None:
                if burst <= 0:
                    raise ValueError("burst must be positive")
                params["b"] = float(burst)
                sql = (
                    "UPDATE chartmetric_global_bucket "
                    "SET rate_per_sec = :r, burst = :b, updated_at = clock_timestamp() "
                    "WHERE id = 1"
                )
            else:
                sql = (
                    "UPDATE chartmetric_global_bucket "
                    "SET rate_per_sec = :r, updated_at = clock_timestamp() "
                    "WHERE id = 1"
                )
            await db.execute(text(sql), params)
            await db.commit()

    async def drain(self) -> None:
        """Zero global tokens. Mirrors TokenBucket.drain() so an on_429
        clamp at one replica can stop other replicas from immediately
        dispatching their own queued requests.

        clock_timestamp() (real wall time) is used here, not NOW(), so a
        subsequent acquire() doesn't see a huge synthetic refill window
        accrued from transaction-start time. The bucket's elapsed-time
        math always compares Python's datetime.now() (wall clock) to the
        DB-recorded last_refill_at, so both ends must use real time."""
        async with self._session_factory() as db:
            await db.execute(
                text(
                    "UPDATE chartmetric_global_bucket "
                    "SET tokens = 0, last_refill_at = clock_timestamp(), "
                    "    updated_at = clock_timestamp() "
                    "WHERE id = 1"
                )
            )
            await db.commit()

    async def snapshot(self) -> dict:
        """Read-only view of the current bucket state. For tests +
        admin diagnostics."""
        async with self._session_factory() as db:
            row = (await db.execute(
                text(
                    "SELECT tokens, last_refill_at, rate_per_sec, burst "
                    "FROM chartmetric_global_bucket WHERE id = 1"
                )
            )).one_or_none()
            if row is None:
                raise RuntimeError("chartmetric_global_bucket missing row id=1")
            return {
                "tokens": float(row.tokens),
                "last_refill_at": row.last_refill_at,
                "rate_per_sec": float(row.rate_per_sec),
                "burst": float(row.burst),
            }
