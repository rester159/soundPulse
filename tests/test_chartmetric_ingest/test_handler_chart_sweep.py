"""Unit tests for the chart_sweep handler's pure shape-walk helpers
plus the planner/handler bootstrap sanity checks.
"""
from __future__ import annotations

from datetime import date

from chartmetric_ingest.handlers.chart_sweep import (
    _build_trending_records,
    _extract_items,
)


def test_extract_top_level_list():
    body = [{"name": "Song A"}, {"name": "Song B"}]
    assert _extract_items(body) == body


def test_extract_obj_list():
    body = {"obj": [{"name": "Song A"}]}
    assert _extract_items(body) == [{"name": "Song A"}]


def test_extract_obj_data():
    body = {"obj": {"data": [{"name": "Song A"}, {"name": "Song B"}]}}
    assert _extract_items(body) == [{"name": "Song A"}, {"name": "Song B"}]


def test_extract_obj_tracks():
    body = {"obj": {"tracks": [{"name": "Song A"}]}}
    assert _extract_items(body) == [{"name": "Song A"}]


def test_extract_platform_nested():
    body = {"obj": {"spotify": [{"name": "Song A"}]}}
    assert _extract_items(body) == [{"name": "Song A"}]


def test_extract_empty_shapes_return_empty():
    assert _extract_items({}) == []
    assert _extract_items({"obj": None}) == []
    assert _extract_items({"obj": {}}) == []
    assert _extract_items(None) == []
    assert _extract_items("garbage") == []


def test_build_trending_records_picks_up_common_fields():
    items = [
        {
            "name": "Song A",
            "artist_name": "Artist A",
            "spotify_track_id": "abc123",
            "isrc": "USRC12345678",
            "rank": 1,
            "cm_track": 99,
        },
        {
            "title": "Song B",
            "artist": "Artist B",
            "apple_music_id": "456",
        },
    ]
    records = _build_trending_records(
        items,
        platform="spotify",
        chart_type="regional",
        country="us",
        entity_type="track",
        snapshot=date(2026, 4, 14),
    )
    assert len(records) == 2
    r0, r1 = records
    assert r0["entity_identifier"]["title"] == "Song A"
    assert r0["entity_identifier"]["artist_name"] == "Artist A"
    assert r0["entity_identifier"]["spotify_id"] == "abc123"
    assert r0["entity_identifier"]["isrc"] == "USRC12345678"
    assert r0["entity_identifier"]["chartmetric_id"] == 99
    assert r0["rank"] == 1
    assert r0["signals"]["source_platform"] == "spotify"
    assert r0["signals"]["chart_type"] == "regional"
    assert r0["signals"]["country"] == "us"
    assert r1["entity_identifier"]["title"] == "Song B"
    assert r1["entity_identifier"]["apple_music_id"] == "456"
    # Rank falls back to index when not provided
    assert r1["rank"] == 2


def test_build_trending_records_skips_nameless():
    items = [{"rank": 1}, {"name": "Song B"}]
    records = _build_trending_records(
        items,
        platform="spotify",
        chart_type="top",
        country="us",
        entity_type="track",
        snapshot=date(2026, 4, 14),
    )
    assert len(records) == 1
    assert records[0]["entity_identifier"]["title"] == "Song B"


def test_handler_is_registered():
    from chartmetric_ingest import handlers as cmq_handlers
    assert cmq_handlers.get("chart_sweep") is not None


def test_planner_is_registered():
    from chartmetric_ingest import planners as cmq_planners
    spec = cmq_planners.get("chart_sweep")
    assert spec is not None
    assert spec.fn.__name__ == "plan_chart_sweep"


def test_chart_endpoints_match_default_config():
    """Every chart_sweep endpoint needs a matching config row."""
    from chartmetric_ingest.endpoints import DEFAULT_ENDPOINT_CONFIGS
    from chartmetric_ingest.planners.chart_sweep import CHART_ENDPOINTS

    cfg_keys = {c["endpoint_key"] for c in DEFAULT_ENDPOINT_CONFIGS}
    missing = [
        s["endpoint_key"] for s in CHART_ENDPOINTS
        if s["endpoint_key"] not in cfg_keys
    ]
    assert not missing, f"endpoints with no default config: {missing}"


def test_chart_endpoints_are_unique():
    from chartmetric_ingest.planners.chart_sweep import CHART_ENDPOINTS
    keys = [s["endpoint_key"] for s in CHART_ENDPOINTS]
    assert len(keys) == len(set(keys)), "duplicate endpoint_key in CHART_ENDPOINTS"


def test_chart_endpoints_chart_sweep_prefix():
    from chartmetric_ingest.planners.chart_sweep import CHART_ENDPOINTS
    for spec in CHART_ENDPOINTS:
        assert spec["endpoint_key"].startswith("chart_sweep_"), spec["endpoint_key"]
