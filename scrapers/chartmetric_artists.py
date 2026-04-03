"""
Chartmetric Artist Stats scraper — per-artist social/streaming growth data.

Pulls artist-level social and streaming statistics from Chartmetric's API.
Unlike the main chartmetric.py scraper (which fetches chart data for tracks),
this scraper fetches per-artist metrics across platforms:

  GET /api/artist/{cm_artist_id}/stat/spotify    — Spotify followers, monthly listeners
  GET /api/artist/{cm_artist_id}/stat/instagram  — Instagram followers
  GET /api/artist/{cm_artist_id}/stat/tiktok     — TikTok followers, video creates
  GET /api/artist/{cm_artist_id}/stat/youtube     — YouTube subscribers, views
  GET /api/artist/{cm_artist_id}/stat/shazam     — Shazam lookup counts
  GET /api/artist/{cm_artist_id}/where-people-listen — Geographic audience data

All endpoints require: Authorization: Bearer {token}

Workflow:
  1. Authenticate with Chartmetric (same token exchange as chart scraper)
  2. Query SoundPulse DB for artist entities with chartmetric_id set
  3. For each artist, fetch social stats from each platform endpoint
  4. POST the stats as signals to the SoundPulse trending API
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


# Platform stat endpoints to fetch per artist.
# Each entry defines the URL path suffix and how to extract signals from the response.
PLATFORM_STAT_ENDPOINTS: list[dict[str, Any]] = [
    {
        "name": "spotify",
        "path_suffix": "/stat/spotify",
        "signal_keys": [
            "followers", "monthly_listeners", "listeners_to_followers_ratio",
            "popularity",
        ],
    },
    {
        "name": "instagram",
        "path_suffix": "/stat/instagram",
        "signal_keys": ["followers", "following", "posts"],
    },
    {
        "name": "tiktok",
        "path_suffix": "/stat/tiktok",
        "signal_keys": ["followers", "likes", "video_creates"],
    },
    {
        "name": "youtube",
        "path_suffix": "/stat/youtube",
        "signal_keys": ["subscribers", "views", "daily_views"],
    },
    {
        "name": "shazam",
        "path_suffix": "/stat/shazam",
        "signal_keys": ["shazam_count"],
    },
]


class ChartmetricArtistsScraper(BaseScraper):
    PLATFORM = "chartmetric_artists"
    API_BASE = "https://api.chartmetric.com"
    TOKEN_URL = "https://api.chartmetric.com/api/token"

    # Re-authenticate every N artists to avoid token expiry mid-run
    REAUTH_EVERY = 25
    # Conservative rate limiting
    REQUEST_DELAY = 0.6

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        super().__init__(credentials, api_base_url, admin_key)
        self.access_token: str | None = None
        self._semaphore = asyncio.Semaphore(2)

    # ------------------------------------------------------------------
    # Authentication (same mechanism as the chart scraper)
    # ------------------------------------------------------------------

    async def authenticate(self) -> None:
        api_key = self.credentials.get("api_key")
        if not api_key:
            raise AuthenticationError(
                "Chartmetric credentials missing 'api_key' (refresh token)"
            )

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
            raise AuthenticationError(
                f"Chartmetric auth failed with HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise AuthenticationError(
                f"Chartmetric auth request failed: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Collect trending: fetch artists from DB, then pull their stats
    # ------------------------------------------------------------------

    async def collect_trending(self) -> list[RawDataPoint]:
        if not self.access_token:
            raise AuthenticationError("Must authenticate before collecting data")

        artists = await self._fetch_artists_from_db()
        if not artists:
            logger.warning("[%s] No artists with chartmetric_id found in DB", self.PLATFORM)
            return []

        logger.info("[%s] Found %d artists with chartmetric_id", self.PLATFORM, len(artists))

        all_points: list[RawDataPoint] = []
        snapshot = date.today()

        for idx, artist in enumerate(artists):
            cm_id = artist["chartmetric_id"]
            artist_name = artist.get("name", "Unknown")

            # Re-authenticate periodically to avoid token expiry
            if idx > 0 and idx % self.REAUTH_EVERY == 0:
                logger.info(
                    "[%s] Re-authenticating after %d artists", self.PLATFORM, idx
                )
                try:
                    await self.authenticate()
                except AuthenticationError:
                    logger.error(
                        "[%s] Re-authentication failed at artist %d, stopping",
                        self.PLATFORM, idx,
                    )
                    break

            try:
                points = await self._fetch_artist_stats(cm_id, artist_name, artist, snapshot)
                all_points.extend(points)
            except Exception as exc:
                logger.error(
                    "[%s] Failed to fetch stats for artist %s (cm_id=%s): %s",
                    self.PLATFORM, artist_name, cm_id, exc,
                )

            if (idx + 1) % 10 == 0:
                logger.info(
                    "[%s] Processed %d/%d artists, %d data points so far",
                    self.PLATFORM, idx + 1, len(artists), len(all_points),
                )

        logger.info(
            "[%s] Collected %d total data points for %d artists",
            self.PLATFORM, len(all_points), len(artists),
        )
        return all_points

    async def _fetch_artists_from_db(self) -> list[dict[str, Any]]:
        """Query SoundPulse API for artist entities that have a chartmetric_id."""
        url = f"{self.api_base_url}/api/v1/trending"
        params = {"entity_type": "artist"}

        try:
            resp = await self.client.get(
                url,
                params=params,
                headers={"X-API-Key": self.admin_key},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("[%s] Failed to fetch artists from DB: %s", self.PLATFORM, exc)
            return []

        # Extract artists that have a chartmetric_id in their entity_identifier
        artists: list[dict[str, Any]] = []
        items = data if isinstance(data, list) else data.get("items", data.get("data", []))

        for item in items:
            eid = item.get("entity_identifier", {})
            cm_id = eid.get("chartmetric_id")
            if cm_id:
                artists.append({
                    "chartmetric_id": str(cm_id),
                    "name": eid.get("artist_name") or eid.get("name") or "Unknown",
                    "entity_identifier": eid,
                })

        # Deduplicate by chartmetric_id
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for a in artists:
            if a["chartmetric_id"] not in seen:
                seen.add(a["chartmetric_id"])
                unique.append(a)

        return unique

    # ------------------------------------------------------------------
    # Per-artist stat fetching
    # ------------------------------------------------------------------

    async def _fetch_artist_stats(
        self,
        cm_artist_id: str,
        artist_name: str,
        artist_info: dict[str, Any],
        snapshot: date,
    ) -> list[RawDataPoint]:
        """Fetch social stats for a single artist across all platforms."""
        all_signals: dict[str, Any] = {}

        # Fetch each platform's stats sequentially with rate limiting
        for endpoint in PLATFORM_STAT_ENDPOINTS:
            try:
                stats = await self._fetch_platform_stat(cm_artist_id, endpoint)
                if stats:
                    # Prefix signal keys with platform name to avoid collisions
                    platform_name = endpoint["name"]
                    for key in endpoint["signal_keys"]:
                        value = stats.get(key)
                        if value is not None:
                            all_signals[f"{platform_name}_{key}"] = value
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (401, 403):
                    logger.warning(
                        "[%s] Auth error fetching %s stats for artist %s, skipping",
                        self.PLATFORM, endpoint["name"], cm_artist_id,
                    )
                elif exc.response.status_code == 429:
                    logger.warning(
                        "[%s] Rate limited fetching %s stats for artist %s, backing off",
                        self.PLATFORM, endpoint["name"], cm_artist_id,
                    )
                    await asyncio.sleep(10)
                else:
                    logger.debug(
                        "[%s] HTTP %d fetching %s for artist %s",
                        self.PLATFORM, exc.response.status_code,
                        endpoint["name"], cm_artist_id,
                    )
            except Exception as exc:
                logger.debug(
                    "[%s] Error fetching %s for artist %s: %s",
                    self.PLATFORM, endpoint["name"], cm_artist_id, exc,
                )

        # Fetch geographic audience data
        try:
            geo_data = await self._fetch_where_people_listen(cm_artist_id)
            if geo_data:
                all_signals["top_cities"] = geo_data.get("cities", [])[:5]
                all_signals["top_countries"] = geo_data.get("countries", [])[:5]
        except Exception as exc:
            logger.debug(
                "[%s] Error fetching geo data for artist %s: %s",
                self.PLATFORM, cm_artist_id, exc,
            )

        if not all_signals:
            return []

        # Build the entity identifier from the original artist info
        entity_identifier: dict[str, Any] = {
            "artist_name": artist_name,
            "chartmetric_id": cm_artist_id,
        }
        # Carry over any additional IDs from the original entity
        orig_eid = artist_info.get("entity_identifier", {})
        for id_key in ("spotify_id", "apple_music_id", "isrc"):
            if orig_eid.get(id_key):
                entity_identifier[id_key] = orig_eid[id_key]

        # Compute a composite score from available follower/listener counts
        raw_score = self._compute_composite_score(all_signals)

        point = RawDataPoint(
            platform=self.PLATFORM,
            entity_type="artist",
            entity_identifier=entity_identifier,
            raw_score=raw_score,
            rank=None,
            signals=all_signals,
            snapshot_date=snapshot,
        )

        return [point]

    async def _fetch_platform_stat(
        self,
        cm_artist_id: str,
        endpoint: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Fetch a single platform stat endpoint for an artist."""
        url = f"{self.API_BASE}/api/artist/{cm_artist_id}{endpoint['path_suffix']}"

        # Use a date range: last 7 days
        today = date.today()
        params = {
            "since": (today - timedelta(days=7)).isoformat(),
            "until": today.isoformat(),
        }

        async with self._semaphore:
            await asyncio.sleep(self.REQUEST_DELAY)
            try:
                resp = await self._rate_limited_request(
                    "GET",
                    url,
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    params=params,
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    return None
                raise

        data = resp.json()

        # Chartmetric wraps stats in obj or obj.data; extract the latest values
        if isinstance(data, dict):
            obj = data.get("obj")
            if isinstance(obj, list) and obj:
                # Return the most recent data point (last in the list)
                return obj[-1] if isinstance(obj[-1], dict) else {}
            if isinstance(obj, dict):
                inner = obj.get("data")
                if isinstance(inner, list) and inner:
                    return inner[-1] if isinstance(inner[-1], dict) else {}
                return obj

        return None

    async def _fetch_where_people_listen(
        self, cm_artist_id: str
    ) -> dict[str, Any] | None:
        """Fetch geographic audience data for an artist."""
        url = f"{self.API_BASE}/api/artist/{cm_artist_id}/where-people-listen"

        async with self._semaphore:
            await asyncio.sleep(self.REQUEST_DELAY)
            try:
                resp = await self._rate_limited_request(
                    "GET",
                    url,
                    headers={"Authorization": f"Bearer {self.access_token}"},
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (401, 403, 404):
                    return None
                raise

        data = resp.json()
        if isinstance(data, dict):
            obj = data.get("obj")
            if isinstance(obj, dict):
                return obj
            if isinstance(obj, list):
                return {"cities": obj}
        return None

    @staticmethod
    def _compute_composite_score(signals: dict[str, Any]) -> float | None:
        """
        Compute a simple composite score from available social metrics.
        Uses a weighted log-scale approach so that one dominant platform
        doesn't overwhelm the score.
        """
        import math

        components: list[float] = []
        weights = {
            "spotify_monthly_listeners": 1.0,
            "spotify_followers": 0.5,
            "instagram_followers": 0.3,
            "tiktok_followers": 0.3,
            "youtube_subscribers": 0.3,
            "shazam_shazam_count": 0.4,
        }

        for key, weight in weights.items():
            val = signals.get(key)
            if val is not None:
                try:
                    numeric = float(val)
                    if numeric > 0:
                        components.append(weight * math.log10(numeric))
                except (ValueError, TypeError):
                    pass

        if not components:
            return None

        return round(sum(components), 2)

    # ------------------------------------------------------------------
    # Entity details (required by BaseScraper interface)
    # ------------------------------------------------------------------

    async def collect_entity_details(self, entity_id: str) -> dict:
        if not self.access_token:
            raise AuthenticationError("Must authenticate before fetching entity details")

        url = f"{self.API_BASE}/api/artist/{entity_id}"

        async with self._semaphore:
            await asyncio.sleep(self.REQUEST_DELAY)
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
                logger.error(
                    "[%s] Request error fetching entity %s: %s",
                    self.PLATFORM, entity_id, exc,
                )
                return {"error": str(exc), "entity_id": entity_id}
