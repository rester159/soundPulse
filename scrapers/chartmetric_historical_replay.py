"""
Chartmetric US historical chart replay — Stage 2A of the ingestion
throughput push (2026-04-14).

Context: the live `chartmetric_deep_us` scraper only pulls "yesterday"
on each run, so it builds forward in time but never fills in history.
Chartmetric stores months of chart data per endpoint; we should be
consuming it.

This scraper wraps `ChartmetricDeepUSScraper.backfill(start, end)` and
iterates the ENTIRE ENDPOINT_MATRIX for a 7-day window further back in
time on every run. A rotating cycle (0..12) covers the last ~91 days
over 13 daily runs, then loops. State is stored in
`scraper_configs.config_json.backfill_cycle` so the scraper is
resumable across container restarts.

Budget
------
- ENDPOINT_MATRIX ≈ 281 calls per date (chart endpoints + per-genre fan-outs)
- 7 days × 281 calls/day ≈ 1,967 calls per run
- 1.0 s/req adaptive throttle → ~33 min runtime per run (safe under the
  1.5 h scheduler grace window)
- 13 cycles × 7 days = 91 days of historical coverage
- Daily cadence → full refresh every 13 days
- Quota impact: ~1,967 calls/day = ~1.1% of 172,800/day quota

Why not run a single 90-day pass
--------------------------------
~25k calls × 1.0 s/req = ~7 h runtime. The stale-scraper reaper kills
any run >1.5 h, and APScheduler's default `misfire_grace_time=3600`
won't recover a 7-hour job. Splitting into daily 7-day slices stays
comfortably inside the grace window and produces useful data on every
run, not just at the end of a marathon sweep.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any

from scrapers.chartmetric_deep_us import ChartmetricDeepUSScraper

logger = logging.getLogger(__name__)


# 13 weeks ≈ 91 days ≈ 3 months of chart history
BACKFILL_CYCLE_COUNT = 13
BACKFILL_DAYS_PER_CYCLE = 7


class ChartmetricHistoricalReplayScraper(ChartmetricDeepUSScraper):
    """
    Reuses every endpoint, parser, rate-limiter and bulk-ingest path from
    `ChartmetricDeepUSScraper`. The only difference is the date window
    passed to `backfill()` — an earlier 7-day slice selected by a
    rotating cycle counter stored in `scraper_configs.config_json`.
    """

    # ChartmetricDeepUSScraper already sets these; restating for clarity.
    PLATFORM = "chartmetric"

    async def run(self) -> dict[str, int]:
        """
        Read cycle state from the DB, compute the next 7-day window, and
        invoke the parent class' `backfill()`.
        """
        cycle = await self._read_cycle_state()
        # cycle=0 means "the week immediately before today". Today is
        # handled by the live deep_us scraper, so start at today-1.
        end_date = date.today() - timedelta(days=1 + cycle * BACKFILL_DAYS_PER_CYCLE)
        start_date = end_date - timedelta(days=BACKFILL_DAYS_PER_CYCLE - 1)
        logger.info(
            "[historical-replay] cycle=%d/%d start=%s end=%s",
            cycle, BACKFILL_CYCLE_COUNT, start_date.isoformat(), end_date.isoformat(),
        )
        try:
            totals = await self.backfill(start_date, end_date)
            next_cycle = (cycle + 1) % BACKFILL_CYCLE_COUNT
            await self._write_cycle_state(next_cycle, last_window=(start_date, end_date))
            logger.info(
                "[historical-replay] cycle %d complete, next=%d, totals=%s",
                cycle, next_cycle, totals,
            )
            return totals
        except Exception:
            # On failure, DO NOT advance the cycle — next run will retry
            # the same window. This is important: if an endpoint fails
            # on 90-day-old data it's almost certainly a transient rate
            # limit, not a permanent data problem.
            logger.exception(
                "[historical-replay] cycle %d failed — will retry next run", cycle,
            )
            raise

    # ----- Cycle state persistence -----

    async def _read_cycle_state(self) -> int:
        """Return current backfill_cycle from scraper_configs.config_json."""
        row = await self._fetch_config_row()
        config = (row or {}).get("config_json") or {}
        cycle = int(config.get("backfill_cycle", 0))
        if cycle < 0 or cycle >= BACKFILL_CYCLE_COUNT:
            cycle = 0
        return cycle

    async def _write_cycle_state(
        self, cycle: int, *, last_window: tuple[date, date]
    ) -> None:
        """Persist next backfill_cycle and last-run metadata via admin API."""
        payload = {
            "config_json": {
                "backfill_cycle": cycle,
                "last_window_start": last_window[0].isoformat(),
                "last_window_end": last_window[1].isoformat(),
            },
        }
        try:
            await self.client.patch(
                f"{self.api_base_url}/api/v1/admin/scraper-config/chartmetric_historical_replay/state",
                json=payload,
                headers={"X-API-Key": self.admin_key},
                timeout=30.0,
            )
        except Exception as exc:
            # Non-fatal: if the PATCH fails we'll just re-run the same
            # window on the next run (idempotent on snapshot dedupe).
            logger.warning("[historical-replay] cycle-state write failed: %s", exc)

    async def _fetch_config_row(self) -> dict[str, Any] | None:
        """Read our scraper_configs row via the admin API."""
        try:
            resp = await self.client.get(
                f"{self.api_base_url}/api/v1/admin/scraper-config/chartmetric_historical_replay/state",
                headers={"X-API-Key": self.admin_key},
                timeout=30.0,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as exc:
            logger.warning("[historical-replay] cycle-state read failed: %s", exc)
        return None
