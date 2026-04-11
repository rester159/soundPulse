"""
Chartmetric artist enrichment lane — Phase 4 Lever 6.

For every artist in our DB with a chartmetric_id, pull the latest-known
fan-base + engagement stats from 6 platforms via
`/api/artist/{id}/stat/{platform}?latest=true` and merge the result into
`artists.metadata_json.chartmetric_stats`.

Platforms pulled:
  - spotify   (followers, monthly_listeners, popularity)
  - instagram (followers)
  - tiktok    (followers, likes)
  - youtube   (subscribers, views)
  - twitter   (followers)
  - shazam    (shazams)

Per-artist cost: 6 API calls. With ~2.5K artists, ~15K calls per full
crawl. Weekly cadence = ~2,150/day amortized = 1.2% of the 172,800/day
budget.

Storage design (MVP — no new table):
  artists.metadata_json.chartmetric_stats = {
      "spotify":   {"followers": N, "monthly_listeners": N, "updated_at": "..."},
      "instagram": {"followers": N, "updated_at": "..."},
      "tiktok":    {"followers": N, "likes": N, "updated_at": "..."},
      ...
  }

A proper time-series table (`artist_platform_stats`) can be added in a
follow-up when we need historical trajectories for ML features. The
`trending_snapshots` table already records artist-level data points via
the spotify/artists charts, so we have some time series there already.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from scrapers.base import AuthenticationError, BaseScraper, RawDataPoint

logger = logging.getLogger(__name__)


# Platforms we query + fields we care about from the response
PLATFORMS: list[str] = ["spotify", "instagram", "tiktok", "youtube", "twitter", "shazam"]

# Field keys we'll try to extract from each platform's response. Chartmetric's
# /stat/{platform} returns a dict mapping metric name → time-series data.
# We pick the LATEST value (via ?latest=true) for a curated subset.
METRIC_KEYS: dict[str, list[str]] = {
    "spotify":   ["followers", "monthly_listeners", "popularity"],
    "instagram": ["followers"],
    "tiktok":    ["followers", "likes"],
    "youtube":   ["subscribers", "views"],
    "twitter":   ["followers"],
    "shazam":    ["shazams"],
}

PAGE_SIZE = 500   # admin-endpoint page size
MAX_ARTISTS = 10_000  # hard cap


class ChartmetricArtistStatsScraper(BaseScraper):
    """
    Enriches artist metadata with latest-known per-platform stats from
    Chartmetric. Writes back via /api/v1/admin/artists/{id}/merge-metadata.
    """

    PLATFORM = "chartmetric"
    API_BASE = "https://api.chartmetric.com"
    TOKEN_URL = "https://api.chartmetric.com/api/token"
    REQUEST_DELAY = 0.55

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        super().__init__(credentials, api_base_url, admin_key)
        self.access_token: str | None = None
        self._semaphore = asyncio.Semaphore(2)
        self._stats: dict[str, int] = {
            "artists_discovered": 0,
            "artists_processed": 0,
            "platform_calls": 0,
            "platform_hits": 0,
            "metadata_writes": 0,
            "errors": 0,
        }

    async def authenticate(self) -> None:
        api_key = self.credentials.get("api_key")
        if not api_key:
            raise AuthenticationError("Artist stats scraper missing 'api_key'")
        try:
            resp = await self._rate_limited_request(
                "POST", self.TOKEN_URL, json={"refreshtoken": api_key}
            )
            data = resp.json()
            token = data.get("token") or data.get("access_token")
            if not token:
                raise AuthenticationError(f"no token: {list(data.keys())}")
            self.access_token = token
            logger.info("[artist-stats] authenticated")
        except httpx.HTTPError as exc:
            raise AuthenticationError(f"auth failed: {exc}") from exc

    async def collect_trending(self) -> list[RawDataPoint]:
        await self._enrich_all_artists()
        return []

    async def collect_entity_details(self, entity_id: str) -> dict:
        return {"error": "artist-stats scraper does not support entity detail"}

    async def run(self) -> dict[str, int]:
        try:
            await self.authenticate()
            await self._enrich_all_artists()
            logger.info("[artist-stats] complete: %s", self._stats)
            return {"total": self._stats["metadata_writes"], **self._stats}
        finally:
            await self.close()

    # ----- Core loop -----

    async def _enrich_all_artists(self) -> None:
        offset = 0
        processed_total = 0
        while processed_total < MAX_ARTISTS:
            artists_page = await self._fetch_artist_page(offset=offset)
            if not artists_page:
                break
            self._stats["artists_discovered"] += len(artists_page)
            for artist in artists_page:
                cm_id = artist.get("chartmetric_id")
                db_uuid = artist.get("artist_id")
                name = artist.get("name", "")
                if cm_id is None or db_uuid is None:
                    continue
                try:
                    stats_by_platform = await self._fetch_artist_stats(int(cm_id))
                    if stats_by_platform:
                        await self._merge_into_artist_metadata(db_uuid, stats_by_platform, name)
                    self._stats["artists_processed"] += 1
                except Exception as exc:
                    logger.warning(
                        "[artist-stats] artist cm_id=%s (%s) failed: %s",
                        cm_id, name, exc,
                    )
                    self._stats["errors"] += 1
                if self._stats["artists_processed"] % 50 == 0 and self._stats["artists_processed"] > 0:
                    logger.info(
                        "[artist-stats] processed %d artists (hits=%d writes=%d errors=%d)",
                        self._stats["artists_processed"],
                        self._stats["platform_hits"],
                        self._stats["metadata_writes"],
                        self._stats["errors"],
                    )
            processed_total += len(artists_page)
            if len(artists_page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE

    async def _fetch_artist_page(self, *, offset: int) -> list[dict[str, Any]]:
        url = f"{self.api_base_url}/api/v1/admin/artists/with-chartmetric-id"
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

    async def _fetch_artist_stats(self, cm_id: int) -> dict[str, dict[str, Any]]:
        """Pull /api/artist/{cm_id}/stat/{platform} for each platform."""
        now_iso = datetime.now(timezone.utc).isoformat()
        out: dict[str, dict[str, Any]] = {}
        for platform in PLATFORMS:
            url = f"{self.API_BASE}/api/artist/{cm_id}/stat/{platform}"
            params = {"latest": "true"}
            async with self._semaphore:
                await asyncio.sleep(self.REQUEST_DELAY)
                self._stats["platform_calls"] += 1
                try:
                    resp = await self._rate_limited_request(
                        "GET", url,
                        headers={"Authorization": f"Bearer {self.access_token}"},
                        params=params,
                    )
                except httpx.HTTPStatusError as exc:
                    code = exc.response.status_code
                    if code in (401, 403, 404):
                        continue
                    raise

            try:
                data = resp.json()
            except Exception:
                continue

            # Chartmetric's /stat/{platform} shape varies. The fields we want
            # may live under obj.<metric_name> as scalars (with ?latest=true)
            # or as [[ts, value], ...] arrays. Pull the latest-known value.
            obj = data.get("obj") if isinstance(data, dict) else None
            if not isinstance(obj, dict):
                continue
            platform_stats: dict[str, Any] = {"updated_at": now_iso}
            for key in METRIC_KEYS.get(platform, []):
                val = obj.get(key)
                if isinstance(val, list) and val:
                    # Time-series shape: take the last entry's value
                    last = val[-1]
                    if isinstance(last, list) and len(last) >= 2:
                        platform_stats[key] = last[1]
                    elif isinstance(last, dict):
                        platform_stats[key] = last.get("value") or last.get("v")
                elif isinstance(val, (int, float)):
                    platform_stats[key] = val
                elif isinstance(val, dict):
                    # Maybe {"value": N}
                    platform_stats[key] = val.get("value")
            # Only record a platform if we extracted at least one metric
            if len(platform_stats) > 1:
                out[platform] = platform_stats
                self._stats["platform_hits"] += 1
        return out

    async def _merge_into_artist_metadata(
        self, db_uuid: str, stats_by_platform: dict[str, dict[str, Any]], name: str
    ) -> None:
        url = f"{self.api_base_url}/api/v1/admin/artists/{db_uuid}/merge-metadata"
        body = {
            "chartmetric_stats": stats_by_platform,
            "chartmetric_stats_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            resp = await self.client.post(
                url,
                json=body,
                headers={"X-API-Key": self.admin_key},
                timeout=30.0,
            )
            if resp.status_code in (200, 201):
                self._stats["metadata_writes"] += 1
            else:
                logger.warning(
                    "[artist-stats] merge-metadata HTTP %d for %s",
                    resp.status_code, name,
                )
        except httpx.HTTPError as exc:
            logger.warning("[artist-stats] merge-metadata error for %s: %s", name, exc)


async def _main() -> None:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [artist-stats] %(message)s")
    scraper = ChartmetricArtistStatsScraper(
        credentials={"api_key": os.environ.get("CHARTMETRIC_API_KEY", "")},
        api_base_url=os.environ.get("SOUNDPULSE_API_URL", "http://localhost:8000"),
        admin_key=os.environ.get("API_ADMIN_KEY", ""),
    )
    stats = await scraper.run()
    print(stats)


if __name__ == "__main__":
    asyncio.run(_main())
