"""Lifespan hook: spawn the single Chartmetric fetcher as a background task.

Called from `api/main.py` during FastAPI startup. Keeps the fetcher
task handle so shutdown can cancel it cleanly.
"""
from __future__ import annotations

import asyncio
import logging
import os

from chartmetric_ingest.fetcher import ChartmetricFetcher

logger = logging.getLogger(__name__)

_fetcher: ChartmetricFetcher | None = None
_task: asyncio.Task | None = None


async def start() -> None:
    """Spawn the fetcher as a detached background task. Idempotent."""
    global _fetcher, _task
    if _task is not None and not _task.done():
        return

    api_key = os.environ.get("CHARTMETRIC_API_KEY", "")
    if not api_key:
        logger.warning("[cm-runner] CHARTMETRIC_API_KEY not set — fetcher NOT started")
        return

    from api.database import async_session_factory

    _fetcher = ChartmetricFetcher(
        session_factory=async_session_factory,
        api_key=api_key,
    )
    _task = asyncio.create_task(_fetcher.start(), name="chartmetric-fetcher")
    logger.info("[cm-runner] fetcher task spawned")


async def stop() -> None:
    """Signal the fetcher to stop and await task completion."""
    global _fetcher, _task
    if _fetcher is not None:
        _fetcher.stop()
    if _task is not None:
        try:
            await asyncio.wait_for(_task, timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("[cm-runner] fetcher did not stop within 10s — cancelling")
            _task.cancel()
        except Exception:
            logger.exception("[cm-runner] fetcher raised during shutdown")
    _fetcher = None
    _task = None


def get_fetcher() -> ChartmetricFetcher | None:
    return _fetcher
