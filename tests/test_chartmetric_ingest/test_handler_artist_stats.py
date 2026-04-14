"""Tests for the artist_stats handler's pure _extract_latest helper
plus registration sanity checks.
"""
from __future__ import annotations

from chartmetric_ingest.handlers.artist_stats import _extract_latest


def test_scalar_metric_passed_through():
    obj = {"followers": 1000, "monthly_listeners": 50000}
    out = _extract_latest(obj, ["followers", "monthly_listeners"])
    assert out == {"followers": 1000, "monthly_listeners": 50000}


def test_time_series_list_takes_last_value():
    obj = {"followers": [[1700000000, 900], [1700086400, 950], [1700172800, 1000]]}
    out = _extract_latest(obj, ["followers"])
    assert out == {"followers": 1000}


def test_dict_point_value_key():
    obj = {"followers": [{"ts": 1700172800, "value": 42}]}
    out = _extract_latest(obj, ["followers"])
    assert out == {"followers": 42}


def test_dict_wrapper_with_value_key():
    obj = {"followers": {"value": 777}}
    out = _extract_latest(obj, ["followers"])
    assert out == {"followers": 777}


def test_missing_metrics_not_included():
    obj = {"followers": 100}
    out = _extract_latest(obj, ["followers", "popularity"])
    assert out == {"followers": 100}
    assert "popularity" not in out


def test_bool_metric_rejected():
    # bool is a subtype of int — we don't want `True` showing up as a stat
    obj = {"followers": True}
    out = _extract_latest(obj, ["followers"])
    assert "followers" not in out


def test_empty_metric_list_returns_empty():
    obj = {"followers": 100}
    assert _extract_latest(obj, []) == {}


def test_handler_is_registered():
    from chartmetric_ingest import handlers as cmq_handlers
    assert cmq_handlers.get("artist_stats") is not None


def test_planner_is_registered():
    from chartmetric_ingest import planners as cmq_planners
    spec = cmq_planners.get("artist_stats")
    assert spec is not None
    assert spec.fn.__name__ == "plan_artist_stats"


def test_platform_specs_alignment():
    """Every PLATFORM_SPECS row must have a matching default endpoint config."""
    from chartmetric_ingest.endpoints import DEFAULT_ENDPOINT_CONFIGS
    from chartmetric_ingest.planners.artist_stats import PLATFORM_SPECS

    cfg_keys = {c["endpoint_key"] for c in DEFAULT_ENDPOINT_CONFIGS}
    for spec in PLATFORM_SPECS:
        assert spec["endpoint_key"] in cfg_keys, (
            f"endpoint_key {spec['endpoint_key']!r} has no default config"
        )


def test_track_history_specs_alignment():
    """Same check for the track_history planner."""
    from chartmetric_ingest.endpoints import DEFAULT_ENDPOINT_CONFIGS
    from chartmetric_ingest.planners.track_history import PLATFORM_SPECS

    cfg_keys = {c["endpoint_key"] for c in DEFAULT_ENDPOINT_CONFIGS}
    for spec in PLATFORM_SPECS:
        assert spec["endpoint_key"] in cfg_keys
