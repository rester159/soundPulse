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
