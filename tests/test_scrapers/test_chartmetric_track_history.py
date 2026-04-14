"""Unit tests for ChartmetricTrackHistoryScraper row transform.

These cover the pure-Python normalization in `_point_to_row` /
`_normalize_date` — the part with non-obvious shape-handling logic.
Network/IO paths are not covered here; those are exercised by the
integration suite.
"""
from __future__ import annotations

from scrapers.chartmetric_track_history import ChartmetricTrackHistoryScraper


def _row(**overrides):
    base = {
        "point": [1709251200000, 12345],  # 2024-03-01 in millis
        "db_uuid": "00000000-0000-0000-0000-000000000001",
        "cm_id": 999,
        "platform": "spotify",
        "metric": "streams",
    }
    base.update(overrides)
    return ChartmetricTrackHistoryScraper._point_to_row(**base)


def test_accepts_millis_list_form_with_int_value():
    row = _row()
    assert row is not None
    assert row["snapshot_date"] == "2024-03-01"
    assert row["value"] == 12345
    assert row["value_float"] is None
    assert row["platform"] == "spotify"
    assert row["metric"] == "streams"
    assert row["chartmetric_track_id"] == 999


def test_accepts_seconds_list_form():
    row = _row(point=[1709251200, 42])
    assert row is not None
    assert row["snapshot_date"] == "2024-03-01"
    assert row["value"] == 42


def test_accepts_iso_string_timestamp():
    row = _row(point=["2025-06-15T00:00:00Z", 7])
    assert row["snapshot_date"] == "2025-06-15"
    assert row["value"] == 7


def test_accepts_plain_date_string():
    row = _row(point=["2025-06-15", 7])
    assert row["snapshot_date"] == "2025-06-15"


def test_accepts_dict_point_with_value_key():
    row = _row(point={"timestamp": "2025-06-15", "value": 3})
    assert row["snapshot_date"] == "2025-06-15"
    assert row["value"] == 3


def test_float_value_stored_as_float():
    row = _row(point=[1709251200000, 0.25])
    assert row["value"] is None
    assert row["value_float"] == 0.25


def test_integer_float_coerced_to_int():
    row = _row(point=[1709251200000, 100.0])
    assert row["value"] == 100
    assert row["value_float"] is None


def test_boolean_value_rejected():
    # Avoid Python's bool-is-int trap — no sensible metric is a bool.
    row = _row(point=[1709251200000, True])
    assert row is None


def test_missing_timestamp_rejected():
    row = _row(point=[None, 5])
    assert row is None


def test_malformed_point_rejected():
    row = _row(point="garbage")
    assert row is None


def test_short_list_rejected():
    row = _row(point=[1709251200000])
    assert row is None
