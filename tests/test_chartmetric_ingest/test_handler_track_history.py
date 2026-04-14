"""Tests for the track_history handler's pure extract_rows function.

Same territory as `tests/test_scrapers/test_chartmetric_track_history.py`
— we test the shape-handling rules (list vs dict, millis vs seconds
vs ISO, int vs float vs bool) — but this time against the new
handler's version. Keeping both test files is intentional until the
Stage 2B scraper is deleted in a future cycle.
"""
from __future__ import annotations

from chartmetric_ingest.handlers.track_history import extract_rows


def _body(**metric_series) -> dict:
    return {"obj": dict(metric_series)}


def test_parses_millis_list_point():
    body = _body(streams=[[1709251200000, 12345]])
    rows = extract_rows(
        body,
        track_id="t1",
        chartmetric_track_id=999,
        platform="spotify",
        metrics=["streams"],
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["snapshot_date"] == "2024-03-01"
    assert r["value"] == 12345
    assert r["value_float"] is None
    assert r["metric"] == "streams"
    assert r["platform"] == "spotify"
    assert r["track_id"] == "t1"
    assert r["chartmetric_track_id"] == 999


def test_parses_iso_string_points():
    body = _body(popularity=[["2025-06-15", 80], ["2025-06-16T00:00:00Z", 82]])
    rows = extract_rows(
        body, track_id="t1", chartmetric_track_id=1,
        platform="spotify", metrics=["popularity"],
    )
    assert [r["snapshot_date"] for r in rows] == ["2025-06-15", "2025-06-16"]
    assert [r["value"] for r in rows] == [80, 82]


def test_multiple_metrics_produce_multiple_rows():
    body = _body(
        streams=[[1709251200000, 100]],
        popularity=[[1709251200000, 50]],
    )
    rows = extract_rows(
        body, track_id="t1", chartmetric_track_id=1,
        platform="spotify", metrics=["streams", "popularity"],
    )
    assert len(rows) == 2
    metrics_out = {r["metric"] for r in rows}
    assert metrics_out == {"streams", "popularity"}


def test_unknown_metrics_ignored():
    body = _body(streams=[[1709251200000, 1]], garbage=[[1709251200000, 2]])
    rows = extract_rows(
        body, track_id="t1", chartmetric_track_id=1,
        platform="spotify", metrics=["streams"],
    )
    assert len(rows) == 1
    assert rows[0]["metric"] == "streams"


def test_missing_obj_returns_empty():
    assert extract_rows({}, track_id="t1", chartmetric_track_id=1,
                        platform="spotify", metrics=["streams"]) == []
    assert extract_rows({"obj": None}, track_id="t1", chartmetric_track_id=1,
                        platform="spotify", metrics=["streams"]) == []


def test_bool_value_rejected():
    body = _body(streams=[[1709251200000, True]])
    rows = extract_rows(
        body, track_id="t1", chartmetric_track_id=1,
        platform="spotify", metrics=["streams"],
    )
    assert rows == []


def test_float_integer_coerced():
    body = _body(streams=[[1709251200000, 42.0]])
    rows = extract_rows(
        body, track_id="t1", chartmetric_track_id=1,
        platform="spotify", metrics=["streams"],
    )
    assert rows[0]["value"] == 42
    assert rows[0]["value_float"] is None


def test_float_fractional_stored_as_float():
    body = _body(popularity=[[1709251200000, 0.5]])
    rows = extract_rows(
        body, track_id="t1", chartmetric_track_id=1,
        platform="spotify", metrics=["popularity"],
    )
    assert rows[0]["value"] is None
    assert rows[0]["value_float"] == 0.5


def test_max_points_clamps_long_series():
    points = [[1700000000 + i * 86400, i] for i in range(200)]
    body = _body(streams=points)
    rows = extract_rows(
        body, track_id="t1", chartmetric_track_id=1,
        platform="spotify", metrics=["streams"],
        max_points_per_series=30,
    )
    assert len(rows) == 30
    # Should be the LAST 30 points (most recent window)
    assert rows[0]["value"] == 170
    assert rows[-1]["value"] == 199


def test_dict_point_with_value_key():
    body = _body(streams=[{"timestamp": "2025-06-15", "value": 99}])
    rows = extract_rows(
        body, track_id="t1", chartmetric_track_id=1,
        platform="spotify", metrics=["streams"],
    )
    assert rows[0]["snapshot_date"] == "2025-06-15"
    assert rows[0]["value"] == 99
