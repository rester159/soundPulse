"""
Chartmetric per-artist tracks enrichment — Phase 2 Lever 2.

For every artist in our DB that has a chartmetric_id, call
`/api/artist/{id}/tracks?limit=100` and bulk-POST the results.
Harvests deep catalog tracks that never appear on any chart — the
artist's full discography as Chartmetric knows it.

Discovery → Crawl → Ingest flow:
  1. GET /api/v1/admin/artists/with-chartmetric-id?limit=500&offset=N
     (paginated, hits our own API which reads the artists table).
  2. For each returned artist, call
     /api/artist/{chartmetric_id}/tracks?limit=100 on Chartmetric.
  3. Parse tracks into TrendingIngest-shaped records with
     signals.source_platform="artist_catalog", signals.artist_id=<uuid>.
  4. Flush buffer every 500 records via /api/v1/trending/bulk.

Cadence: weekly (168h). With ~2,500 tracked artists × 0.55s/call =
~23 minutes runtime. Budget: ~2,500 calls/week = ~350/day amortized
= 0.2% of the 172,800/day Chartmetric quota.

The scraper is idempotent — rerunning it re-pulls artist catalogs,
which only adds NEW tracks (dedupe via the ISRC/spotify_id path in
entity_resolution + ON CONFLICT DO NOTHING on the snapshot unique
constraint).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import httpx

from scrapers.base import AuthenticationError, BaseScraper, RawDataPoint

logger = logging.getLogger(__name__)

PAGE_SIZE = 500   # how many artists per admin-endpoint page
TRACKS_LIMIT = 100  # limit param on /api/artist/{id}/tracks
MAX_ARTISTS = 20_000   # hard cap to prevent runaway runs


class ChartmetricArtistTracksScraper(BaseScraper):
    """
    Crawls per-artist track catalogs from Chartmetric for every artist in
    our DB that has a chartmetric_id.

    Overrides BaseScraper.run() to do its own bulk ingest.
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
            "artists_discovered": 0,
            "artists_processed": 0,
            "artists_skipped": 0,
            "tracks_buffered": 0,
            "calls": 0,
            "errors": 0,
        }

    async def authenticate(self) -> None:
        api_key = self.credentials.get("api_key")
        if not api_key:
            raise AuthenticationError("Artist tracks scraper missing 'api_key'")
        try:
            resp = await self._rate_limited_request(
                "POST", self.TOKEN_URL, json={"refreshtoken": api_key}
            )
            data = resp.json()
            token = data.get("token") or data.get("access_token")
            if not token:
                raise AuthenticationError(f"no token: {list(data.keys())}")
            self.access_token = token
            logger.info("[artist-tracks] authenticated")
        except httpx.HTTPError as exc:
            raise AuthenticationError(f"auth failed: {exc}") from exc

    async def collect_trending(self) -> list[RawDataPoint]:
        await self._crawl_all_artists()
        return []

    async def collect_entity_details(self, entity_id: str) -> dict:
        return {"error": "artist-tracks scraper does not support entity detail"}

    async def run(self) -> dict[str, int]:
        try:
            await self.authenticate()
            await self._crawl_all_artists()
            await self._flush_buffer()
            logger.info("[artist-tracks] complete: %s", self._stats)
            return {"total": self._stats["tracks_buffered"], **self._stats}
        finally:
            await self.close()

    # ----- Core crawl loop -----

    async def _crawl_all_artists(self) -> None:
        offset = 0
        processed_total = 0
        while processed_total < MAX_ARTISTS:
            artists_page = await self._fetch_artist_page(offset=offset, limit=PAGE_SIZE)
            if not artists_page:
                break
            self._stats["artists_discovered"] += len(artists_page)
            for i, artist in enumerate(artists_page):
                cm_id = artist.get("chartmetric_id")
                sp_artist_id = artist.get("artist_id")  # UUID string
                name = artist.get("name", "Unknown")
                if cm_id is None:
                    self._stats["artists_skipped"] += 1
                    continue
                try:
                    await self._fetch_and_buffer_artist_tracks(
                        cm_id=int(cm_id),
                        db_artist_uuid=sp_artist_id,
                        name=name,
                    )
                    self._stats["artists_processed"] += 1
                except Exception as exc:
                    logger.warning(
                        "[artist-tracks] artist cm_id=%s (%s) failed: %s",
                        cm_id, name, exc,
                    )
                    self._stats["artists_skipped"] += 1
                if len(self._buffer) >= self.BULK_BATCH_SIZE:
                    await self._flush_buffer()
                if (processed_total + i + 1) % 100 == 0:
                    logger.info(
                        "[artist-tracks] processed %d artists, tracks buffered=%d",
                        processed_total + i + 1, self._stats["tracks_buffered"],
                    )
            processed_total += len(artists_page)
            if len(artists_page) < PAGE_SIZE:
                break  # partial page = no more artists
            offset += PAGE_SIZE

    async def _fetch_artist_page(
        self, *, offset: int, limit: int
    ) -> list[dict[str, Any]]:
        """Pull a page of artists from our own admin endpoint."""
        url = f"{self.api_base_url}/api/v1/admin/artists/with-chartmetric-id"
        params = {"offset": offset, "limit": limit}
        try:
            resp = await self.client.get(
                url,
                params=params,
                headers={"X-API-Key": self.admin_key},
                timeout=60.0,
            )
            if resp.status_code != 200:
                logger.warning(
                    "[artist-tracks] admin page HTTP %d at offset=%d",
                    resp.status_code, offset,
                )
                return []
            return resp.json().get("data", [])
        except httpx.HTTPError as exc:
            logger.warning("[artist-tracks] admin page fetch failed offset=%d: %s",
                           offset, exc)
            return []

    async def _fetch_and_buffer_artist_tracks(
        self, *, cm_id: int, db_artist_uuid: str | None, name: str
    ) -> None:
        """Call /api/artist/{cm_id}/tracks and buffer the records."""
        url = f"{self.API_BASE}/api/artist/{cm_id}/tracks"
        params = {"limit": TRACKS_LIMIT}
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
                    return  # artist no longer exists on Chartmetric, skip
                raise

        try:
            data = resp.json()
        except Exception:
            return

        tracks = []
        if isinstance(data, dict):
            obj = data.get("obj")
            if isinstance(obj, list):
                tracks = obj
            elif isinstance(obj, dict):
                tracks = obj.get("data") or obj.get("tracks") or []

        if not tracks:
            return

        snapshot_date = date.today()
        for t in tracks:
            point = self._parse_artist_track(
                t, cm_artist_id=cm_id, db_artist_uuid=db_artist_uuid,
                artist_name=name, snapshot=snapshot_date,
            )
            if point:
                self._buffer.append(point)
                self._stats["tracks_buffered"] += 1

    def _parse_artist_track(
        self,
        entry: dict[str, Any],
        *,
        cm_artist_id: int,
        db_artist_uuid: str | None,
        artist_name: str,
        snapshot: date,
    ) -> dict[str, Any] | None:
        cm_track = entry.get("cm_track") or entry.get("cm_track_id") or entry.get("id")
        name = entry.get("name") or entry.get("track_name") or entry.get("title")
        if not name:
            return None

        entity_identifier: dict[str, Any] = {
            "title": name,
            "artist_name": artist_name,
        }
        if entry.get("spotify_track_id"):
            entity_identifier["spotify_id"] = entry["spotify_track_id"]
        elif entry.get("spotify_id"):
            entity_identifier["spotify_id"] = entry["spotify_id"]
        if entry.get("apple_music_id") or entry.get("itunes_track_id"):
            entity_identifier["apple_music_id"] = str(
                entry.get("apple_music_id") or entry.get("itunes_track_id")
            )
        if entry.get("isrc"):
            entity_identifier["isrc"] = entry["isrc"]
        if cm_track:
            entity_identifier["chartmetric_id"] = cm_track

        return {
            "platform": "chartmetric",
            "entity_type": "track",
            "entity_identifier": entity_identifier,
            "raw_score": None,
            "rank": None,
            "snapshot_date": snapshot.isoformat(),
            "signals": {
                "source_platform": "artist_catalog",
                "chart_type": "catalog_discovery",
                "cm_track_id": cm_track,
                "cm_artist_id": cm_artist_id,
                "db_artist_uuid": db_artist_uuid,
                "genres": entry.get("track_genre") or entry.get("genre"),
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
                        "[artist-tracks] bulk: received=%d ingested=%d dupes=%d "
                        "errors=%d created=%d elapsed=%dms",
                        body.get("received", 0), body.get("ingested", 0),
                        body.get("duplicates", 0), body.get("errors", 0),
                        body.get("entities_created", 0), body.get("elapsed_ms", 0),
                    )
                else:
                    logger.error(
                        "[artist-tracks] bulk failed: HTTP %d %s",
                        resp.status_code, resp.text[:300],
                    )
            except httpx.HTTPError as exc:
                logger.error("[artist-tracks] bulk error: %s", exc)


async def _main() -> None:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [artist-tracks] %(message)s")
    scraper = ChartmetricArtistTracksScraper(
        credentials={"api_key": os.environ.get("CHARTMETRIC_API_KEY", "")},
        api_base_url=os.environ.get("SOUNDPULSE_API_URL", "http://localhost:8000"),
        admin_key=os.environ.get("API_ADMIN_KEY", ""),
    )
    stats = await scraper.run()
    print(stats)


if __name__ == "__main__":
    asyncio.run(_main())
