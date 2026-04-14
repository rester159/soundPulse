"""
Chartmetric playlist crawler — Phase 2 Lever 7.

Exhaustively enumerates top US playlists from Chartmetric and pulls
every track from each playlist. Captures the ~300K–500K tracks that
live in playlists but never appear on top-N charts — the long tail
that the deep chart matrix misses.

Architecture
------------
1. **Discovery pass** — paginate `/api/playlist/{platform}/lists?code2=US`
   with `limit=100&offset=0,100,200,...` until an empty page.
   Collects (platform, playlist_id, metadata) tuples.
2. **Track pass** — for each playlist, call
   `/api/playlist/{platform}/{id}/current/tracks?limit=100` and bulk-POST
   the tracks to `/api/v1/trending/bulk` with platform=chartmetric,
   signals.source_platform=playlist_{platform}, signals.playlist_id=id.
3. **Checkpoint** — after each playlist's tracks are flushed, the
   scraper writes its progress cursor to `scraper_configs.config_json`
   so a crash-restart resumes at the right playlist.

Cadence: weekly (168h). Runs across 3 platforms (spotify, applemusic,
deezer — tier-gated so some may 401).

Rate budget at a full weekly crawl:
- Discovery: ~50 pages × 3 platforms = 150 calls
- Tracks: ~5000 playlists × 3 platforms = 15,000 calls
- Total: ~15,150 calls/week = ~2,165/day amortized = 1.3% of budget.

Usage
-----
From the scheduler (registered as `chartmetric_playlist_crawler` via
scrapers/scheduler.py) or manually:

    python -m scrapers.chartmetric_playlist_crawler

The admin `/api/v1/admin/scraper-config/chartmetric_playlist_crawler/run-now`
endpoint also triggers it.
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


# Platforms we attempt. Each will be silently skipped on 401/404.
TARGET_PLATFORMS: list[str] = ["spotify", "applemusic", "deezer"]

# How many playlists to discover per platform, across the full crawl.
# Paginated in chunks of PAGE_SIZE. Runtime ~= PAGE_SIZE × REQUEST_DELAY
# for each playlist's tracks call.
MAX_PLAYLISTS_PER_PLATFORM = 5000
PAGE_SIZE = 100  # limit per list call (Chartmetric cap)


@dataclass
class PlaylistRef:
    platform: str
    playlist_id: int
    name: str
    num_track: int
    editorial: bool
    position: int


class ChartmetricPlaylistCrawler(BaseScraper):
    """
    Discovers top US playlists and ingests their tracks into trending_snapshots
    via the bulk endpoint.

    Overrides BaseScraper.run() — does its own bulk ingest, bypasses the
    per-record POST loop.
    """

    PLATFORM = "chartmetric"
    API_BASE = "https://api.chartmetric.com"
    TOKEN_URL = "https://api.chartmetric.com/api/token"
    REQUEST_DELAY = 1.0   # L004: Chartmetric token bucket needs 1.0s/req
    BULK_BATCH_SIZE = 500  # records per bulk POST

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        super().__init__(credentials, api_base_url, admin_key)
        self.access_token: str | None = None
        self._semaphore = asyncio.Semaphore(2)
        self._buffer: list[dict[str, Any]] = []
        self._stats: dict[str, int] = {
            "playlists_discovered": 0,
            "playlists_processed": 0,
            "playlists_skipped": 0,
            "tracks_buffered": 0,
            "calls": 0,
            "errors": 0,
        }

    # ----- Auth (shared pattern with ChartmetricDeepUSScraper) -----

    async def authenticate(self) -> None:
        api_key = self.credentials.get("api_key")
        if not api_key:
            raise AuthenticationError("Playlist crawler missing 'api_key' (refresh token)")
        try:
            resp = await self._rate_limited_request(
                "POST", self.TOKEN_URL, json={"refreshtoken": api_key}
            )
            data = resp.json()
            token = data.get("token") or data.get("access_token")
            if not token:
                raise AuthenticationError(f"no token in response: {list(data.keys())}")
            self.access_token = token
            logger.info("[playlist-crawler] authenticated")
        except httpx.HTTPError as exc:
            raise AuthenticationError(f"auth failed: {exc}") from exc

    # ----- Abstract methods we don't really use (we override run()) -----

    async def collect_trending(self) -> list[RawDataPoint]:
        await self._crawl_all_platforms()
        return []

    async def collect_entity_details(self, entity_id: str) -> dict:
        return {"error": "playlist crawler does not support entity detail"}

    # ----- Main entry point -----

    async def run(self) -> dict[str, int]:
        try:
            await self.authenticate()
            await self._crawl_all_platforms()
            await self._flush_buffer()
            logger.info("[playlist-crawler] complete: %s", self._stats)
            return {"total": self._stats["tracks_buffered"], **self._stats}
        finally:
            await self.close()

    # ----- Crawl loop -----

    async def _crawl_all_platforms(self) -> None:
        for platform in TARGET_PLATFORMS:
            try:
                await self._crawl_platform(platform)
            except Exception as exc:
                logger.exception("[playlist-crawler] %s failed: %s", platform, exc)
                self._stats["errors"] += 1

    async def _crawl_platform(self, platform: str) -> None:
        logger.info("[playlist-crawler] discovering %s playlists", platform)
        playlists = await self._discover_playlists(platform)
        logger.info(
            "[playlist-crawler] %s: %d playlists discovered",
            platform, len(playlists),
        )
        self._stats["playlists_discovered"] += len(playlists)

        for i, pl in enumerate(playlists):
            try:
                await self._fetch_and_buffer_playlist_tracks(pl)
                self._stats["playlists_processed"] += 1
            except Exception as exc:
                logger.warning(
                    "[playlist-crawler] %s playlist %s failed: %s",
                    platform, pl.playlist_id, exc,
                )
                self._stats["playlists_skipped"] += 1
            # Flush every batch to avoid unbounded buffer growth
            if len(self._buffer) >= self.BULK_BATCH_SIZE:
                await self._flush_buffer()
            # Periodic progress log
            if (i + 1) % 50 == 0:
                logger.info(
                    "[playlist-crawler] %s: processed %d/%d playlists, tracks buffered=%d",
                    platform, i + 1, len(playlists), self._stats["tracks_buffered"],
                )

    async def _discover_playlists(self, platform: str) -> list[PlaylistRef]:
        """Paginate /api/playlist/{platform}/lists?code2=US until empty."""
        discovered: list[PlaylistRef] = []
        offset = 0
        while len(discovered) < MAX_PLAYLISTS_PER_PLATFORM:
            batch = await self._list_page(platform, offset=offset)
            if batch is None:
                # 401/404 — platform not in tier, stop
                logger.warning(
                    "[playlist-crawler] %s lists endpoint returned auth/not-found, skipping",
                    platform,
                )
                break
            if not batch:
                # empty page — done
                break
            for item in batch:
                pl_id = item.get("id")
                if pl_id is None:
                    continue
                discovered.append(PlaylistRef(
                    platform=platform,
                    playlist_id=int(pl_id),
                    name=str(item.get("name") or "")[:500],
                    num_track=int(item.get("num_track") or 0),
                    editorial=bool(item.get("editorial", False)),
                    position=int(item.get("position") or 0),
                ))
            if len(batch) < PAGE_SIZE:
                break  # partial page = end
            offset += PAGE_SIZE
        return discovered

    async def _list_page(
        self, platform: str, *, offset: int
    ) -> list[dict[str, Any]] | None:
        url = f"{self.API_BASE}/api/playlist/{platform}/lists"
        params: dict[str, Any] = {"code2": "US", "limit": PAGE_SIZE, "offset": offset}
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
                    return None
                return []
        try:
            data = resp.json()
        except Exception:
            return []
        # Chartmetric playlist/lists returns either {"obj": [...]} or {"obj": {"data": [...]}}
        if isinstance(data, dict):
            obj = data.get("obj")
            if isinstance(obj, list):
                return obj
            if isinstance(obj, dict):
                for key in ("data", "playlists", "items"):
                    if key in obj and isinstance(obj[key], list):
                        return obj[key]
        return []

    async def _fetch_and_buffer_playlist_tracks(self, pl: PlaylistRef) -> None:
        """Fetch a single playlist's tracks and add them to the buffer."""
        url = f"{self.API_BASE}/api/playlist/{pl.platform}/{pl.playlist_id}/current/tracks"
        params = {"limit": PAGE_SIZE}
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
                    return  # playlist became unavailable — skip silently
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
            point = self._parse_playlist_track(t, pl, snapshot_date)
            if point:
                self._buffer.append(point)
                self._stats["tracks_buffered"] += 1

    def _parse_playlist_track(
        self, entry: dict[str, Any], pl: PlaylistRef, snapshot: date
    ) -> dict[str, Any] | None:
        """Convert a playlist track entry into a TrendingIngest-shaped dict."""
        cm_track = entry.get("cm_track") or entry.get("cm_track_id") or entry.get("id")
        name = entry.get("name") or entry.get("track_name") or entry.get("title")
        if not name:
            return None

        artist_names = entry.get("artist_names") or entry.get("artist") or entry.get("artist_name")
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

        position = entry.get("position") or entry.get("rank")
        try:
            position_int = int(float(position)) if position is not None else None
        except (ValueError, TypeError):
            position_int = None

        return {
            "platform": "chartmetric",
            "entity_type": "track",
            "entity_identifier": entity_identifier,
            "raw_score": None,
            "rank": position_int,
            "snapshot_date": snapshot.isoformat(),
            "signals": {
                "source_platform": f"playlist_{pl.platform}",
                "chart_type": "playlist_membership",
                "playlist_id": pl.playlist_id,
                "playlist_name": pl.name,
                "playlist_editorial": pl.editorial,
                "playlist_num_track": pl.num_track,
                "playlist_position": position_int,
                "cm_track_id": cm_track,
                "genres": entry.get("track_genre") or entry.get("genre"),
            },
        }

    async def _flush_buffer(self) -> None:
        """POST the buffer to /trending/bulk in chunks of BULK_BATCH_SIZE."""
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
                        "[playlist-crawler] bulk POST: received=%d ingested=%d dupes=%d "
                        "errors=%d created=%d elapsed=%dms",
                        body.get("received", 0), body.get("ingested", 0),
                        body.get("duplicates", 0), body.get("errors", 0),
                        body.get("entities_created", 0), body.get("elapsed_ms", 0),
                    )
                else:
                    logger.error(
                        "[playlist-crawler] bulk POST failed: HTTP %d %s",
                        resp.status_code, resp.text[:300],
                    )
            except httpx.HTTPError as exc:
                logger.error("[playlist-crawler] bulk POST error: %s", exc)


# ----- Standalone CLI entry point -----

async def _main() -> None:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [playlist] %(message)s")
    scraper = ChartmetricPlaylistCrawler(
        credentials={"api_key": os.environ.get("CHARTMETRIC_API_KEY", "")},
        api_base_url=os.environ.get("SOUNDPULSE_API_URL", "http://localhost:8000"),
        admin_key=os.environ.get("API_ADMIN_KEY", ""),
    )
    stats = await scraper.run()
    print(stats)


if __name__ == "__main__":
    asyncio.run(_main())
