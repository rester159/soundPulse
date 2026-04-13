"""
Chartmetric velocity pulse — hourly sanity check on high-momentum charts.

Runs every hour on a tight subset of Chartmetric chart endpoints —
Spotify viral + Spotify regional top-50 US — so we catch fast-moving
tracks before the 1.5h chartmetric_deep_us cadence picks them up.

This is Tier 3 of the Chartmetric crank-up. Cheap (~40 calls/run × 24
runs/day = ~960 calls/day = 0.6% of 172,800 quota). Complements but
doesn't replace chartmetric_deep_us — the deep scraper still runs the
full ENDPOINT_MATRIX on a slower cadence, this one just adds hourly
resolution on the most volatile surfaces.

Signals it captures that the slower cadences can miss:
  - First-hour viral explosions (Spotify Viral 50 US)
  - Intra-day position spikes on the Spotify regional top 50 US
  - Sudden rank jumps before the 1.5h chartmetric_deep_us next fires

The data funnels into the same trending_snapshots table so the
breakout detection + velocity calculation pick it up automatically —
no new schema needed.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Any

import httpx

from scrapers.base import AuthenticationError, BaseScraper, RawDataPoint

logger = logging.getLogger(__name__)

# Hot endpoints — high-volume, fast-moving charts. Everything else
# stays with the 1.5h chartmetric_deep_us cadence.
HOT_ENDPOINTS = [
    {
        "platform": "spotify",
        "chart_type": "viral_daily_pulse",
        "path": "/api/charts/spotify",
        "params": {"type": "viral", "interval": "daily"},
        "country_code": "us",
    },
    {
        "platform": "spotify",
        "chart_type": "regional_daily_pulse",
        "path": "/api/charts/spotify",
        "params": {"type": "regional", "interval": "daily"},
        "country_code": "us",
    },
    {
        "platform": "tiktok",
        "chart_type": "tiktok_songs_pulse",
        "path": "/api/charts/tiktok/songs",
        "params": {},
        "country_code": "us",
    },
    {
        "platform": "shazam",
        "chart_type": "shazam_pulse",
        "path": "/api/charts/shazam",
        "params": {},
        "country_code": "us",
    },
]

# Per-request delay — respect the 2 req/sec Chartmetric limit shared
# across all scrapers running concurrently.
REQUEST_DELAY_SECONDS = 0.6


class ChartmetricVelocityPulse(BaseScraper):
    """Hourly pulse scraper for the hottest Chartmetric chart surfaces."""

    PLATFORM = "chartmetric_velocity_pulse"

    def __init__(self, api_key: str, api_base_url: str, admin_key: str):
        super().__init__(api_key=api_key, api_base_url=api_base_url, admin_key=admin_key)
        self.upstream_base = "https://api.chartmetric.com"
        self._token: str | None = None

    async def authenticate(self) -> None:
        """Exchange the Chartmetric refresh token for a bearer token."""
        try:
            r = await self.client.post(
                f"{self.upstream_base}/api/token",
                json={"refreshtoken": self.api_key},
                timeout=15,
            )
            r.raise_for_status()
            self._token = r.json().get("token")
        except Exception as e:
            raise AuthenticationError(f"Chartmetric token exchange failed: {e}") from e
        if not self._token:
            raise AuthenticationError("Chartmetric returned empty token")
        self.client.headers["Authorization"] = f"Bearer {self._token}"

    async def collect(self) -> list[RawDataPoint]:
        """Hit each HOT_ENDPOINT once. Return all parsed RawDataPoints."""
        await self.authenticate()
        today_iso = date.today().isoformat()

        all_points: list[RawDataPoint] = []
        for ep in HOT_ENDPOINTS:
            try:
                params = dict(ep["params"])
                params["country_code"] = ep["country_code"]
                params["date"] = today_iso
                url = f"{self.upstream_base}{ep['path']}"
                resp = await self._rate_limited_request("GET", url, params=params)
                body = resp.json()
                items = body.get("obj") or body.get("data") or []
                if isinstance(items, dict):
                    items = items.get("data") or items.get("tracks") or []
                count = 0
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    # Best-effort normalize — different chart endpoints
                    # use different field names. The same permissive
                    # extractor pattern is used by chartmetric_deep_us.
                    name = (
                        item.get("name") or item.get("track_name")
                        or item.get("title") or ""
                    )
                    artists = item.get("artists") or item.get("artist_names") or []
                    if isinstance(artists, str):
                        artists = [artists]
                    if isinstance(artists, list) and artists and isinstance(artists[0], dict):
                        artists = [a.get("name", "") for a in artists if a.get("name")]
                    artist_str = ", ".join(artists) if artists else (item.get("artist") or "")
                    if not name or not artist_str:
                        continue
                    rank = item.get("rank") or item.get("position")
                    try:
                        rank_int = int(rank) if rank is not None else None
                    except (ValueError, TypeError):
                        rank_int = None
                    all_points.append(RawDataPoint(
                        source_platform=ep["platform"],
                        source_chart_id=f"velocity_pulse:{ep['chart_type']}",
                        country_code=ep["country_code"],
                        rank=rank_int,
                        entity_type="track",
                        track_name=name,
                        artist_name=artist_str,
                        extra={
                            "velocity_pulse": True,
                            "pulse_timestamp": datetime.now(timezone.utc).isoformat(),
                            "source_path": ep["path"],
                        },
                    ))
                    count += 1
                logger.info("[velocity-pulse] %s: %d items", ep["chart_type"], count)
            except Exception as e:
                logger.warning("[velocity-pulse] %s failed: %s", ep["chart_type"], e)
                continue
            await asyncio.sleep(REQUEST_DELAY_SECONDS)

        logger.info("[velocity-pulse] total collected: %d", len(all_points))
        return all_points
