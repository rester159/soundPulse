"""Unit tests for freshness_score and priority_from_scores.

These are the two pure functions planners rely on to translate
"how stale is this row?" into a queue-ready integer priority. Drift
here would silently break the whole prioritization system, so we
test the boundary conditions explicitly.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from chartmetric_ingest.priority import freshness_score, priority_from_scores


NOW = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)


def test_never_fetched_is_maximally_stale():
    assert freshness_score(None, 24.0, now=NOW) == 0.0


def test_fresh_is_near_100():
    last = NOW - timedelta(minutes=1)
    assert freshness_score(last, 24.0, now=NOW) > 99.0


def test_exactly_target_interval_hits_midpoint():
    last = NOW - timedelta(hours=24)
    assert freshness_score(last, 24.0, now=NOW) == pytest.approx(50.0)


def test_double_target_is_maximally_stale():
    last = NOW - timedelta(hours=48)
    assert freshness_score(last, 24.0, now=NOW) == 0.0


def test_past_double_target_clamps_at_zero():
    last = NOW - timedelta(days=30)
    assert freshness_score(last, 24.0, now=NOW) == 0.0


def test_naive_datetime_is_assumed_utc():
    last_naive = datetime(2026, 4, 13, 12, 0, 0)  # 24h before NOW
    assert freshness_score(last_naive, 24.0, now=NOW) == pytest.approx(50.0)


def test_target_interval_must_be_positive():
    with pytest.raises(ValueError):
        freshness_score(NOW, 0, now=NOW)
    with pytest.raises(ValueError):
        freshness_score(NOW, -1, now=NOW)


def test_priority_stale_and_important_becomes_urgent():
    # Maximally stale (freshness=0), high importance, neutral weight
    assert priority_from_scores(freshness=0.0, importance=100.0) == 0


def test_priority_fresh_and_important_is_low_urgency():
    # Fresh row never needs to be refetched regardless of importance
    assert priority_from_scores(freshness=100.0, importance=100.0) == 100


def test_priority_stale_but_unimportant_is_deprioritized():
    # Stale but importance=0 → should not displace other work
    assert priority_from_scores(freshness=0.0, importance=0.0) == 100


def test_priority_endpoint_weight_boosts_urgency():
    base = priority_from_scores(freshness=50.0, importance=50.0, endpoint_weight=1.0)
    boosted = priority_from_scores(freshness=50.0, importance=50.0, endpoint_weight=2.0)
    assert boosted < base  # lower = more urgent


def test_priority_clamps_into_0_100():
    # Absurd weights must not produce out-of-range priorities
    low = priority_from_scores(freshness=0.0, importance=100.0, endpoint_weight=100.0)
    high = priority_from_scores(freshness=100.0, importance=0.0, endpoint_weight=0.0)
    assert 0 <= low <= 100
    assert 0 <= high <= 100


def test_priority_default_importance_is_midpoint():
    # A planner without an importance signal should still produce
    # sensible monotonic output as freshness changes.
    stale = priority_from_scores(freshness=0.0)
    mid = priority_from_scores(freshness=50.0)
    fresh = priority_from_scores(freshness=100.0)
    assert stale < mid < fresh
