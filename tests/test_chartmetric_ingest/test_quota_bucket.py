"""Token-bucket tests — steady-state rate + adaptive recovery.

We don't test the persisted ChartmetricQuota wrapper here because
that needs a DB. The pure TokenBucket and the compute_multiplier
recovery curve are both exercised without any I/O.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone

import pytest

from chartmetric_ingest.quota import (
    BASE_RATE,
    BURST,
    RECOVERY_SECONDS,
    THROTTLE_MULTIPLIER,
    TokenBucket,
    compute_multiplier,
)


@pytest.mark.asyncio
async def test_burst_capacity_allows_immediate_consumption():
    b = TokenBucket(rate_per_sec=2.0, burst=5)
    start = time.monotonic()
    for _ in range(5):
        await b.acquire()
    elapsed = time.monotonic() - start
    # All 5 should come out of the burst, nearly instantly
    assert elapsed < 0.1


@pytest.mark.asyncio
async def test_steady_state_rate_enforced_after_burst():
    b = TokenBucket(rate_per_sec=10.0, burst=2)
    # Drain the burst
    await b.acquire()
    await b.acquire()
    # Now the bucket is empty — next 3 should take ~0.3s (3 × 0.1s)
    start = time.monotonic()
    for _ in range(3):
        await b.acquire()
    elapsed = time.monotonic() - start
    # Allow generous slack — Windows asyncio schedulers are noisy
    assert 0.2 <= elapsed <= 0.6


@pytest.mark.asyncio
async def test_set_rate_changes_refill_speed():
    b = TokenBucket(rate_per_sec=1.0, burst=1)
    await b.acquire()  # drain
    b.set_rate(100.0)  # much faster refill
    start = time.monotonic()
    await b.acquire()
    elapsed = time.monotonic() - start
    assert elapsed < 0.1  # refilled fast


def test_invalid_rate_rejected():
    with pytest.raises(ValueError):
        TokenBucket(rate_per_sec=0, burst=1)
    with pytest.raises(ValueError):
        TokenBucket(rate_per_sec=-1, burst=1)


def test_invalid_burst_rejected():
    with pytest.raises(ValueError):
        TokenBucket(rate_per_sec=1.0, burst=0)


def test_compute_multiplier_none_returns_one():
    assert compute_multiplier(None) == 1.0


def test_compute_multiplier_at_moment_of_429_is_throttled():
    now = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)
    assert compute_multiplier(now, now=now) == THROTTLE_MULTIPLIER


def test_compute_multiplier_midway_through_recovery():
    now = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)
    halfway = now - timedelta(seconds=RECOVERY_SECONDS / 2)
    expected = THROTTLE_MULTIPLIER + (1.0 - THROTTLE_MULTIPLIER) * 0.5
    assert compute_multiplier(halfway, now=now) == pytest.approx(expected)


def test_compute_multiplier_after_recovery_is_one():
    now = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)
    long_ago = now - timedelta(seconds=RECOVERY_SECONDS * 2)
    assert compute_multiplier(long_ago, now=now) == 1.0


def test_compute_multiplier_naive_datetime_assumed_utc():
    now = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)
    naive = datetime(2026, 4, 14, 12, 0, 0)  # same instant, naive
    assert compute_multiplier(naive, now=now) == THROTTLE_MULTIPLIER


# --- Phase A fix for L004 microburst storm (2026-04-15) -------------------
# Live data showed sub-100ms gaps between requests at sustained 0.5 req/s
# average — bucket was bursting up to 3 tokens immediately after an on_429
# clamp because old tokens survived the rate change. Two guards:
#   1. BURST must be 1 — no microbursts allowed at the in-process layer.
#   2. drain() must zero remaining tokens so an on_429 clamp actually
#      stops dispatch instead of leaking 3 stale requests.

def test_module_burst_is_one():
    """Regression guard: BURST > 1 reintroduces microbursts that
    Chartmetric's per-burst enforcement 429s. See L004 in lessons.md."""
    assert BURST == 1, (
        "BURST must stay at 1 — bumping it back to 3 was the L004 microburst "
        "anti-pattern that produced the 50% 429 storm on 2026-04-15. "
        "If you're tempted to raise this, read planning/lessons.md L004 first."
    )


@pytest.mark.asyncio
async def test_drain_empties_bucket():
    """drain() zeroes available tokens so an on_429 clamp actually
    stops the next dispatch instead of leaking burst tokens."""
    b = TokenBucket(rate_per_sec=10.0, burst=3)
    # Bucket starts full (3 tokens).
    assert b.available_tokens == pytest.approx(3.0, abs=0.01)
    b.drain()
    assert b.available_tokens == pytest.approx(0.0, abs=0.01)


@pytest.mark.asyncio
async def test_drain_then_acquire_waits_full_refill_interval():
    """After drain(), the next acquire must wait the full 1/rate
    interval — no leftover tokens. This simulates the on_429 contract."""
    b = TokenBucket(rate_per_sec=2.0, burst=3)
    # Pre-fill the bucket to its burst capacity, then drain to simulate
    # the post-429 state.
    b.drain()
    start = time.monotonic()
    await b.acquire()
    elapsed = time.monotonic() - start
    # 1 / 2.0 = 0.5s minimum wait; allow generous Windows scheduler slack.
    assert 0.4 <= elapsed <= 0.8, (
        f"expected ~0.5s wait after drain at rate=2.0, got {elapsed:.3f}s"
    )
