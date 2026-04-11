"""
Chartmetric per-city US Apple Music tracks — Phase 3 Lever 5.

Discovers the top N US cities via `/api/cities?country_code=US`, then for
each city calls `/api/charts/applemusic/tracks?city_id={cid}&type=top` to
pull Apple Music's top tracks for that city. Captures tracks that are big
in NYC but not nationally, tracks that are big in Nashville but not LA,
etc. — regional variation the national chart misses.

Chartmetric found to return 23,857 US cities on the discovery endpoint.
We filter to TOP_N_CITIES by population to keep the API budget bounded.

Architecture
------------
1. Discovery pass (once per run): GET /api/cities?country_code=US →
   sort by population → take top N.
2. For each city × top-tracks chart variant (Pop, All Genres, Hip-Hop/Rap,
   R&B/Soul, Country, Dance, Electronic — the 7 biggest streaming genres),
   call /api/charts/applemusic/tracks?city_id={cid}&type=top&genre={g}.
3. Parse and bulk-POST to /api/v1/trending/bulk with
   signals.source_platform=applemusic_city_{city_id}.

Rate budget:
  Discovery:   1 call per run
  Per-city:    20 cities × 7 genres = 140 calls per run
  Total:       141 calls per run × daily = 141/day = 0.08% of 172,800/day

Cadence: every 24h (captures daily rank changes per city).

Shazam per-city charts: Chartmetric's /charts/shazam?city=<name> format
returned 0 items on live probing. Skipping until we figure out the
correct param shape.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from scrapers.base import AuthenticationError, BaseScraper, RawDataPoint

logger = logging.getLogger(__name__)


TOP_N_CITIES = 20  # top US cities by population we pull per-city charts for

# The 7 biggest Apple Music genres for US streaming activity.
# Keeps call count bounded; can expand to all 24 genres later if needed.
CITY_GENRES: list[str] = [
    "All Genres",
    "Pop",
    "Hip-Hop/Rap",
    "R&B/Soul",
    "Country",
    "Dance",
    "Electronic",
]


@dataclass
class CityRef:
    city_id: int
    name: str
    state: str
    population: int


class ChartmetricUSCitiesScraper(BaseScraper):
    """
    Per-city Apple Music top-tracks scraper for the top N US cities.
    """

    PLATFORM = "chartmetric"
    API_BASE = "https://api.chartmetric.com"
    TOKEN_URL = "https://api.chartmetric.com/api/token"
    REQUEST_DELAY = 0.55
    BULK_BATCH_SIZE = 500

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        super().__init__(credentials, api_base_url, admin_key)
        self.access_token: str | None = None
        self._semaphore = asyncio.Semaphore(2)
        self._buffer: list[dict[str, Any]] = []
        self._stats: dict[str, int] = {
            "cities_discovered": 0,
            "cities_processed": 0,
            "calls": 0,
            "empty_calls": 0,
            "tracks_buffered": 0,
            "errors": 0,
        }

    async def authenticate(self) -> None:
        api_key = self.credentials.get("api_key")
        if not api_key:
            raise AuthenticationError("US cities scraper missing 'api_key'")
        try:
            resp = await self._rate_limited_request(
                "POST", self.TOKEN_URL, json={"refreshtoken": api_key}
            )
            data = resp.json()
            token = data.get("token") or data.get("access_token")
            if not token:
                raise AuthenticationError(f"no token: {list(data.keys())}")
            self.access_token = token
            logger.info("[us-cities] authenticated")
        except httpx.HTTPError as exc:
            raise AuthenticationError(f"auth failed: {exc}") from exc

    async def collect_trending(self) -> list[RawDataPoint]:
        cities = await self._discover_top_cities()
        await self._crawl_cities(cities)
        return []

    async def collect_entity_details(self, entity_id: str) -> dict:
        return {"error": "us-cities scraper does not support entity detail"}

    async def run(self) -> dict[str, int]:
        try:
            await self.authenticate()
            cities = await self._discover_top_cities()
            self._stats["cities_discovered"] = len(cities)
            await self._crawl_cities(cities)
            await self._flush_buffer()
            logger.info("[us-cities] complete: %s", self._stats)
            return {"total": self._stats["tracks_buffered"], **self._stats}
        finally:
            await self.close()

    # ----- Discovery -----

    async def _discover_top_cities(self) -> list[CityRef]:
        """Fetch /api/cities?country_code=US and return top N by population."""
        url = f"{self.API_BASE}/api/cities"
        params = {"country_code": "US"}
        async with self._semaphore:
            await asyncio.sleep(self.REQUEST_DELAY)
            self._stats["calls"] += 1
            try:
                resp = await self._rate_limited_request(
                    "GET", url,
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    params=params,
                )
            except httpx.HTTPError as exc:
                logger.error("[us-cities] /api/cities failed: %s", exc)
                return []

        try:
            data = resp.json()
        except Exception:
            return []

        raw_cities: list[dict[str, Any]] = []
        if isinstance(data, dict):
            obj = data.get("obj")
            if isinstance(obj, list):
                raw_cities = obj
            elif isinstance(obj, dict):
                raw_cities = obj.get("data") or obj.get("cities") or []

        if not raw_cities:
            logger.warning("[us-cities] /api/cities returned 0 items")
            return []

        # Build typed CityRefs
        parsed: list[CityRef] = []
        for c in raw_cities:
            cid = c.get("city_id") or c.get("id")
            if cid is None:
                continue
            try:
                pop = int(c.get("population") or 0)
            except (ValueError, TypeError):
                pop = 0
            parsed.append(CityRef(
                city_id=int(cid),
                name=str(c.get("city_name") or c.get("name") or ""),
                state=str(c.get("province") or c.get("state") or ""),
                population=pop,
            ))

        # Sort descending by population, take top N
        parsed.sort(key=lambda x: x.population, reverse=True)
        top = parsed[:TOP_N_CITIES]
        logger.info(
            "[us-cities] discovered %d cities, top %d by population: %s",
            len(parsed), len(top),
            ", ".join(f"{c.name}({c.population//1000}k)" for c in top[:5]),
        )
        return top

    # ----- Crawl -----

    async def _crawl_cities(self, cities: list[CityRef]) -> None:
        if not cities:
            return
        target_date = date.today() - (date.today() - date.today())  # = today
        from datetime import timedelta
        target_date = date.today() - timedelta(days=1)  # Chartmetric lag ~1 day

        for i, city in enumerate(cities):
            for genre in CITY_GENRES:
                try:
                    await self._fetch_and_buffer_city_chart(city, genre, target_date)
                except Exception as exc:
                    logger.warning(
                        "[us-cities] %s × %s failed: %s",
                        city.name, genre, exc,
                    )
                    self._stats["errors"] += 1
                if len(self._buffer) >= self.BULK_BATCH_SIZE:
                    await self._flush_buffer()
            self._stats["cities_processed"] += 1
            if (i + 1) % 5 == 0:
                logger.info(
                    "[us-cities] processed %d/%d cities, tracks buffered=%d",
                    i + 1, len(cities), self._stats["tracks_buffered"],
                )

    async def _fetch_and_buffer_city_chart(
        self, city: CityRef, genre: str, target: date
    ) -> None:
        url = f"{self.API_BASE}/api/charts/applemusic/tracks"
        params: dict[str, Any] = {
            "date": target.isoformat(),
            "country_code": "us",
            "type": "top",
            "city_id": city.city_id,
            "genre": genre,
        }
        async with self._semaphore:
            await asyncio.sleep(self.REQUEST_DELAY)
            self._stats["calls"] += 1
            try:
                resp = await self._rate_limited_request(
                    "GET", url,
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    params=params,
                )
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                if code in (401, 403, 404):
                    return
                raise

        try:
            data = resp.json()
        except Exception:
            return

        tracks = []
        if isinstance(data, dict):
            obj = data.get("obj")
            if isinstance(obj, dict) and "data" in obj:
                tracks = obj["data"]
            elif isinstance(obj, list):
                tracks = obj

        if not tracks:
            self._stats["empty_calls"] += 1
            return

        for entry in tracks:
            point = self._parse_city_track(entry, city, genre, target)
            if point:
                self._buffer.append(point)
                self._stats["tracks_buffered"] += 1

    def _parse_city_track(
        self, entry: dict[str, Any], city: CityRef, genre: str, snapshot: date
    ) -> dict[str, Any] | None:
        cm_track = entry.get("cm_track") or entry.get("cm_track_id") or entry.get("id")
        name = entry.get("name") or entry.get("track_name") or entry.get("title")
        if not name:
            return None

        artist_names = entry.get("artist_names") or entry.get("artist")
        if isinstance(artist_names, list):
            artist_name = ", ".join(str(a) for a in artist_names)
        else:
            artist_name = artist_names

        entity_identifier: dict[str, Any] = {
            "title": name,
            "artist_name": artist_name or "Unknown",
        }
        if entry.get("spotify_track_id"):
            entity_identifier["spotify_id"] = entry["spotify_track_id"]
        if entry.get("apple_music_id") or entry.get("itunes_track_id"):
            entity_identifier["apple_music_id"] = str(
                entry.get("apple_music_id") or entry.get("itunes_track_id")
            )
        if entry.get("isrc"):
            entity_identifier["isrc"] = entry["isrc"]
        if cm_track:
            entity_identifier["chartmetric_id"] = cm_track

        rank = entry.get("rank") or entry.get("position")
        try:
            rank_int = int(float(rank)) if rank is not None else None
        except (ValueError, TypeError):
            rank_int = None

        return {
            "platform": "chartmetric",
            "entity_type": "track",
            "entity_identifier": entity_identifier,
            "raw_score": None,
            "rank": rank_int,
            "snapshot_date": snapshot.isoformat(),
            "signals": {
                "source_platform": f"applemusic_city",
                "chart_type": f"city_top_{genre}",
                "city_id": city.city_id,
                "city_name": city.name,
                "city_state": city.state,
                "city_population": city.population,
                "genre_filter": genre,
                "cm_track_id": cm_track,
            },
        }

    async def _flush_buffer(self) -> None:
        if not self._buffer:
            return
        url = f"{self.api_base_url}/api/v1/trending/bulk"
        while self._buffer:
            chunk = self._buffer[: self.BULK_BATCH_SIZE]
            self._buffer = self._buffer[self.BULK_BATCH_SIZE :]
            try:
                resp = await self.client.post(
                    url,
                    json={"items": chunk},
                    headers={"X-API-Key": self.admin_key},
                    timeout=120.0,
                )
                if resp.status_code in (200, 201):
                    body = resp.json().get("data", {})
                    logger.info(
                        "[us-cities] bulk: received=%d ingested=%d dupes=%d errors=%d created=%d",
                        body.get("received", 0), body.get("ingested", 0),
                        body.get("duplicates", 0), body.get("errors", 0),
                        body.get("entities_created", 0),
                    )
                else:
                    logger.error(
                        "[us-cities] bulk failed: HTTP %d %s",
                        resp.status_code, resp.text[:300],
                    )
            except httpx.HTTPError as exc:
                logger.error("[us-cities] bulk error: %s", exc)


async def _main() -> None:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [us-cities] %(message)s")
    scraper = ChartmetricUSCitiesScraper(
        credentials={"api_key": os.environ.get("CHARTMETRIC_API_KEY", "")},
        api_base_url=os.environ.get("SOUNDPULSE_API_URL", "http://localhost:8000"),
        admin_key=os.environ.get("API_ADMIN_KEY", ""),
    )
    stats = await scraper.run()
    print(stats)


if __name__ == "__main__":
    asyncio.run(_main())
