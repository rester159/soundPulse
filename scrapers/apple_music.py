"""
Apple Music scraper for SoundPulse.

Collects chart data from Apple Music API using JWT (ES256) authentication.
Fetches top songs charts across multiple storefronts to discover trending tracks.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date
from pathlib import Path
from typing import Any

import jwt

from scrapers.base import AuthenticationError, BaseScraper, RawDataPoint

logger = logging.getLogger(__name__)


class AppleMusicScraper(BaseScraper):
    """Scrape trending chart data from Apple Music."""

    PLATFORM = "apple_music"
    API_BASE = "https://api.music.apple.com"

    # US-only storefront for maximum data density and prediction precision.
    # Previously included gb, de, fr, jp, br, mx, kr, au, ca — removed to
    # concentrate all API calls on US market data.
    STOREFRONTS = ["us"]

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        super().__init__(credentials, api_base_url, admin_key)
        self.developer_token: str = ""
        self._semaphore = asyncio.Semaphore(3)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(self) -> None:
        """Generate a JWT developer token using ES256 and the Apple Music private key."""
        team_id = self.credentials.get("team_id", "")
        key_id = self.credentials.get("key_id", "")
        private_key_path = self.credentials.get("private_key_path", "")

        if not team_id or not key_id or not private_key_path:
            raise AuthenticationError(
                "team_id, key_id, and private_key_path are required for Apple Music"
            )

        key_file = Path(private_key_path)
        if not key_file.exists():
            raise AuthenticationError(
                f"Apple Music private key file not found: {private_key_path}"
            )

        private_key = key_file.read_text().strip()
        if not private_key:
            raise AuthenticationError(
                f"Apple Music private key file is empty: {private_key_path}"
            )

        try:
            now = int(time.time())
            headers = {"alg": "ES256", "kid": key_id}
            payload = {
                "iss": team_id,
                "iat": now,
                "exp": now + 15777000,  # ~6 months
            }
            self.developer_token = jwt.encode(
                payload, private_key, algorithm="ES256", headers=headers
            )
        except Exception as e:
            raise AuthenticationError(f"Failed to generate Apple Music JWT: {e}") from e

        logger.info("[apple_music] Authenticated with developer token (key_id=%s)", key_id)

    # ------------------------------------------------------------------
    # Throttled request helper
    # ------------------------------------------------------------------

    async def _throttled_get(self, url: str, params: dict | None = None) -> Any:
        """GET with concurrency limit (3) and 350ms inter-request delay."""
        async with self._semaphore:
            await asyncio.sleep(0.35)
            resp = await self._rate_limited_request(
                "GET",
                url,
                headers={"Authorization": f"Bearer {self.developer_token}"},
                params=params,
            )
            return resp.json()

    # ------------------------------------------------------------------
    # Chart fetching
    # ------------------------------------------------------------------

    async def _fetch_chart(self, storefront: str) -> list[dict[str, Any]]:
        """Fetch the top songs chart for a single storefront."""
        url = f"{self.API_BASE}/v1/catalog/{storefront}/charts"
        params = {"types": "songs", "limit": "100"}

        try:
            data = await self._throttled_get(url, params=params)
            # Response: results.songs[0].data
            songs_charts = data.get("results", {}).get("songs", [])
            if songs_charts:
                return songs_charts[0].get("data", [])
            return []
        except Exception as e:
            logger.warning(
                "[apple_music] Failed to fetch chart for storefront %s: %s",
                storefront,
                e,
            )
            return []

    # ------------------------------------------------------------------
    # collect_trending
    # ------------------------------------------------------------------

    async def collect_trending(self) -> list[RawDataPoint]:
        """Fetch top songs charts across all storefronts."""
        today = date.today()
        data_points: list[RawDataPoint] = []
        seen: set[str] = set()  # track (id, storefront) to avoid dupes

        logger.info(
            "[apple_music] Fetching charts for %d storefronts", len(self.STOREFRONTS)
        )

        for storefront in self.STOREFRONTS:
            entries = await self._fetch_chart(storefront)
            logger.info(
                "[apple_music] Storefront %s: %d chart entries",
                storefront,
                len(entries),
            )

            for position, entry in enumerate(entries, start=1):
                track_id = entry.get("id", "")
                dedup_key = f"{track_id}:{storefront}"
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                attrs = entry.get("attributes", {})
                title = attrs.get("name", "")
                artist_name = attrs.get("artistName", "")
                album_name = attrs.get("albumName", "")
                genre_names = attrs.get("genreNames", [])
                isrc = attrs.get("isrc", "")
                apple_url = attrs.get("url", "")

                data_points.append(
                    RawDataPoint(
                        platform="apple_music",
                        entity_type="track",
                        entity_identifier={
                            "apple_music_id": track_id,
                            "title": title,
                            "artist_name": artist_name,
                            "isrc": isrc,
                        },
                        raw_score=None,
                        rank=position,
                        signals={
                            "storefront": storefront,
                            "chart_type": "songs",
                            "apple_music_genres": genre_names,
                            "album_name": album_name,
                            "apple_music_url": apple_url,
                        },
                        snapshot_date=today,
                    )
                )

        logger.info("[apple_music] Collected %d total chart entries", len(data_points))
        return data_points

    # ------------------------------------------------------------------
    # collect_entity_details
    # ------------------------------------------------------------------

    async def collect_entity_details(self, entity_id: str) -> dict:
        """Fetch detailed info for a song by Apple Music ID (uses US storefront)."""
        url = f"{self.API_BASE}/v1/catalog/us/songs/{entity_id}"
        data = await self._throttled_get(url)
        return data.get("data", [{}])[0] if data.get("data") else {}
