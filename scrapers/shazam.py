"""
Shazam scraper using Shazam's public web API.

Previously used RapidAPI's shazam-core endpoint, which hit per-minute
rate limits on the free tier after ~5 calls and couldn't sustain any
useful cadence. Shazam's own web frontend API at shazam.com/services/
exposes the same chart + search data with no API key required.

Two data paths:
  1. Top chart for US: /services/charts/v4/chart/country/US?pageSize=200
     Returns the current top 200 Shazam'd songs in the US.
  2. Genre-aware search: /services/search/v4/en/US/web/search?term=...
     Surfaces tracks matching genre-specific queries.

Rate limit: Shazam's public API has no documented limit, but we
respect a conservative 1 req/sec to be good citizens.
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
    API_BASE = "https://www.shazam.com/services"

    SEARCH_QUERIES: list[dict[str, str]] = [
        {"query": "trending 2026", "genre_hint": "pop"},
        {"query": "hit song", "genre_hint": "pop"},
        {"query": "viral", "genre_hint": "pop"},
        {"query": "top rap", "genre_hint": "hip-hop"},
        {"query": "hip hop new", "genre_hint": "hip-hop"},
        {"query": "r&b soul", "genre_hint": "r-and-b"},
        {"query": "latin reggaeton", "genre_hint": "latin"},
        {"query": "electronic dance", "genre_hint": "electronic"},
        {"query": "rock alternative", "genre_hint": "rock"},
        {"query": "country new", "genre_hint": "country"},
        {"query": "afrobeats", "genre_hint": "african"},
        {"query": "k-pop", "genre_hint": "asian"},
        {"query": "tiktok viral", "genre_hint": "pop"},
    ]

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        super().__init__(credentials, api_base_url, admin_key)
        self._semaphore = asyncio.Semaphore(1)

    async def authenticate(self) -> None:
        logger.info("[%s] No authentication needed (public API)", self.PLATFORM)

    async def collect_trending(self) -> list[RawDataPoint]:
        all_points: list[RawDataPoint] = []
        seen_ids: set[str] = set()

        # Path 1: US top chart (the richest single call — up to 200 tracks)
        chart_points = await self._fetch_us_chart(seen_ids)
        all_points.extend(chart_points)

        # Path 2: Genre-aware searches for diversity beyond the top chart
        for search in self.SEARCH_QUERIES:
            points = await self._search_songs(
                query=search["query"],
                genre_hint=search["genre_hint"],
                seen_ids=seen_ids,
            )
            all_points.extend(points)

        logger.info(
            "[%s] Collected %d unique tracks (chart=%d, search=%d)",
            self.PLATFORM, len(all_points), len(chart_points),
            len(all_points) - len(chart_points),
        )
        return all_points

    async def _fetch_us_chart(self, seen_ids: set[str]) -> list[RawDataPoint]:
        """Fetch the current US Shazam top chart (up to 200 tracks)."""
        url = f"{self.API_BASE}/charts/v4/chart/country/US"
        async with self._semaphore:
            await asyncio.sleep(1.0)
            try:
                resp = await self.client.get(
                    url,
                    params={"pageSize": "200", "startFrom": "0"},
                    headers={"Accept": "application/json"},
                    timeout=30.0,
                )
                if resp.status_code != 200:
                    logger.warning(
                        "[%s] US chart HTTP %d: %s",
                        self.PLATFORM, resp.status_code, resp.text[:200],
                    )
                    return []
            except httpx.HTTPError as exc:
                logger.warning("[%s] US chart fetch failed: %s", self.PLATFORM, exc)
                return []

        try:
            data = resp.json()
        except Exception:
            logger.warning("[%s] Non-JSON response from US chart", self.PLATFORM)
            return []

        # Shazam chart responses vary in shape. Common patterns:
        # {tracks: [{key, title, subtitle, ...}]} or {chart: [{...}]}
        tracks_list = (
            data.get("tracks") or data.get("chart") or
            data.get("data") or data.get("songs") or []
        )

        snapshot = date.today()
        points: list[RawDataPoint] = []

        for position, track in enumerate(tracks_list, start=1):
            point = self._parse_chart_track(track, position, "us_chart", seen_ids, snapshot)
            if point:
                points.append(point)

        logger.info("[%s] US chart: %d tracks", self.PLATFORM, len(points))
        return points

    async def _search_songs(
        self,
        query: str,
        genre_hint: str,
        seen_ids: set[str],
    ) -> list[RawDataPoint]:
        url = f"{self.API_BASE}/search/v4/en/US/web/search"
        async with self._semaphore:
            await asyncio.sleep(1.0)
            try:
                resp = await self.client.get(
                    url,
                    params={"term": query, "limit": "20", "types": "songs"},
                    headers={"Accept": "application/json"},
                    timeout=30.0,
                )
                if resp.status_code != 200:
                    logger.warning(
                        "[%s] Search '%s' HTTP %d",
                        self.PLATFORM, query, resp.status_code,
                    )
                    return []
            except httpx.HTTPError as exc:
                logger.warning("[%s] Search '%s' failed: %s", self.PLATFORM, query, exc)
                return []

        try:
            data = resp.json()
        except Exception:
            logger.warning("[%s] Non-JSON for query '%s'", self.PLATFORM, query)
            return []

        # Search response shapes vary. Try multiple paths.
        songs = (
            data.get("tracks", {}).get("hits", []) or
            data.get("data", []) or
            data.get("songs", {}).get("data", []) or
            []
        )

        snapshot = date.today()
        points: list[RawDataPoint] = []

        for position, song in enumerate(songs, start=1):
            # Search results may nest the actual track under "track"
            track_obj = song.get("track", song)
            point = self._parse_chart_track(
                track_obj, position, f"search:{query}",
                seen_ids, snapshot, genre_hint=genre_hint,
            )
            if point:
                points.append(point)

        logger.info("[%s] Found %d tracks for query '%s'", self.PLATFORM, len(points), query)
        return points

    def _parse_chart_track(
        self,
        track: dict[str, Any],
        position: int,
        source: str,
        seen_ids: set[str],
        snapshot: date,
        genre_hint: str | None = None,
    ) -> RawDataPoint | None:
        """Parse a track from either chart or search response. Tolerates
        multiple Shazam response shapes."""
        # Shazam track object: {key, title, subtitle, ...}
        # OR Apple Music-style: {id, attributes: {name, artistName, ...}}
        shazam_key = str(track.get("key") or track.get("id") or "")
        if not shazam_key or shazam_key in seen_ids:
            return None
        seen_ids.add(shazam_key)

        # Shape 1: Shazam native {title, subtitle, ...}
        title = track.get("title") or track.get("heading", {}).get("title")
        artist = track.get("subtitle") or track.get("heading", {}).get("subtitle")

        # Shape 2: Apple Music-style {attributes: {name, artistName, ...}}
        attrs = track.get("attributes") or {}
        if not title:
            title = attrs.get("name") or attrs.get("title")
        if not artist:
            artist = attrs.get("artistName") or attrs.get("artist")

        if not title:
            return None

        # Extract metadata from whichever shape is present
        isrc = attrs.get("isrc") or track.get("isrc")
        genre_names = attrs.get("genreNames") or track.get("genres", {}).get("primary")
        if isinstance(genre_names, str):
            genre_names = [genre_names]

        signals: dict[str, Any] = {
            "shazam_key": shazam_key,
            "source": source,
        }
        if genre_names:
            signals["shazam_genres"] = genre_names
        if genre_hint:
            signals["genre_hint"] = genre_hint
        if attrs.get("albumName"):
            signals["album"] = attrs["albumName"]
        if attrs.get("durationInMillis"):
            signals["duration_ms"] = attrs["durationInMillis"]
        if attrs.get("releaseDate"):
            signals["release_date"] = attrs["releaseDate"]
        # Shazam native tracks sometimes carry Apple Music URLs and images
        share = track.get("share") or {}
        if share.get("href"):
            signals["shazam_url"] = share["href"]
        hub = track.get("hub") or {}
        for action in hub.get("actions", []):
            if action.get("type") == "uri" and "apple.com" in (action.get("uri") or ""):
                signals["apple_music_url"] = action["uri"]

        entity_id: dict[str, Any] = {
            "title": title,
            "artist_name": artist or "Unknown",
        }
        if isrc:
            entity_id["isrc"] = isrc

        return RawDataPoint(
            platform=self.PLATFORM,
            entity_type="track",
            entity_identifier=entity_id,
            raw_score=None,
            rank=position,
            signals=signals,
            snapshot_date=snapshot,
        )

    async def collect_entity_details(self, entity_id: str) -> dict:
        """Look up track details by Shazam key via the public web API."""
        url = f"https://www.shazam.com/services/amapi/v1/catalog/US/songs/{entity_id}"
        try:
            resp = await self.client.get(
                url, headers={"Accept": "application/json"}, timeout=15.0,
            )
            return resp.json()
        except Exception as e:
            return {"error": str(e), "entity_id": entity_id}
