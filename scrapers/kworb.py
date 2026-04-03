"""
Kworb scraper — daily Spotify chart data from kworb.net.

Kworb.net publishes daily Spotify and YouTube chart data freely.
This scraper pulls daily charts for multiple countries, parsing the
HTML table for rank, track, artist, and streams.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date
from typing import Any

import httpx

from scrapers.base import BaseScraper, RawDataPoint

logger = logging.getLogger(__name__)


class KworbScraper(BaseScraper):
    """Scrape daily Spotify chart data from kworb.net."""

    PLATFORM = "kworb"
    KWORB_BASE = "https://kworb.net/spotify/country"

    # US-only market focus for maximum data density and prediction precision.
    # Previously included GB, DE, BR, JP, MX — removed to concentrate on US.
    COUNTRIES: dict[str, str] = {
        "us": "us_daily.html",
    }

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        super().__init__(credentials, api_base_url, admin_key)
        self._semaphore = asyncio.Semaphore(1)
        self.client = httpx.AsyncClient(
            timeout=90.0,
            follow_redirects=True,
        )

    async def authenticate(self) -> None:
        logger.info("[%s] No authentication required for kworb.net", self.PLATFORM)

    async def collect_trending(self) -> list[RawDataPoint]:
        all_points: list[RawDataPoint] = []

        for country_code, page_slug in self.COUNTRIES.items():
            points = await self._fetch_country_chart(country_code, page_slug)
            all_points.extend(points)
            # Be polite between requests
            await asyncio.sleep(3.0)

        logger.info(
            "[%s] Collected %d total data points across %d countries",
            self.PLATFORM, len(all_points), len(self.COUNTRIES),
        )
        return all_points

    async def _fetch_country_chart(
        self, country_code: str, page_slug: str
    ) -> list[RawDataPoint]:
        url = f"{self.KWORB_BASE}/{page_slug}"

        async with self._semaphore:
            try:
                resp = await self._rate_limited_request(
                    "GET",
                    url,
                    headers={
                        "User-Agent": self.USER_AGENT,
                        "Accept": "text/html",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                )
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "[%s] Failed to fetch %s chart: HTTP %d",
                    self.PLATFORM, country_code, exc.response.status_code,
                )
                return []
            except httpx.HTTPError as exc:
                logger.error(
                    "[%s] Request error for %s: %s", self.PLATFORM, country_code, exc
                )
                return []

        html = resp.text
        entries = self._parse_table(html)

        if not entries:
            logger.warning(
                "[%s] Could not parse any entries from %s", self.PLATFORM, country_code
            )
            return []

        snapshot = date.today()
        points: list[RawDataPoint] = []

        for rank, entry in enumerate(entries, start=1):
            point = self._build_data_point(entry, country_code, rank, snapshot)
            if point is not None:
                points.append(point)

        logger.info(
            "[%s] Parsed %d entries from %s", self.PLATFORM, len(points), country_code
        )
        return points

    def _parse_table(self, html: str) -> list[dict[str, Any]]:
        """Parse the HTML table from kworb.net.

        Kworb uses a simple <table> with rows containing:
        - Column with track name and artist (often as "Artist - Track" or with links)
        - Column(s) with stream counts

        The format is typically:
        <tr><td>...<a>Artist - Track</a>...</td><td>streams</td>...</tr>
        """
        entries: list[dict[str, Any]] = []

        # Find all table rows
        row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)

        for row_match in row_pattern.finditer(html):
            row_html = row_match.group(1)

            # Skip header rows
            if "<th" in row_html:
                continue

            entry = self._extract_table_entry(row_html)
            if entry and entry.get("title"):
                entries.append(entry)

        return entries

    def _extract_table_entry(self, row_html: str) -> dict[str, Any]:
        """Extract track, artist, and streams from a table row."""
        entry: dict[str, Any] = {}

        # Extract cells
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        if not cells:
            return entry

        # First meaningful cell typically has the track info
        # Look for an anchor tag with "Artist - Track" format
        track_cell = cells[0] if cells else ""

        # Try to find link text first
        link_match = re.search(r"<a[^>]*>(.*?)</a>", track_cell, re.DOTALL)
        if link_match:
            track_text = re.sub(r"<[^>]+>", "", link_match.group(1)).strip()
        else:
            track_text = re.sub(r"<[^>]+>", "", track_cell).strip()

        if not track_text:
            return entry

        # Kworb typically uses "Artist - Track" format
        if " - " in track_text:
            parts = track_text.split(" - ", 1)
            entry["artist_name"] = parts[0].strip()
            entry["title"] = parts[1].strip()
        else:
            entry["title"] = track_text
            entry["artist_name"] = "Unknown"

        # Try to extract stream count from subsequent cells
        for cell in cells[1:]:
            clean_cell = re.sub(r"<[^>]+>", "", cell).strip()
            # Remove commas and check if numeric
            numeric = clean_cell.replace(",", "").replace(".", "")
            if numeric.isdigit() and len(numeric) > 3:
                entry["streams"] = int(numeric)
                break

        return entry

    def _build_data_point(
        self,
        entry: dict[str, Any],
        country_code: str,
        rank: int,
        snapshot: date,
    ) -> RawDataPoint | None:
        title = entry.get("title")
        if not title:
            return None

        artist_name = entry.get("artist_name") or "Unknown"
        streams = entry.get("streams")

        # Score based on rank position (top 200)
        raw_score = max(0.0, 200.0 - rank)

        # Boost score for high stream counts
        if streams and streams > 0:
            # Normalize streams to a 0-100 bonus
            # Top tracks get ~1M+ daily streams per country
            stream_bonus = min(100.0, streams / 10000.0)
            raw_score += stream_bonus

        signals: dict[str, Any] = {
            "country": country_code,
            "chart_rank": rank,
        }
        if streams:
            signals["daily_streams"] = streams

        return RawDataPoint(
            platform=self.PLATFORM,
            entity_type="track",
            entity_identifier={
                "title": title,
                "artist_name": artist_name,
            },
            raw_score=raw_score,
            rank=rank,
            signals=signals,
            snapshot_date=snapshot,
        )

    async def collect_entity_details(self, entity_id: str) -> dict:
        return {
            "error": "Kworb charts do not provide entity detail endpoints",
            "entity_id": entity_id,
        }
