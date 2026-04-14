"""Planner registry tests + self-bootstrap sanity check.

Verifies that importing `chartmetric_ingest.planners` triggers the
@register side-effects in every implementation module, and that
PLATFORM_SPECS covers the same platforms the handler expects.
"""
from __future__ import annotations

import pytest

from chartmetric_ingest import planners as cmq_planners
from chartmetric_ingest.planners.track_history import (
    HANDLER_NAME,
    PLATFORM_SPECS,
    PLANNER_INTERVAL_SECONDS,
)


def test_track_history_planner_is_registered():
    spec = cmq_planners.get("track_history")
    assert spec is not None
    assert spec.name == "track_history"
    assert spec.interval_seconds == PLANNER_INTERVAL_SECONDS
    assert spec.fn.__name__ == "plan_track_history"


def test_all_planners_non_empty_after_bootstrap():
    # At least the track_history planner should be registered from
    # the package __init__ self-bootstrap imports.
    names = [p.name for p in cmq_planners.all_planners()]
    assert "track_history" in names


def test_platform_specs_well_formed():
    assert len(PLATFORM_SPECS) > 0
    for spec in PLATFORM_SPECS:
        assert "endpoint_key" in spec
        assert "platform" in spec
        assert isinstance(spec["metrics"], list)
        assert all(isinstance(m, str) for m in spec["metrics"])
        assert spec["endpoint_key"].startswith("track_stat_")
        assert spec["endpoint_key"].endswith(spec["platform"])


def test_handler_is_registered_by_name():
    from chartmetric_ingest import handlers as cmq_handlers
    assert cmq_handlers.get(HANDLER_NAME) is not None


def test_duplicate_planner_registration_rejected():
    with pytest.raises(RuntimeError, match="already registered"):
        @cmq_planners.register("track_history", interval_seconds=60)
        async def dup(db):
            return 0
