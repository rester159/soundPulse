"""
Chartmetric per-track historical stats — Stage 2B of the ingestion
throughput push (2026-04-14).

Context
-------
The live `chartmetric_deep_us` scraper and the Stage 2A replay scraper
together snapshot US *chart* positions for every track. What they do
NOT give us is per-track time-series for the metrics that actually
predict hits — streams, popularity, TikTok video count, Shazam
velocity — those live on `/api/track/{cm_id}/stat/{platform}`.

This scraper walks every track that has a `chartmetric_id`, pulls the
latest-known time-series for a curated list of (platform, metric)
pairs, and bulk-inserts into `track_stat_history` (tall/narrow).

Budget
------
- ~6 API calls per track (3 platforms × single fetch; each fetch
  returns a 30-90-day daily series for multiple metrics)
- Target throughput: ~5,000 tracks per run × 6 calls = 30,000 calls
- At 1.0 s/req with adaptive throttle → ~50 min runtime
- Cadence: every 24 h initially
- Daily quota cost: ~30,000 calls = ~17% of the 172,800/day budget
- Yield per run: 5,000 tracks × 3 platforms × ~3 metrics × ~30 days
  ≈ 1.35M rows per day, or ~40M rows per month at steady state

State
-----
Cursor-resumable via `scraper_configs.config_json.last_offset`. Each
run picks up where the previous one left off, wraps around to 0 when
the cursor exceeds the total track count, and logs a full-cycle
completion message so we can see coverage rate in logs.

Idempotency
-----------
The admin bulk endpoint uses ON CONFLICT DO UPDATE on
(track_id, platform, metric, snapshot_date), so overlapping windows
are harmless and we can re-run any range without creating duplicates.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from scrapers.base import AuthenticationError, BaseScraper, RawDataPoint

logger = logging.getLogger(__name__)


# (platform, [metric_keys]) — keys are the fields Chartmetric returns
# under `obj.<metric_name>`. Each metric is a [[ts, value], ...] daily
# time-series. We persist each (date, value) pair as its own row.
PLATFORM_METRICS: dict[str, list[str]] = {
    "spotify":   ["streams", "popularity", "playlist_reach"],
    "tiktok":    ["video_count", "view_count"],
    "shazam":    ["count"],
}

# Tuning
TRACKS_PER_RUN = 5_000      # hard ceiling per scheduler run
PAGE_SIZE = 500             # admin paginate chunk
BULK_FLUSH_SIZE = 1_000     # rows per POST to bulk admin endpoint
MAX_DAYS_PER_SERIES = 120   # clamp anything older than this


class ChartmetricTrackHistoryScraper(BaseScraper):
    """Pulls per-track daily time-series from Chartmetric."""

    PLATFORM = "chartmetric"
    API_BASE = "https://api.chartmetric.com"
    TOKEN_URL = "https://api.chartmetric.com/api/token"
    REQUEST_DELAY = 1.0
    REQUEST_DELAY_AFTER_THROTTLE = 2.0

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        super().__init__(credentials, api_base_url, admin_key)
        self.access_token: str | None = None
        self._semaphore = asyncio.Semaphore(2)
        self._throttled = False
        self._row_buffer: list[dict[str, Any]] = []
        self._stats: dict[str, int] = {
            "tracks_processed": 0,
            "api_calls": 0,
            "rows_sent": 0,
            "bulk_flushes": 0,
            "errors": 0,
        }

    def _current_delay(self) -> float:
        return (
            self.REQUEST_DELAY_AFTER_THROTTLE if self._throttled else self.REQUEST_DELAY
        )

    def _on_throttle(self) -> None:
        if not self._throttled:
            logger.warning(
                "[track-history] 429 observed — slowing to %.1fs/req",
                self.REQUEST_DELAY_AFTER_THROTTLE,
            )
            self._throttled = True

    # ----- Required BaseScraper hooks -----

    async def authenticate(self) -> None:
        api_key = self.credentials.get("api_key")
        if not api_key:
            raise AuthenticationError("track-history scraper missing 'api_key'")
        try:
            resp = await self._rate_limited_request(
                "POST", self.TOKEN_URL, json={"refreshtoken": api_key}
            )
            data = resp.json()
            token = data.get("token") or data.get("access_token")
            if not token:
                raise AuthenticationError(f"no token: {list(data.keys())}")
            self.access_token = token
            logger.info("[track-history] authenticated")
        except httpx.HTTPError as exc:
            raise AuthenticationError(f"auth failed: {exc}") from exc

    async def collect_trending(self) -> list[RawDataPoint]:
        # This scraper does not produce trending_snapshots rows.
        await self._crawl_tracks()
        return []

    async def collect_entity_details(self, entity_id: str) -> dict:
        return {"error": "track-history scraper does not support entity detail"}

    async def run(self) -> dict[str, int]:
        try:
            await self.authenticate()
            await self._crawl_tracks()
            await self._flush_buffer(force=True)
            logger.info("[track-history] complete: %s", self._stats)
            return {"total": self._stats["rows_sent"], **self._stats}
        finally:
            await self.close()

    # ----- Core loop -----

    async def _crawl_tracks(self) -> None:
        start_offset = await self._read_offset()
        offset = start_offset
        processed = 0
        wrapped = False

        while processed < TRACKS_PER_RUN:
            page = await self._fetch_track_page(offset=offset)
            if not page:
                # Reached the end — wrap back to 0 once per run.
                if wrapped:
                    break
                logger.info(
                    "[track-history] reached end at offset=%d, wrapping to 0", offset
                )
                offset = 0
                wrapped = True
                continue

            for track in page:
                if processed >= TRACKS_PER_RUN:
                    break
                cm_id = track.get("chartmetric_id")
                db_uuid = track.get("track_id")
                if cm_id is None or db_uuid is None:
                    continue
                try:
                    await self._pull_track_history(int(cm_id), db_uuid)
                    self._stats["tracks_processed"] += 1
                except Exception as exc:
                    self._stats["errors"] += 1
                    logger.warning(
                        "[track-history] track cm_id=%s failed: %s", cm_id, exc
                    )
                processed += 1

                if processed % 100 == 0:
                    logger.info(
                        "[track-history] processed=%d api=%d rows=%d errors=%d",
                        self._stats["tracks_processed"],
                        self._stats["api_calls"],
                        self._stats["rows_sent"],
                        self._stats["errors"],
                    )
                    await self._flush_buffer()

            offset += len(page)
            if len(page) < PAGE_SIZE:
                # End of page — let the outer loop decide whether to wrap.
                if wrapped:
                    break

        # Persist cursor: where the next run should start.
        final_offset = offset if not wrapped else offset
        await self._write_offset(final_offset)

    async def _fetch_track_page(self, *, offset: int) -> list[dict[str, Any]]:
        url = f"{self.api_base_url}/api/v1/admin/tracks/with-chartmetric-id"
        params = {"offset": offset, "limit": PAGE_SIZE}
        try:
            resp = await self.client.get(
                url, params=params,
                headers={"X-API-Key": self.admin_key},
                timeout=60.0,
            )
            if resp.status_code != 200:
                return []
            return resp.json().get("data", [])
        except httpx.HTTPError:
            return []

    async def _pull_track_history(self, cm_id: int, db_uuid: str) -> None:
        """Fetch all (platform, metric) series for one track."""
        for platform, metric_keys in PLATFORM_METRICS.items():
            url = f"{self.API_BASE}/api/track/{cm_id}/stat/{platform}"
            async with self._semaphore:
                await asyncio.sleep(self._current_delay())
                self._stats["api_calls"] += 1
                try:
                    resp = await self._rate_limited_request(
                        "GET", url,
                        headers={"Authorization": f"Bearer {self.access_token}"},
                    )
                except httpx.HTTPStatusError as exc:
                    code = exc.response.status_code
                    if code == 429:
                        self._on_throttle()
                    if code in (401, 403, 404, 429):
                        continue
                    raise

            try:
                data = resp.json()
            except Exception:
                continue
            obj = data.get("obj") if isinstance(data, dict) else None
            if not isinstance(obj, dict):
                continue

            for metric in metric_keys:
                series = obj.get(metric)
                if not isinstance(series, list):
                    continue
                for point in series[-MAX_DAYS_PER_SERIES:]:
                    row = self._point_to_row(
                        point=point,
                        db_uuid=db_uuid,
                        cm_id=cm_id,
                        platform=platform,
                        metric=metric,
                    )
                    if row is not None:
                        self._row_buffer.append(row)

            if len(self._row_buffer) >= BULK_FLUSH_SIZE:
                await self._flush_buffer()

    @staticmethod
    def _point_to_row(
        *,
        point: Any,
        db_uuid: str,
        cm_id: int,
        platform: str,
        metric: str,
    ) -> dict[str, Any] | None:
        """Normalize a single time-series point to a bulk-insert row."""
        ts = None
        value: int | None = None
        value_float: float | None = None

        if isinstance(point, list) and len(point) >= 2:
            ts, raw = point[0], point[1]
        elif isinstance(point, dict):
            ts = point.get("timestamp") or point.get("ts") or point.get("date")
            raw = point.get("value") or point.get("v")
        else:
            return None

        snapshot_date = ChartmetricTrackHistoryScraper._normalize_date(ts)
        if snapshot_date is None:
            return None

        if isinstance(raw, bool):
            return None
        if isinstance(raw, int):
            value = raw
        elif isinstance(raw, float):
            if raw.is_integer():
                value = int(raw)
            else:
                value_float = raw
        else:
            return None

        return {
            "track_id": db_uuid,
            "chartmetric_track_id": cm_id,
            "platform": platform,
            "metric": metric,
            "snapshot_date": snapshot_date,
            "value": value,
            "value_float": value_float,
        }

    @staticmethod
    def _normalize_date(ts: Any) -> str | None:
        """Accept ISO string or unix millis; return 'YYYY-MM-DD' or None."""
        if ts is None:
            return None
        if isinstance(ts, str):
            # Already an ISO string like '2026-03-01T00:00:00Z' or '2026-03-01'
            return ts[:10]
        if isinstance(ts, (int, float)):
            try:
                secs = float(ts)
                if secs > 1e12:  # millis
                    secs /= 1000.0
                return datetime.fromtimestamp(secs, tz=timezone.utc).date().isoformat()
            except Exception:
                return None
        return None

    # ----- Bulk flush -----

    async def _flush_buffer(self, *, force: bool = False) -> None:
        if not self._row_buffer:
            return
        if not force and len(self._row_buffer) < BULK_FLUSH_SIZE:
            return
        payload = {"rows": self._row_buffer}
        self._row_buffer = []
        url = f"{self.api_base_url}/api/v1/admin/track-stat-history/bulk"
        try:
            resp = await self.client.post(
                url,
                json=payload,
                headers={"X-API-Key": self.admin_key},
                timeout=120.0,
            )
            if resp.status_code in (200, 201):
                try:
                    accepted = int(resp.json().get("accepted", 0))
                except Exception:
                    accepted = len(payload["rows"])
                self._stats["rows_sent"] += accepted
                self._stats["bulk_flushes"] += 1
            else:
                self._stats["errors"] += 1
                logger.warning(
                    "[track-history] bulk HTTP %d: %s",
                    resp.status_code, resp.text[:200],
                )
        except httpx.HTTPError as exc:
            self._stats["errors"] += 1
            logger.warning("[track-history] bulk error: %s", exc)

    # ----- Cursor persistence -----

    async def _read_offset(self) -> int:
        try:
            resp = await self.client.get(
                f"{self.api_base_url}/api/v1/admin/scraper-config/chartmetric_track_history/state",
                headers={"X-API-Key": self.admin_key},
                timeout=30.0,
            )
            if resp.status_code == 200:
                cfg = (resp.json() or {}).get("config_json") or {}
                off = int(cfg.get("last_offset", 0))
                return max(0, off)
        except Exception as exc:
            logger.warning("[track-history] offset read failed: %s", exc)
        return 0

    async def _write_offset(self, offset: int) -> None:
        payload = {"config_json": {"last_offset": offset}}
        try:
            await self.client.patch(
                f"{self.api_base_url}/api/v1/admin/scraper-config/chartmetric_track_history/state",
                json=payload,
                headers={"X-API-Key": self.admin_key},
                timeout=30.0,
            )
        except Exception as exc:
            logger.warning("[track-history] offset write failed: %s", exc)


async def _main() -> None:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [track-history] %(message)s"
    )
    scraper = ChartmetricTrackHistoryScraper(
        credentials={"api_key": os.environ.get("CHARTMETRIC_API_KEY", "")},
        api_base_url=os.environ.get("SOUNDPULSE_API_URL", "http://localhost:8000"),
        admin_key=os.environ.get("API_ADMIN_KEY", ""),
    )
    stats = await scraper.run()
    print(stats)


if __name__ == "__main__":
    asyncio.run(_main())
