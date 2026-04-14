"""Lifespan hook: spawn the fetcher + planner tasks.

Called from `api/main.py` during FastAPI startup. Manages three
things:
  1. Seeds endpoint_config rows from `endpoints.DEFAULT_ENDPOINT_CONFIGS`
     (idempotent — operator overrides are preserved).
  2. Spawns the single ChartmetricFetcher as a background task.
  3. Spawns one background task per registered planner, each running
     a simple sleep-then-plan loop on the planner's declared cadence.

Planner loops are independent of the fetcher loop and independent of
each other. The fetcher doesn't care who produced a job; it only
looks at priority. This is the whole point of the queue: decouple
"what to fetch" from "when to fetch it".
"""
from __future__ import annotations

import asyncio
import logging
import os

from chartmetric_ingest.fetcher import ChartmetricFetcher

logger = logging.getLogger(__name__)

_fetcher: ChartmetricFetcher | None = None
_fetcher_task: asyncio.Task | None = None
_planner_tasks: list[asyncio.Task] = []
_stop_event: asyncio.Event | None = None


async def start() -> None:
    """Spawn fetcher + planners. Idempotent — second call is a no-op."""
    global _fetcher, _fetcher_task, _planner_tasks, _stop_event
    if _fetcher_task is not None and not _fetcher_task.done():
        return

    api_key = os.environ.get("CHARTMETRIC_API_KEY", "")
    if not api_key:
        logger.warning("[cm-runner] CHARTMETRIC_API_KEY not set — pipeline NOT started")
        return

    from api.database import async_session_factory
    from chartmetric_ingest.endpoints import seed_endpoint_configs
    # Importing the planners package triggers self-registration of
    # every @register'd planner. Importing the handlers package does
    # the same for handlers.
    from chartmetric_ingest import planners as cmq_planners
    from chartmetric_ingest import handlers as cmq_handlers  # noqa: F401

    # Seed endpoint config (idempotent)
    try:
        async with async_session_factory() as db:
            await seed_endpoint_configs(db)
    except Exception:
        logger.exception("[cm-runner] endpoint config seeding failed (continuing)")

    _stop_event = asyncio.Event()

    _fetcher = ChartmetricFetcher(
        session_factory=async_session_factory,
        api_key=api_key,
    )
    _fetcher_task = asyncio.create_task(_fetcher.start(), name="chartmetric-fetcher")

    _planner_tasks = []
    for spec in cmq_planners.all_planners():
        task = asyncio.create_task(
            _run_planner_loop(spec, async_session_factory),
            name=f"chartmetric-planner-{spec.name}",
        )
        _planner_tasks.append(task)
        logger.info(
            "[cm-runner] spawned planner %r cadence=%.0fs",
            spec.name, spec.interval_seconds,
        )

    logger.info(
        "[cm-runner] started: 1 fetcher + %d planners", len(_planner_tasks)
    )


async def _run_planner_loop(spec, session_factory) -> None:
    """Sleep-then-plan loop for a single planner."""
    assert _stop_event is not None
    # Small initial delay so planners don't all fire at the same instant
    # as the fetcher spins up.
    try:
        await asyncio.wait_for(_stop_event.wait(), timeout=5.0)
        return  # stopped before we started
    except asyncio.TimeoutError:
        pass

    while not _stop_event.is_set():
        try:
            async with session_factory() as db:
                enqueued = await spec.fn(db)
            if enqueued:
                logger.info(
                    "[cm-runner] planner %r enqueued %d jobs", spec.name, enqueued
                )
        except Exception:
            logger.exception("[cm-runner] planner %r raised", spec.name)
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=spec.interval_seconds)
        except asyncio.TimeoutError:
            pass


async def stop() -> None:
    """Signal everything to stop and await all tasks."""
    global _fetcher, _fetcher_task, _planner_tasks, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _fetcher is not None:
        _fetcher.stop()

    tasks = []
    if _fetcher_task is not None:
        tasks.append(_fetcher_task)
    tasks.extend(_planner_tasks)

    for task in tasks:
        try:
            await asyncio.wait_for(task, timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("[cm-runner] %s did not stop in 10s — cancelling", task.get_name())
            task.cancel()
        except Exception:
            logger.exception("[cm-runner] %s raised during shutdown", task.get_name())

    _fetcher = None
    _fetcher_task = None
    _planner_tasks = []
    _stop_event = None


def get_fetcher() -> ChartmetricFetcher | None:
    return _fetcher
