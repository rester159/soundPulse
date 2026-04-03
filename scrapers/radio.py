"""
Radio scraper — Billboard airplay chart data.

Parses Billboard's public chart pages for radio airplay data.
Uses HTML parsing against the o-chart-results-list-row structure.
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


class RadioScraper(BaseScraper):
    PLATFORM = "radio"
    BILLBOARD_BASE = "https://www.billboard.com"

    # All Billboard charts below are US-market charts, aligning with our
    # US-only data strategy for maximum prediction precision.
    # billboard-global-200 is excluded as it covers global, not US-specific data.
    CHARTS: dict[str, str] = {
        "radio-songs": "/charts/radio-songs/",
        "hot-100": "/charts/hot-100/",
        "country-airplay": "/charts/country-airplay/",
        "adult-contemporary": "/charts/adult-contemporary/",
        "billboard-200": "/charts/billboard-200/",
        "artist-100": "/charts/artist-100/",
    }

    # Charts that produce artist entities instead of track entities
    ARTIST_CHARTS: set[str] = {"artist-100"}

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        super().__init__(credentials, api_base_url, admin_key)
        self._semaphore = asyncio.Semaphore(1)
        # Billboard requires follow_redirects and a longer timeout
        self.client = httpx.AsyncClient(
            timeout=90.0,
            follow_redirects=True,
        )

    async def authenticate(self) -> None:
        logger.info("[%s] No authentication required for Billboard charts", self.PLATFORM)

    async def collect_trending(self) -> list[RawDataPoint]:
        all_points: list[RawDataPoint] = []

        for chart_name, chart_path in self.CHARTS.items():
            points = await self._fetch_chart(chart_name, chart_path)
            all_points.extend(points)
            # Be polite between chart requests
            await asyncio.sleep(3.0)

        logger.info(
            "[%s] Collected %d total data points across %d charts",
            self.PLATFORM, len(all_points), len(self.CHARTS),
        )
        return all_points

    async def _fetch_chart(self, chart_name: str, chart_path: str) -> list[RawDataPoint]:
        url = f"{self.BILLBOARD_BASE}{chart_path}"

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
                    "[%s] Failed to fetch %s: HTTP %d",
                    self.PLATFORM, chart_name, exc.response.status_code,
                )
                return []
            except httpx.HTTPError as exc:
                logger.error("[%s] Request error for %s: %s", self.PLATFORM, chart_name, exc)
                return []

        html = resp.text
        entries = self._parse_chart_rows(html)

        if not entries:
            logger.warning("[%s] Could not parse any entries from %s", self.PLATFORM, chart_name)
            return []

        snapshot = date.today()
        points: list[RawDataPoint] = []

        for entry in entries:
            point = self._build_data_point(entry, chart_name, snapshot)
            if point is not None:
                points.append(point)

        logger.info("[%s] Parsed %d entries from %s", self.PLATFORM, len(points), chart_name)
        return points

    def _parse_chart_rows(self, html: str) -> list[dict[str, Any]]:
        """Parse chart rows from Billboard HTML.

        Billboard uses <ul class="o-chart-results-list-row ..."> elements.
        Each row contains:
        - A <span class="c-label ..."> with the rank number
        - An <h3> with the song title
        - A <span class="...a-no-trucate..."> with the artist name
        """
        entries: list[dict[str, Any]] = []

        # Match each chart row (ul element)
        row_pattern = re.compile(
            r'<ul\s+class="o-chart-results-list-row[^"]*"[^>]*>(.*?)</ul>',
            re.DOTALL,
        )

        for row_match in row_pattern.finditer(html):
            row_html = row_match.group(1)
            entry = self._extract_entry(row_html)
            if entry and entry.get("title"):
                entries.append(entry)

        return entries

    def _extract_entry(self, row_html: str) -> dict[str, Any]:
        """Extract rank, title, and artist from a single chart row."""
        entry: dict[str, Any] = {}

        # Rank: first standalone number in a c-label span
        rank_match = re.search(
            r'<span\s+class="c-label[^"]*"[^>]*>\s*(\d+)\s*</span>',
            row_html,
        )
        if rank_match:
            entry["rank"] = int(rank_match.group(1))

        # Title: text inside <h3> tags (skip empty ones)
        h3_matches = re.findall(r'<h3[^>]*>(.*?)</h3>', row_html, re.DOTALL)
        for h3 in h3_matches:
            clean = re.sub(r'<[^>]+>', '', h3).strip()
            if clean and len(clean) > 1:
                entry["title"] = clean
                break

        # Artist: text inside span with a-no-trucate class
        artist_match = re.search(
            r'a-no-trucate[^>]*>(.*?)</span>',
            row_html,
            re.DOTALL,
        )
        if artist_match:
            clean = re.sub(r'<[^>]+>', '', artist_match.group(1)).strip()
            if clean:
                entry["artist_name"] = clean

        return entry

    def _build_data_point(
        self,
        entry: dict[str, Any],
        chart_name: str,
        snapshot: date,
    ) -> RawDataPoint | None:
        title = entry.get("title")
        if not title:
            return None

        artist_name = entry.get("artist_name") or "Unknown"
        rank = entry.get("rank")

        raw_score: float | None = None
        if rank is not None:
            raw_score = max(0.0, 100.0 - rank)

        signals: dict[str, Any] = {"chart_name": chart_name}

        # artist-100 chart produces artist entities
        if chart_name in self.ARTIST_CHARTS:
            return RawDataPoint(
                platform=self.PLATFORM,
                entity_type="artist",
                entity_identifier={
                    "artist_name": title,  # title field holds artist name on artist charts
                },
                raw_score=raw_score,
                rank=rank,
                signals=signals,
                snapshot_date=snapshot,
            )

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
            "error": "Billboard radio charts do not provide entity detail endpoints",
            "entity_id": entity_id,
        }
