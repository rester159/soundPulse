"""
Cross-replica Chartmetric global bucket tests (task #8, migration 035).

The bucket is Postgres-backed via SELECT ... FOR UPDATE on a single-row
table, so its concurrency safety is inherited from Postgres. These tests
verify the per-call math: snapshot/consume/refill/drain/set_rate and
the wait-when-empty timing.
"""
from __future__ import annotations

import asyncio
import time

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from chartmetric_ingest.global_bucket import GlobalChartmetricBucket


@pytest.fixture
async def reset_global_bucket(db_session):
    """Force the bucket back to a known state before each test. The
    db_session fixture rolls back at end-of-test, so this only affects
    the current test's transaction. Uses a session_factory wrapper that
    yields the same rolled-back session — sufficient because every test
    here exercises the bucket within one transaction window.

    Important: NOW() in Postgres returns transaction-start time, which
    inside a single test transaction is fixed at the time the conftest
    opened the connection. That can be many seconds before the actual
    test body runs, which would make the bucket's elapsed-time math see
    a huge synthetic refill. clock_timestamp() returns real wall-clock
    time per statement, matching what the bucket's Python-side
    datetime.now() will compute."""
    await db_session.execute(text(
        "UPDATE chartmetric_global_bucket "
        "SET tokens = 1.0, rate_per_sec = 1.0, burst = 1.0, "
        "    last_refill_at = clock_timestamp() WHERE id = 1"
    ))
    await db_session.flush()
    yield


def _factory_yielding(session):
    """Build an async_sessionmaker-shaped object that always yields the
    given AsyncSession. Lets the bucket use its own async-context-manager
    pattern (`async with session_factory() as db: ...`) without spinning
    up new sessions, so all writes land in the test's single rolled-back
    transaction."""
    class _Stub:
        def __call__(self):
            return _Ctx(session)
    class _Ctx:
        def __init__(self, s):
            self._s = s
        async def __aenter__(self):
            return self._s
        async def __aexit__(self, exc_type, exc, tb):
            return False
    return _Stub()


# --- snapshot / acquire / drain -------------------------------------------

@pytest.mark.asyncio
async def test_snapshot_returns_seeded_state(db_session, reset_global_bucket):
    bucket = GlobalChartmetricBucket(_factory_yielding(db_session))
    snap = await bucket.snapshot()
    assert snap["tokens"] == pytest.approx(1.0)
    assert snap["rate_per_sec"] == pytest.approx(1.0)
    assert snap["burst"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_acquire_consumes_one_token_when_available(db_session, reset_global_bucket):
    bucket = GlobalChartmetricBucket(_factory_yielding(db_session))
    start = time.monotonic()
    await bucket.acquire()
    elapsed = time.monotonic() - start
    # First acquire should be immediate (1 token available)
    assert elapsed < 0.2, f"first acquire took {elapsed:.3f}s, expected immediate"
    snap = await bucket.snapshot()
    # Token consumed - allow a sliver of refill from elapsed time
    assert snap["tokens"] < 0.5


@pytest.mark.asyncio
async def test_acquire_waits_when_drained(db_session, reset_global_bucket):
    """Drain the bucket; next acquire must wait ~1/rate seconds for a
    refill before consuming."""
    bucket = GlobalChartmetricBucket(_factory_yielding(db_session))
    await bucket.drain()
    snap_after_drain = await bucket.snapshot()
    assert snap_after_drain["tokens"] == pytest.approx(0.0, abs=0.05)

    start = time.monotonic()
    await bucket.acquire()
    elapsed = time.monotonic() - start
    # At rate=1.0/s, refilling 1 token theoretically takes 1.0s, but the
    # bucket's "elapsed-since-last-refill" math counts time accrued
    # between drain() and the first SELECT FOR UPDATE inside acquire()
    # against the wait. With Neon roundtrip latency in the 100-300ms
    # range, that pre-loop accrual can shave ~0.3-0.5s off the total
    # wait. The point of this test is to prove we waited at all (without
    # drain it would be ~0ms), not that we waited exactly 1s. Floor of
    # 0.3s is still 6x what an unblocked acquire takes.
    assert 0.3 <= elapsed <= 2.5, (
        f"drained-then-acquire took {elapsed:.3f}s, expected real wait (>=0.3s)"
    )


@pytest.mark.asyncio
async def test_drain_zeros_tokens(db_session, reset_global_bucket):
    bucket = GlobalChartmetricBucket(_factory_yielding(db_session))
    await bucket.drain()
    snap = await bucket.snapshot()
    assert snap["tokens"] == pytest.approx(0.0, abs=0.05)


# --- set_rate -------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_rate_persists(db_session, reset_global_bucket):
    bucket = GlobalChartmetricBucket(_factory_yielding(db_session))
    await bucket.set_rate(0.5)
    snap = await bucket.snapshot()
    assert snap["rate_per_sec"] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_set_rate_with_burst(db_session, reset_global_bucket):
    bucket = GlobalChartmetricBucket(_factory_yielding(db_session))
    await bucket.set_rate(2.0, burst=3.0)
    snap = await bucket.snapshot()
    assert snap["rate_per_sec"] == pytest.approx(2.0)
    assert snap["burst"] == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_set_rate_rejects_zero(db_session, reset_global_bucket):
    bucket = GlobalChartmetricBucket(_factory_yielding(db_session))
    with pytest.raises(ValueError, match="positive"):
        await bucket.set_rate(0.0)


# --- regression guards ----------------------------------------------------

@pytest.mark.asyncio
async def test_acquire_amount_zero_returns_immediately(db_session, reset_global_bucket):
    """Cheap exit so callers can pass amount=0 as a no-op without
    paying a DB roundtrip. Avoids surprises in conditional acquire
    paths."""
    bucket = GlobalChartmetricBucket(_factory_yielding(db_session))
    start = time.monotonic()
    await bucket.acquire(amount=0)
    elapsed = time.monotonic() - start
    assert elapsed < 0.05


@pytest.mark.asyncio
async def test_singleton_check_constraint_blocks_second_row(db_session, reset_global_bucket):
    """Defense-in-depth: ck_chartmetric_global_bucket_singleton stops
    anyone from accidentally creating a second budget row that would
    silently split the global rate limit."""
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        await db_session.execute(text(
            "INSERT INTO chartmetric_global_bucket "
            "(id, tokens, rate_per_sec, burst) "
            "VALUES (2, 1.0, 1.0, 1.0)"
        ))
        await db_session.flush()


@pytest.mark.asyncio
async def test_positive_check_constraint_blocks_negative_rate(db_session, reset_global_bucket):
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        await db_session.execute(text(
            "UPDATE chartmetric_global_bucket SET rate_per_sec = -1 WHERE id = 1"
        ))
        await db_session.flush()
