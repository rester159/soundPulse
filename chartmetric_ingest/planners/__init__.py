"""Planner registry — each planner emits fetch jobs into the queue.

A planner is an async function that:
  1. Queries our DB for "what's stale and worth fetching"
  2. Computes a priority for each candidate from freshness × importance
  3. Calls `queue.enqueue(...)` for each job

Planners run on their own cadence (independent of the fetcher loop).
Each planner is registered with an `interval_seconds` — the runner
spawns a background task per planner that runs in a simple
sleep-then-plan loop. Planners never hit Chartmetric directly.

Self-bootstrapping: imports at the bottom of this file trigger
@register side-effects so the PLANNER_REGISTRY is populated on
package import.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

PlannerFn = Callable[[AsyncSession], Awaitable[int]]
# returns number of jobs enqueued (for logging / stats)


@dataclass
class PlannerSpec:
    name: str
    fn: PlannerFn
    interval_seconds: float


_PLANNERS: dict[str, PlannerSpec] = {}


def register(
    name: str,
    *,
    interval_seconds: float,
) -> Callable[[PlannerFn], PlannerFn]:
    """Decorator to register a planner + its cadence."""
    def decorator(fn: PlannerFn) -> PlannerFn:
        if name in _PLANNERS:
            raise RuntimeError(
                f"chartmetric_ingest planner {name!r} already registered"
            )
        _PLANNERS[name] = PlannerSpec(
            name=name, fn=fn, interval_seconds=float(interval_seconds)
        )
        return fn
    return decorator


def get(name: str) -> PlannerSpec | None:
    return _PLANNERS.get(name)


def all_planners() -> list[PlannerSpec]:
    return sorted(_PLANNERS.values(), key=lambda s: s.name)


def clear_for_tests() -> None:
    _PLANNERS.clear()


# ---- self-bootstrapping planners ----
from chartmetric_ingest.planners import track_history  # noqa: F401,E402
from chartmetric_ingest.planners import artist_stats   # noqa: F401,E402
