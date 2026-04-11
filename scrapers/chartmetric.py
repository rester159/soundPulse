"""
Chartmetric scraper — cross-platform chart data aggregator.

Pulls trending chart data from Chartmetric's API. Chartmetric is the primary
data backbone for SoundPulse — it aggregates cross-platform signals from
Spotify, Apple Music, TikTok, Shazam, and more into a single API.

API endpoint format:
  POST /api/token              — exchange refresh token for bearer token
  GET  /api/charts/spotify     — Spotify charts (params: date, country_code, type, interval)
  GET  /api/charts/shazam      — Shazam charts (params: date, country_code)
  GET  /api/charts/applemusic  — Apple Music charts (varies by plan)
  GET  /api/charts/tiktok      — TikTok charts (varies by plan)

Note: Apple Music, TikTok, and Shazam chart access may require a paid tier
above the free trial. The scraper gracefully skips unavailable endpoints.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

import httpx

from scrapers.base import (
    AuthenticationError,
    BaseScraper,
    RawDataPoint,
)

logger = logging.getLogger(__name__)


class ChartmetricScraper(BaseScraper):
    PLATFORM = "chartmetric"
    API_BASE = "https://api.chartmetric.com"
    TOKEN_URL = "https://api.chartmetric.com/api/token"

    # Chart endpoints to fetch.
    # Spotify track chart accepts type ∈ {regional, viral} ONLY (per
    # api.chartmetric.com/apidoc — verified 2026-04-11). The values
    # `plays`, `popularity`, `monthly_listeners`, `playlist_count`,
    # `playlist_reach` belong to the SEPARATE `/charts/spotify/artists`
    # endpoint, which is covered by `scrapers/chartmetric_deep_us.py`.
    # The previously-defined `plays` entry has been removed (P1-069 / L001).
    # Other platforms may have different param requirements or need higher-tier access.
    CHART_ENDPOINTS: list[dict[str, Any]] = [
        # Spotify charts
        {
            "source_platform": "spotify",
            "chart_type": "regional",
            "path": "/api/charts/spotify",
            "params": {"type": "regional", "interval": "daily"},
        },
        {
            "source_platform": "spotify",
            "chart_type": "viral",
            "path": "/api/charts/spotify",
            "params": {"type": "viral", "interval": "daily"},
        },
        # Shazam charts (200 items — great discovery signal)
        {
            "source_platform": "shazam",
            "chart_type": "top",
            "path": "/api/charts/shazam",
            "params": {},
        },
        # Apple Music charts — /tracks sub-resource required (confirmed by Chartmetric support Apr 2026)
        {
            "source_platform": "apple_music",
            "chart_type": "top",
            "path": "/api/charts/applemusic/tracks",
            "params": {"type": "top"},
        },
        # TikTok charts — /tracks sub-resource required (confirmed by Chartmetric support Apr 2026)
        {
            "source_platform": "tiktok",
            "chart_type": "viral",
            "path": "/api/charts/tiktok/tracks",
            "params": {},
        },
    ]

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        super().__init__(credentials, api_base_url, admin_key)
        self.access_token: str | None = None
        self._semaphore = asyncio.Semaphore(2)  # conservative concurrency for rate limits

    async def authenticate(self) -> None:
        api_key = self.credentials.get("api_key")
        if not api_key:
            raise AuthenticationError("Chartmetric credentials missing 'api_key' (refresh token)")

        try:
            resp = await self._rate_limited_request(
                "POST",
                self.TOKEN_URL,
                json={"refreshtoken": api_key},
            )
            data = resp.json()
            token = data.get("token") or data.get("access_token")
            if not token:
                raise AuthenticationError(
                    f"Chartmetric token response missing 'token': keys={list(data.keys())}"
                )
            self.access_token = token
            logger.info("[%s] Authenticated successfully", self.PLATFORM)
        except httpx.HTTPStatusError as exc:
            raise AuthenticationError(f"Chartmetric auth failed with HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise AuthenticationError(f"Chartmetric auth request failed: {exc}") from exc

    async def collect_trending(self) -> list[RawDataPoint]:
        if not self.access_token:
            raise AuthenticationError("Must authenticate before collecting data")

        today = date.today()
        # Chartmetric data can lag 1-2 days. Try today, yesterday, then 2 days ago.
        dates_to_try = [
            today.isoformat(),
            (today - timedelta(days=1)).isoformat(),
            (today - timedelta(days=2)).isoformat(),
        ]

        all_points: list[RawDataPoint] = []

        # Run chart fetches sequentially to respect rate limits
        for endpoint in self.CHART_ENDPOINTS:
            try:
                points = await self._fetch_chart(endpoint, dates_to_try)
                all_points.extend(points)
            except Exception as exc:
                logger.error(
                    "[%s] Failed to fetch %s %s chart: %s",
                    self.PLATFORM,
                    endpoint["source_platform"],
                    endpoint["chart_type"],
                    exc,
                )
            # Pause between chart requests to stay within rate limits
            await asyncio.sleep(2)

        logger.info("[%s] Collected %d total data points across all charts", self.PLATFORM, len(all_points))
        return all_points

    async def _fetch_chart(
        self,
        endpoint: dict[str, Any],
        dates_to_try: list[str],
    ) -> list[RawDataPoint]:
        source_platform = endpoint["source_platform"]
        chart_type = endpoint["chart_type"]

        entries = None
        for chart_date in dates_to_try:
            entries = await self._request_chart(endpoint, chart_date)
            if entries:
                logger.info("[%s] Found data for %s/%s on %s", self.PLATFORM, source_platform, chart_type, chart_date)
                break
            logger.info("[%s] No data for %s/%s on %s, trying next date", self.PLATFORM, source_platform, chart_type, chart_date)
            await asyncio.sleep(1)

        if entries is None:
            logger.warning(
                "[%s] No chart data available for %s/%s on either date",
                self.PLATFORM, source_platform, chart_type,
            )
            return []

        snapshot = date.today()
        points: list[RawDataPoint] = []

        for entry in entries:
            try:
                point = self._parse_chart_entry(entry, source_platform, chart_type, snapshot)
                if point is not None:
                    points.append(point)
            except Exception:
                logger.debug(
                    "[%s] Skipping unparseable chart entry: %s",
                    self.PLATFORM,
                    str(entry)[:200],
                )

        logger.info(
            "[%s] Parsed %d entries from %s/%s",
            self.PLATFORM, len(points), source_platform, chart_type,
        )
        return points

    async def _request_chart(
        self, endpoint: dict[str, Any], chart_date: str
    ) -> list[dict[str, Any]] | None:
        path = endpoint["path"]
        url = f"{self.API_BASE}{path}"

        # Build query params: merge endpoint-specific params with date and country
        params = {"date": chart_date, "country_code": "us"}
        params.update(endpoint.get("params", {}))

        async with self._semaphore:
            await asyncio.sleep(1)  # respect rate limits
            try:
                resp = await self._rate_limited_request(
                    "GET",
                    url,
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    params=params,
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (401, 403):
                    logger.warning(
                        "[%s] Access denied for %s (HTTP %d) — may require paid tier",
                        self.PLATFORM, path, exc.response.status_code,
                    )
                    return None
                if exc.response.status_code == 404:
                    return None
                raise

        data = resp.json()

        # Chartmetric wraps chart data in obj.data
        if isinstance(data, dict):
            obj = data.get("obj")
            if isinstance(obj, dict) and "data" in obj:
                return obj["data"]
            # Fallback: try common response keys
            for key in ("data", "charts", "tracks", "results", "items"):
                if key in data and isinstance(data[key], list):
                    return data[key]
        if isinstance(data, list):
            return data

        return None

    def _parse_chart_entry(
        self,
        entry: dict[str, Any],
        source_platform: str,
        chart_type: str,
        snapshot: date,
    ) -> RawDataPoint | None:
        # Chartmetric response fields (from /api/charts/spotify):
        #   id, name, isrc, spotify_track_id, cm_track, artist_names,
        #   rank, velocity, current_plays, spotify_popularity, etc.
        cm_track_id = entry.get("cm_track") or entry.get("cm_track_id") or entry.get("id")
        # Primary-artist ID — Chartmetric returns a list for tracks with
        # multiple artists; we keep only the first to match the artist_id FK.
        from scrapers.chartmetric_deep_us import _primary_cm_artist_id
        cm_artist_id = _primary_cm_artist_id(entry.get("cm_artist") or entry.get("cm_artist_id"))
        name = entry.get("name") or entry.get("title") or entry.get("track_name")

        # artist_names can be a list or string
        artist_names = entry.get("artist_names") or entry.get("artist_name") or entry.get("artist")
        if isinstance(artist_names, list):
            artist_name = ", ".join(artist_names)
        else:
            artist_name = artist_names

        rank = entry.get("rank") or entry.get("position") or entry.get("chart_position")

        if not name:
            return None

        entity_identifier: dict[str, Any] = {
            "title": name,
            "artist_name": artist_name or "Unknown",
        }

        if entry.get("spotify_track_id"):
            entity_identifier["spotify_id"] = entry["spotify_track_id"]
        elif entry.get("spotify_id"):
            entity_identifier["spotify_id"] = entry["spotify_id"]
        if entry.get("apple_music_id"):
            entity_identifier["apple_music_id"] = entry["apple_music_id"]
        if entry.get("isrc"):
            entity_identifier["isrc"] = entry["isrc"]
        if cm_track_id:
            entity_identifier["chartmetric_id"] = cm_track_id

        try:
            rank_int = int(float(rank)) if rank is not None else None
        except (ValueError, TypeError):
            rank_int = None

        # Build a meaningful score: use spotify_popularity if available, else invert rank
        spotify_popularity = entry.get("spotify_popularity")
        velocity = entry.get("velocity")
        current_plays = entry.get("current_plays")

        if spotify_popularity is not None:
            raw_score = float(spotify_popularity)
        elif rank_int is not None:
            raw_score = max(0.0, 200.0 - rank_int)
        else:
            raw_score = None

        return RawDataPoint(
            platform=self.PLATFORM,
            entity_type="track",
            entity_identifier=entity_identifier,
            raw_score=raw_score,
            rank=rank_int,
            signals={
                "chart_type": chart_type,
                "source_platform": source_platform,
                "cm_track_id": cm_track_id,
                "cm_artist_id": cm_artist_id,
                "source_rank": rank_int,
                "spotify_popularity": spotify_popularity,
                "velocity": velocity,
                "current_plays": current_plays,
                "genres": entry.get("track_genre") or entry.get("genre"),
            },
            snapshot_date=snapshot,
        )

    async def collect_entity_details(self, entity_id: str) -> dict:
        if not self.access_token:
            raise AuthenticationError("Must authenticate before fetching entity details")

        url = f"{self.API_BASE}/api/track/{entity_id}"

        async with self._semaphore:
            await asyncio.sleep(1)
            try:
                resp = await self._rate_limited_request(
                    "GET",
                    url,
                    headers={"Authorization": f"Bearer {self.access_token}"},
                )
                return resp.json()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "[%s] Failed to fetch entity %s: HTTP %d",
                    self.PLATFORM, entity_id, exc.response.status_code,
                )
                return {"error": f"HTTP {exc.response.status_code}", "entity_id": entity_id}
            except httpx.HTTPError as exc:
                logger.error("[%s] Request error fetching entity %s: %s", self.PLATFORM, entity_id, exc)
                return {"error": str(exc), "entity_id": entity_id}
