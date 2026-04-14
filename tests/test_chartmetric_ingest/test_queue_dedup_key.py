"""Unit tests for the pure dedup_key_for helper.

The rest of queue.py needs a DB — that's covered by the integration
tests which run against Postgres in CI. This file covers the
canonicalization rules that stop the partial unique index from
fragmenting over semantically-identical jobs.
"""
from __future__ import annotations

from chartmetric_ingest.queue import dedup_key_for


def test_same_url_same_params_same_key():
    a = dedup_key_for("https://api.chartmetric.com/api/track/1/stat/spotify", {"since": "2026-01-01"})
    b = dedup_key_for("https://api.chartmetric.com/api/track/1/stat/spotify", {"since": "2026-01-01"})
    assert a == b


def test_param_order_does_not_matter():
    a = dedup_key_for("u", {"a": 1, "b": 2})
    b = dedup_key_for("u", {"b": 2, "a": 1})
    assert a == b


def test_different_params_differ():
    a = dedup_key_for("u", {"a": 1})
    b = dedup_key_for("u", {"a": 2})
    assert a != b


def test_different_urls_differ():
    a = dedup_key_for("u1", {"a": 1})
    b = dedup_key_for("u2", {"a": 1})
    assert a != b


def test_none_params_equals_empty_dict():
    assert dedup_key_for("u", None) == dedup_key_for("u", {})


def test_key_is_stable_short_hex():
    k = dedup_key_for("u", {"a": 1})
    assert len(k) == 32
    assert all(c in "0123456789abcdef" for c in k)
