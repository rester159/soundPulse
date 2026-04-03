"""
Shazam scraper via RapidAPI (shazam-core).

Uses the search endpoint to discover tracks across genres,
since chart endpoints have been deprecated.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import httpx

from scrapers.base import AuthenticationError, BaseScraper, RawDataPoint

logger = logging.getLogger(__name__)


class ShazamScraper(BaseScraper):
    PLATFORM = "shazam"
    API_HOST = "shazam-core.p.rapidapi.com"
    API_BASE = f"https://{API_HOST}"

    # Search queries designed to surface trending/popular tracks across genres.
    # NOTE: Shazam search endpoint does not support a country/market filter,
    # so these results are global. Post-processing or cross-referencing with
    # US-specific sources (Spotify US, Billboard, etc.) is used to isolate
    # US-relevant tracks.
    SEARCH_QUERIES: list[dict[str, str]] = [
        {"query": "trending 2026", "genre_hint": "pop"},
        {"query": "hit song", "genre_hint": "pop"},
        {"query": "new release", "genre_hint": "pop"},
        {"query": "viral", "genre_hint": "pop"},
        {"query": "top rap", "genre_hint": "hip-hop"},
        {"query": "hip hop new", "genre_hint": "hip-hop"},
        {"query": "drill", "genre_hint": "hip-hop"},
        {"query": "r&b soul", "genre_hint": "r-and-b"},
        {"query": "latin reggaeton", "genre_hint": "latin"},
        {"query": "electronic dance", "genre_hint": "electronic"},
        {"query": "house music", "genre_hint": "electronic"},
        {"query": "rock alternative", "genre_hint": "rock"},
        {"query": "indie", "genre_hint": "rock"},
        {"query": "country new", "genre_hint": "country"},
        {"query": "afrobeats", "genre_hint": "african"},
        {"query": "k-pop", "genre_hint": "asian"},
        {"query": "amapiano", "genre_hint": "african"},
        {"query": "pop 2026", "genre_hint": "pop"},
        {"query": "summer hit", "genre_hint": "pop"},
        {"query": "tiktok viral song", "genre_hint": "pop"},
    ]

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        super().__init__(credentials, api_base_url, admin_key)
        self._rapidapi_key: str | None = None
        self._semaphore = asyncio.Semaphore(2)

    def _api_headers(self) -> dict[str, str]:
        return {
            "X-RapidAPI-Key": self._rapidapi_key or "",
            "X-RapidAPI-Host": self.API_HOST,
        }

    async def authenticate(self) -> None:
        key = self.credentials.get("rapidapi_key")
        if not key:
            raise AuthenticationError("Shazam credentials missing 'rapidapi_key'")
        self._rapidapi_key = key
        logger.info("[%s] RapidAPI key configured", self.PLATFORM)

    async def collect_trending(self) -> list[RawDataPoint]:
        if not self._rapidapi_key:
            raise AuthenticationError("Must authenticate before collecting data")

        all_points: list[RawDataPoint] = []
        seen_ids: set[str] = set()  # deduplicate across queries

        for search in self.SEARCH_QUERIES:
            points = await self._search_songs(
                query=search["query"],
                genre_hint=search["genre_hint"],
                seen_ids=seen_ids,
            )
            all_points.extend(points)
            # Pace requests to stay within RapidAPI limits
            await asyncio.sleep(1.0)

        logger.info(
            "[%s] Collected %d unique data points from %d searches",
            self.PLATFORM, len(all_points), len(self.SEARCH_QUERIES),
        )
        return all_points

    async def _search_songs(
        self,
        query: str,
        genre_hint: str,
        seen_ids: set[str],
    ) -> list[RawDataPoint]:
        async with self._semaphore:
            await asyncio.sleep(0.5)
            try:
                resp = await self._rate_limited_request(
                    "GET",
                    f"{self.API_BASE}/v1/search/multi",
                    headers=self._api_headers(),
                    params={
                        "search_type": "SONGS",
                        "query": query,
                        "offset": "0",
                        "limit": "20",
                    },
                )
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "[%s] Search failed for '%s': HTTP %d",
                    self.PLATFORM, query, exc.response.status_code,
                )
                return []
            except httpx.HTTPError as exc:
                logger.warning("[%s] Search error for '%s': %s", self.PLATFORM, query, exc)
                return []

        try:
            data = resp.json()
        except Exception:
            logger.warning("[%s] Non-JSON response for query '%s'", self.PLATFORM, query)
            return []

        songs = data.get("data", [])
        if not songs:
            logger.debug("[%s] No results for query '%s'", self.PLATFORM, query)
            return []

        snapshot = date.today()
        points: list[RawDataPoint] = []

        for position, song in enumerate(songs, start=1):
            try:
                song_id = song.get("id", "")
                if song_id in seen_ids:
                    continue
                seen_ids.add(song_id)

                attrs = song.get("attributes", {})
                title = attrs.get("name", "")
                artist = attrs.get("artistName", "")
                if not title or not artist:
                    continue

                isrc = attrs.get("isrc")
                genre_names = attrs.get("genreNames", [])
                album = attrs.get("albumName", "")
                duration_ms = attrs.get("durationInMillis")
                release_date = attrs.get("releaseDate")

                signals: dict[str, Any] = {
                    "search_query": query,
                    "genre_hint": genre_hint,
                    "shazam_id": song_id,
                }
                if genre_names:
                    signals["shazam_genres"] = genre_names
                if album:
                    signals["album"] = album
                if duration_ms:
                    signals["duration_ms"] = duration_ms
                if release_date:
                    signals["release_date"] = release_date
                if isrc:
                    signals["isrc"] = isrc

                point = RawDataPoint(
                    platform=self.PLATFORM,
                    entity_type="track",
                    entity_identifier={
                        "title": title,
                        "artist_name": artist,
                        "isrc": isrc,
                    },
                    raw_score=None,
                    rank=position,
                    signals=signals,
                    snapshot_date=snapshot,
                )
                points.append(point)

            except Exception:
                logger.debug("[%s] Failed to parse song in query '%s'", self.PLATFORM, query)

        logger.info("[%s] Found %d tracks for query '%s'", self.PLATFORM, len(points), query)
        return points

    async def collect_entity_details(self, entity_id: str) -> dict:
        """Look up track details by Shazam ID."""
        try:
            resp = await self._rate_limited_request(
                "GET",
                f"{self.API_BASE}/v2/tracks/details",
                headers=self._api_headers(),
                params={"track_id": entity_id},
            )
            return resp.json()
        except Exception as e:
            return {"error": str(e), "entity_id": entity_id}
