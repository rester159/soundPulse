"""The single Chartmetric fetcher.

One long-running asyncio task drains the global work queue, respects
the token-bucket quota, dispatches successful responses to the
handler registry, and logs metrics. No other code in the codebase is
allowed to call `api.chartmetric.com` directly — L004 enforcement
becomes "nothing except this file talks to Chartmetric."

Dry mode
--------
Controlled by `CHARTMETRIC_FETCHER_DRY_MODE` env var. When true
(Phase A default), the fetcher claims jobs, waits on the quota, and
then logs what it *would* have fetched without actually hitting the
API or calling any handler. Flip to 0 after Phase B migration lands.

Idle behavior
-------------
When the queue is empty, the fetcher sleeps `IDLE_SLEEP_SECONDS`
before polling again. Short poll interval is fine because claim is
cheap (one indexed query) and planners push work frequently once
wired up.

Abandoned jobs
--------------
Every `STUCK_RELEASE_INTERVAL_SECONDS` we call `queue.release_stuck`
to un-claim jobs whose fetcher died mid-request. This is how the
system recovers from container replacements without operator
intervention.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import httpx

from chartmetric_ingest import handlers as cmq_handlers
from chartmetric_ingest import queue as cmq_queue
from chartmetric_ingest.quota import ChartmetricQuota

logger = logging.getLogger(__name__)

TOKEN_URL = "https://api.chartmetric.com/api/token"
IDLE_SLEEP_SECONDS = 2.0
STUCK_RELEASE_INTERVAL_SECONDS = 120.0
ERROR_BACKOFF_SECONDS = 5.0


def _dry_mode_enabled() -> bool:
    return os.environ.get("CHARTMETRIC_FETCHER_DRY_MODE", "1") == "1"


class ChartmetricFetcher:
    """Single-instance fetcher loop."""

    def __init__(self, *, session_factory, api_key: str):
        self._session_factory = session_factory
        self._api_key = api_key
        self._quota = ChartmetricQuota(session_factory)
        self._client: httpx.AsyncClient | None = None
        self._access_token: str | None = None
        self._stop = asyncio.Event()
        self._last_stuck_release = 0.0
        self._stats = {
            "claimed": 0,
            "completed": 0,
            "errors": 0,
            "dry_logged": 0,
            "rate_limited": 0,
        }

    async def start(self) -> None:
        """Main entrypoint. Runs until `stop()` is called."""
        self._client = httpx.AsyncClient(timeout=60.0)
        try:
            await self._quota.load_state()
        except Exception:
            logger.exception("[cm-fetcher] load_state failed — using defaults")

        dry = _dry_mode_enabled()
        logger.info(
            "[cm-fetcher] starting loop dry_mode=%s rate=%.2f req/s",
            dry, self._quota.current_rate,
        )
        try:
            await self._loop()
        finally:
            if self._client is not None:
                await self._client.aclose()

    def stop(self) -> None:
        self._stop.set()

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self._maybe_release_stuck()
                processed = await self._claim_and_process_one()
            except Exception:
                logger.exception("[cm-fetcher] unexpected error in loop body")
                processed = False
                await self._sleep_interruptible(ERROR_BACKOFF_SECONDS)
                continue
            if not processed:
                await self._sleep_interruptible(IDLE_SLEEP_SECONDS)

    async def _sleep_interruptible(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    async def _maybe_release_stuck(self) -> None:
        now = time.monotonic()
        if now - self._last_stuck_release < STUCK_RELEASE_INTERVAL_SECONDS:
            return
        self._last_stuck_release = now
        try:
            async with self._session_factory() as db:
                released = await cmq_queue.release_stuck(db, older_than_minutes=10)
            if released:
                logger.warning("[cm-fetcher] released %d stuck jobs", released)
        except Exception:
            logger.exception("[cm-fetcher] release_stuck failed")

    async def _claim_and_process_one(self) -> bool:
        async with self._session_factory() as db:
            job = await cmq_queue.claim_next(db)
        if job is None:
            return False
        self._stats["claimed"] += 1

        await self._quota.acquire()

        if _dry_mode_enabled():
            self._stats["dry_logged"] += 1
            logger.info(
                "[cm-fetcher][dry] would fetch id=%d handler=%s url=%s params=%s",
                job.id, job.handler, job.url, job.params,
            )
            async with self._session_factory() as db:
                await cmq_queue.complete(db, job.id, status=0, error="dry-mode")
            self._stats["completed"] += 1
            return True

        resp = await self._fetch_one(job.url, job.params)
        if resp is None:
            self._stats["errors"] += 1
            async with self._session_factory() as db:
                await cmq_queue.complete(db, job.id, status=None, error="transport-error")
            return True

        if resp.status_code == 429:
            self._stats["rate_limited"] += 1
            await self._quota.on_429()
            async with self._session_factory() as db:
                await cmq_queue.complete(db, job.id, status=429, error="rate-limited")
            return True

        if resp.status_code == 401:
            await self._authenticate()
            async with self._session_factory() as db:
                await cmq_queue.complete(db, job.id, status=401, error="re-auth")
            return True

        if not 200 <= resp.status_code < 300:
            self._stats["errors"] += 1
            async with self._session_factory() as db:
                await cmq_queue.complete(
                    db, job.id, status=resp.status_code, error=resp.text[:500]
                )
            return True

        await self._dispatch_to_handler(job, resp)
        return True

    async def _fetch_one(self, url: str, params: dict[str, Any]) -> httpx.Response | None:
        if self._client is None:
            return None
        if not self._access_token:
            await self._authenticate()
        try:
            return await self._client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
        except httpx.HTTPError as exc:
            logger.warning("[cm-fetcher] transport error on %s: %s", url, exc)
            return None

    async def _dispatch_to_handler(
        self,
        job: cmq_queue.ClaimedJob,
        resp: httpx.Response,
    ) -> None:
        try:
            body = resp.json()
        except Exception as exc:
            self._stats["errors"] += 1
            async with self._session_factory() as db:
                await cmq_queue.complete(
                    db, job.id, status=resp.status_code, error=f"json-decode: {exc}"
                )
            return

        handler = cmq_handlers.get(job.handler)
        if handler is None:
            self._stats["errors"] += 1
            logger.error(
                "[cm-fetcher] no handler registered for %r (job %d)",
                job.handler, job.id,
            )
            async with self._session_factory() as db:
                await cmq_queue.complete(
                    db, job.id, status=resp.status_code,
                    error=f"no handler: {job.handler}",
                )
            return

        try:
            async with self._session_factory() as db:
                await handler(body, job.handler_context, db)
            async with self._session_factory() as db:
                await cmq_queue.complete(db, job.id, status=resp.status_code)
            self._stats["completed"] += 1
        except Exception as exc:
            self._stats["errors"] += 1
            logger.exception("[cm-fetcher] handler %s failed on job %d", job.handler, job.id)
            async with self._session_factory() as db:
                await cmq_queue.complete(
                    db, job.id, status=resp.status_code,
                    error=f"handler: {type(exc).__name__}: {exc}",
                )

    async def _authenticate(self) -> None:
        if self._client is None:
            return
        try:
            resp = await self._client.post(TOKEN_URL, json={"refreshtoken": self._api_key})
            data = resp.json()
            token = data.get("token") or data.get("access_token")
            if not token:
                logger.error("[cm-fetcher] auth response missing token: %s", list(data.keys()))
                return
            self._access_token = token
            logger.info("[cm-fetcher] authenticated")
        except Exception:
            logger.exception("[cm-fetcher] auth failed")

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)
