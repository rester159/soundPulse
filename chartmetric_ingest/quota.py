"""Global Chartmetric quota governor.

Single in-process token bucket (rate 1.8 req/s ≈ 90% of the 2 req/s
Chartmetric limit, small burst for jitter) wrapped in an adaptive
throttle that persists across fetcher restarts.

On a 429 response, the fetcher calls `on_429()` which:
  - sets the adaptive multiplier to 0.5 (half rate)
  - records `last_429_at` in the singleton quota_state row

The multiplier recovers linearly back to 1.0 over `RECOVERY_SECONDS`
from the last 429. Recovery is lazy — `acquire()` recomputes the
multiplier on each call and writes it back when it has drifted
meaningfully from the last persisted value.

`BASE_RATE` / `BURST` are module-level constants here because they're
properties of Chartmetric's API contract, not instance configuration.
If we ever move to a higher-quota plan we'll bump these or make them
config-driven — but that's a known-future change, not hypothetical
flexibility. The only runtime-tunable input to the rate limiter is
the adaptive multiplier.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from api.models.chartmetric_queue import ChartmetricQuotaState

logger = logging.getLogger(__name__)

# 75% of Chartmetric's documented 2 req/s ceiling. This is a per-second
# average — the bucket absorbs short bursts via BURST.
#
# We dropped from 1.8 (90%) to 1.5 (75%) after the 2026-04-15 saturation
# attempt showed 1.8 req/s immediately triggered 429s, which dragged the
# adaptive multiplier down to 0.5x — NET throughput ended up BELOW 1.0
# req/s. The 90% headline gave us 54% actual. 1.5 req/s gives a wider
# safety margin and avoids the throttle-bounce: with no 429s, effective
# throughput is 1.5 req/s × 86,400 s/day = 129,600 req/day = 75% of
# quota — a real 75% beats a theoretical 90% that adaptive-throttles to
# 54%. Once we verify this settles cleanly, we can tick back up to 1.65
# or 1.75 to recover some headroom.
BASE_RATE = 1.5
BURST = 5

# How much the multiplier drops on a 429 event.
THROTTLE_MULTIPLIER = 0.5

# Linear recovery window. At `RECOVERY_SECONDS` after the last 429 the
# multiplier has fully returned to 1.0.
RECOVERY_SECONDS = 600  # 10 minutes

# Only persist a multiplier change if it differs by at least this much
# from the last persisted value — avoids hammering the DB.
PERSIST_EPSILON = 0.05


class TokenBucket:
    """Asyncio-friendly token bucket. Single consumer per instance.

    Pure in-process — callers hold the `acquire()` contract across a
    single process. The fetcher is single-instance today (see Stage 3
    design doc); if we ever add multi-fetcher, we'd move the bucket
    behind a Postgres advisory lock or Redis.
    """

    def __init__(self, rate_per_sec: float, burst: int):
        if rate_per_sec <= 0:
            raise ValueError("rate_per_sec must be positive")
        if burst < 1:
            raise ValueError("burst must be >= 1")
        self._rate = float(rate_per_sec)
        self._burst = float(burst)
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed > 0:
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
            self._last_refill = now

    async def acquire(self, amount: float = 1.0) -> None:
        """Block until `amount` tokens are available, then consume them."""
        if amount <= 0:
            return
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= amount:
                    self._tokens -= amount
                    return
                deficit = amount - self._tokens
                wait_seconds = deficit / self._rate
            # Sleep outside the lock so other consumers (future) can see
            # refills, and so cancellation works.
            await asyncio.sleep(wait_seconds)

    def set_rate(self, rate_per_sec: float) -> None:
        """Change the refill rate. Callers hold no lock assumption."""
        if rate_per_sec <= 0:
            raise ValueError("rate_per_sec must be positive")
        # Refill at the old rate first so the bucket state reflects
        # time elapsed under the previous setting.
        self._refill()
        self._rate = float(rate_per_sec)

    @property
    def current_rate(self) -> float:
        return self._rate

    @property
    def available_tokens(self) -> float:
        self._refill()
        return self._tokens


def compute_multiplier(last_429_at: datetime | None, *, now: datetime | None = None) -> float:
    """Linear recovery from THROTTLE_MULTIPLIER to 1.0 over RECOVERY_SECONDS."""
    if last_429_at is None:
        return 1.0
    now = now or datetime.now(timezone.utc)
    if last_429_at.tzinfo is None:
        last_429_at = last_429_at.replace(tzinfo=timezone.utc)
    elapsed = (now - last_429_at).total_seconds()
    if elapsed <= 0:
        return THROTTLE_MULTIPLIER
    if elapsed >= RECOVERY_SECONDS:
        return 1.0
    # Linear interp from THROTTLE_MULTIPLIER at t=0 to 1.0 at t=RECOVERY_SECONDS
    fraction = elapsed / RECOVERY_SECONDS
    return THROTTLE_MULTIPLIER + (1.0 - THROTTLE_MULTIPLIER) * fraction


class ChartmetricQuota:
    """Bucket + persisted adaptive multiplier + on_429 hook."""

    def __init__(self, session_factory: async_sessionmaker):
        self._session_factory = session_factory
        self._bucket = TokenBucket(BASE_RATE, BURST)
        self._multiplier = 1.0
        self._last_429_at: datetime | None = None
        self._persisted_multiplier = 1.0

    async def load_state(self) -> None:
        """Read the singleton quota_state row and sync bucket rate."""
        async with self._session_factory() as db:
            row = (
                await db.execute(select(ChartmetricQuotaState).where(ChartmetricQuotaState.id == 1))
            ).scalar_one_or_none()
            if row is None:
                # Should have been seeded in migration 027. Be defensive.
                self._multiplier = 1.0
                self._last_429_at = None
            else:
                self._multiplier = float(row.adaptive_multiplier or 1.0)
                self._last_429_at = row.last_429_at
        self._persisted_multiplier = self._multiplier
        self._bucket.set_rate(BASE_RATE * self._multiplier)
        logger.info(
            "[cm-quota] loaded state: multiplier=%.2f rate=%.2f req/s last_429=%s",
            self._multiplier, self._bucket.current_rate, self._last_429_at,
        )

    async def acquire(self) -> None:
        """Recompute adaptive multiplier (lazy recovery) then block on bucket."""
        new_mult = compute_multiplier(self._last_429_at)
        if new_mult != self._multiplier:
            self._multiplier = new_mult
            self._bucket.set_rate(BASE_RATE * self._multiplier)
            if abs(self._multiplier - self._persisted_multiplier) >= PERSIST_EPSILON:
                await self._persist()
        await self._bucket.acquire()

    async def on_429(self) -> None:
        """Called by the fetcher when Chartmetric returns HTTP 429."""
        # Dedupe the log: only warn on the FIRST 429 after a recovery
        # window, not on every rate-limited request. A flood of 429s
        # during a burst produces one log line, not dozens.
        was_fresh = self._multiplier >= 1.0 - PERSIST_EPSILON
        if was_fresh:
            logger.warning(
                "[cm-quota] 429 observed — clamping to %.2fx base rate",
                THROTTLE_MULTIPLIER,
            )
        self._multiplier = THROTTLE_MULTIPLIER
        self._last_429_at = datetime.now(timezone.utc)
        self._bucket.set_rate(BASE_RATE * self._multiplier)
        await self._persist()

    async def _persist(self) -> None:
        async with self._session_factory() as db:
            await db.execute(
                update(ChartmetricQuotaState)
                .where(ChartmetricQuotaState.id == 1)
                .values(
                    adaptive_multiplier=self._multiplier,
                    last_429_at=self._last_429_at,
                )
            )
            await db.commit()
        self._persisted_multiplier = self._multiplier

    @property
    def current_rate(self) -> float:
        return self._bucket.current_rate

    @property
    def multiplier(self) -> float:
        return self._multiplier
