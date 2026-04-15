"""Planner registry tests + self-bootstrap sanity check.

Verifies that importing `chartmetric_ingest.planners` triggers the
@register side-effects in every implementation module.

Note: `track_history` is intentionally NOT registered as a planner
(the module is still importable for the handler's sake, but the
per-track stat endpoints are internal-API-tier on Chartmetric and
our plan can't call them — see planners/__init__.py for the full
rationale). Tests here assert the disabled state so nobody
re-registers it without also verifying the tier.
"""
from __future__ import annotations

import pytest

from chartmetric_ingest import planners as cmq_planners
from chartmetric_ingest.planners.track_history import (
    HANDLER_NAME,
    PLATFORM_SPECS,
)


def test_track_history_planner_is_disabled():
    """track_history must NOT be in the active planner registry."""
    assert cmq_planners.get("track_history") is None


def test_active_planners_are_registered():
    """The two tier-compatible planners are present."""
    names = {p.name for p in cmq_planners.all_planners()}
    assert "artist_stats" in names
    assert "chart_sweep" in names
    assert "track_history" not in names


def test_track_history_platform_specs_still_well_formed():
    """Even though we don't run it, keep the module importable — the
    handler reads PLATFORM_SPECS to know which metrics to persist."""
    assert len(PLATFORM_SPECS) > 0
    for spec in PLATFORM_SPECS:
        assert "endpoint_key" in spec
        assert "platform" in spec
        assert isinstance(spec["metrics"], list)
        assert all(isinstance(m, str) for m in spec["metrics"])
        assert spec["endpoint_key"].startswith("track_stat_")
        assert spec["endpoint_key"].endswith(spec["platform"])


def test_handler_is_registered_by_name():
    """The handler stays registered so any pre-purged pending jobs
    can still resolve cleanly if the fetcher claims them."""
    from chartmetric_ingest import handlers as cmq_handlers
    assert cmq_handlers.get(HANDLER_NAME) is not None


def test_duplicate_planner_registration_rejected():
    with pytest.raises(RuntimeError, match="already registered"):
        @cmq_planners.register("artist_stats", interval_seconds=60)
        async def dup(db):
            return 0
