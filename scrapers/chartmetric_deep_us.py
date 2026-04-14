"""
Deep US Chartmetric scraper — exhausts the paid-tier API for US data.

Implements the MECE definition in PRD §7.2 "Chartmetric Deep US Coverage."
The endpoint matrix below is built from the official Chartmetric API
documentation (api.chartmetric.com/apidoc) cross-referenced against the
musicfox/pycmc client and the Mixture Labs chartmetric-cli reference.

Designed to work alongside (not replace) `scrapers/chartmetric.py`. The
existing scraper keeps running on its 4-hour cadence; this one is invoked
for backfills and the periodic deep refresh.

Architecture
------------
- Authenticates once (refresh-token → bearer)
- Iterates a deterministic ENDPOINT_MATRIX (the MECE space)
- Per-genre endpoints fan out across the platform-specific genre list
- Weekday-restricted endpoints (Thursday/Friday-only weekly charts) snap
  the requested date to the most recent valid weekday
- Buffers parsed records into batches of `BULK_BATCH_SIZE`
- POSTs each batch to `/api/v1/trending/bulk`
- Tracks per-endpoint success/empty/error counts
- Respects 2 req/sec Chartmetric rate limit via `REQUEST_DELAY` and a semaphore

The matrix is partitioned into three sections:
  1. CONFIRMED — endpoints documented in the official apidoc and known to work
  2. PER_GENRE_ENDPOINTS — confirmed but expanded across genre strings at runtime
  3. ENRICHMENT — per-entity calls (artists, tracks, cities) — separate execution lane

Run `scripts/chartmetric_probe.py` first to verify tier access (some
audience-demographic endpoints are sold as add-ons) and to discover the
numeric Chartmetric city IDs for US cities.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import httpx

from scrapers.base import AuthenticationError, BaseScraper, RateLimitError, RawDataPoint


def _primary_cm_artist_id(value: Any) -> int | None:
    """
    Normalize Chartmetric's cm_artist field to a single integer ID.

    Chartmetric returns `cm_artist` as a list when a track has multiple
    artists (featured artists, etc.). Downstream code, SQL casts
    (`::bigint`), and artist-level stats lookups all expect a scalar, so
    we take the primary (first) ID. Accepts scalar int, scalar str,
    list, or None.
    """
    if value is None:
        return None
    if isinstance(value, list):
        if not value:
            return None
        value = value[0]
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

logger = logging.getLogger(__name__)


# ---------- Genre lists per platform (from Chartmetric apidoc) ----------

APPLE_MUSIC_GENRES = [
    "All Genres", "Pop", "Hip-Hop/Rap", "Country", "R&B/Soul", "Dance",
    "Rock", "Alternative", "Christian & Gospel", "Latin", "Electronic",
    "Jazz", "Classical", "Soundtrack", "Reggae", "World", "Blues",
    "Children's Music", "K-Pop", "J-Pop", "Singer/Songwriter",
    "Easy Listening", "Fitness & Workout", "Disney",
]

# Amazon shares Apple's genre taxonomy
AMAZON_GENRES = APPLE_MUSIC_GENRES

ITUNES_GENRES = APPLE_MUSIC_GENRES

SOUNDCLOUD_GENRES = [
    "all-music", "rock", "house", "pop", "hip-hop-rap", "electronic",
    "indie", "r-b-soul", "country", "latin",
]

BEATPORT_GENRES = [
    "top-100", "house", "tech-house", "drum-and-bass", "techno", "trance",
    "deep-house", "progressive-house", "dubstep", "minimal", "electronica",
    "breaks", "hardcore", "hard-dance",
]

SHAZAM_GENRES = ["alternative", "rock", "house", "pop"]


# ---------- Endpoint definition ----------

@dataclass
class ChartEndpoint:
    """One concrete chart endpoint to fetch."""
    source_platform: str          # spotify, apple_music, tiktok, ...
    chart_type: str               # regional, viral, top, popular_track, ...
    path: str                     # URL path under api.chartmetric.com
    params: dict[str, Any] = field(default_factory=dict)  # static query params
    entity_type: str = "track"    # "track" or "artist"
    country_param: str | None = "country_code"  # the country param name (None = no country)
    country_value: str = "us"     # "us" or "US" — Chartmetric is mostly case-insensitive
    weekday: str | None = None    # None | "thursday" | "friday" — date snap
    genre_loop: list[str] | None = None  # if set, fan out across these genre strings
    genre_param: str | None = None       # param name for the genre value
    confirmed: bool = True        # False = speculative; failures are silent
    # Phase 1 lever 3: offset pagination. Chartmetric chart endpoints return
    # a fixed page size (typically 50 for Spotify, 100-200 for others).
    # Setting depth_pages > 1 makes _fetch_one iterate offset=0, 50, 100, ...
    # to reach deeper into the chart. Only Spotify regional/viral support
    # this — other platforms cap their own depth below what pagination
    # can reach. Set to 4 on spotify regional charts → top 200 instead of top 50.
    depth_pages: int = 1
    page_size: int = 50           # items per page (used for offset increment)
    notes: str = ""


# ---------- ENDPOINT MATRIX (MECE — verified against Chartmetric apidoc) ----------

ENDPOINT_MATRIX: list[ChartEndpoint] = [
    # ========== Spotify tracks (daily) ==========
    # Phase 1 L3: regional charts paginate to depth 4 (top 200 items total
    # via offset=0,50,100,150). Viral caps at 50 by Spotify's own design.
    ChartEndpoint("spotify", "regional_daily", "/api/charts/spotify",
                  params={"type": "regional", "interval": "daily"},
                  depth_pages=4),
    ChartEndpoint("spotify", "viral_daily",    "/api/charts/spotify",
                  params={"type": "viral",    "interval": "daily"}),

    # ========== Spotify tracks (weekly) ==========
    ChartEndpoint("spotify", "regional_weekly", "/api/charts/spotify",
                  params={"type": "regional", "interval": "weekly"},
                  depth_pages=4),
    ChartEndpoint("spotify", "viral_weekly",    "/api/charts/spotify",
                  params={"type": "viral",    "interval": "weekly"}),

    # ========== Spotify artists (5 type variants) ==========
    # CORRECTION 2026-04-11: /api/charts/spotify/artists is a GLOBAL chart,
    # not country-filtered — rejects country_code. Also requires `interval`.
    # Weekly is the baseline that works. Dropping country_param entirely.
    ChartEndpoint("spotify", "artists_monthly_listeners", "/api/charts/spotify/artists",
                  params={"type": "monthly_listeners", "interval": "weekly"},
                  entity_type="artist", country_param=None),
    ChartEndpoint("spotify", "artists_popularity",         "/api/charts/spotify/artists",
                  params={"type": "popularity",         "interval": "weekly"},
                  entity_type="artist", country_param=None),
    ChartEndpoint("spotify", "artists_followers",          "/api/charts/spotify/artists",
                  params={"type": "followers",          "interval": "weekly"},
                  entity_type="artist", country_param=None),
    ChartEndpoint("spotify", "artists_playlist_count",     "/api/charts/spotify/artists",
                  params={"type": "playlist_count",     "interval": "weekly"},
                  entity_type="artist", country_param=None),
    ChartEndpoint("spotify", "artists_playlist_reach",     "/api/charts/spotify/artists",
                  params={"type": "playlist_reach",     "interval": "weekly"},
                  entity_type="artist", country_param=None),

    # ========== Spotify Fresh Find (Thursday-only editorial new music) ==========
    ChartEndpoint("spotify", "freshfind", "/api/charts/spotify/freshfind",
                  params={}, country_param=None, weekday="thursday"),

    # ========== Apple Music tracks per genre ==========
    # CORRECTION 2026-04-11: per Skylar + live test — Apple Music tracks uses
    # `type=top` query param. `type=daily` is NOT valid (API responds
    # "'type' must be [top]"). Only ONE variant supported. Also: genre
    # must be a specific name like "Pop", not "All Genres".
    ChartEndpoint("apple_music", "tracks_top_per_genre", "/api/charts/applemusic/tracks",
                  params={"type": "top"},
                  genre_loop=APPLE_MUSIC_GENRES, genre_param="genre"),

    # ========== Apple Music albums + videos ==========
    # PROBE 2026-04-11: albums_per_genre returned OK 200 with 200 items.
    # Promoted to confirmed=True. videos returned EMPTY 200 — endpoint exists,
    # just no items right now. Promoted too.
    ChartEndpoint("apple_music", "albums_per_genre", "/api/charts/applemusic/albums",
                  params={},
                  genre_loop=APPLE_MUSIC_GENRES, genre_param="genre"),
    ChartEndpoint("apple_music", "videos", "/api/charts/applemusic/videos",
                  params={}),

    # ========== iTunes ==========
    # PROBE 2026-04-11: all 3 variants confirmed working. tracks_per_genre
    # was rate-limited on first probe; the re-probe at 2.0s/req returned OK.
    ChartEndpoint("itunes", "tracks_per_genre", "/api/charts/itunes/tracks",
                  params={},
                  genre_loop=ITUNES_GENRES, genre_param="genre"),
    ChartEndpoint("itunes", "albums_per_genre", "/api/charts/itunes/albums",
                  params={},
                  genre_loop=ITUNES_GENRES, genre_param="genre"),
    ChartEndpoint("itunes", "videos", "/api/charts/itunes/videos",
                  params={}),

    # ========== Amazon Music (uses code2 not country_code) ==========
    # CORRECTION 2026-04-11: applying the same `type=` pattern as Apple Music
    # (per Skylar's email — insight= was wrong for Apple, likely wrong for
    # Amazon too). Will confirm via re-probe. Also trying code2=US uppercase.
    ChartEndpoint("amazon", "tracks_popular_per_genre", "/api/charts/amazon/tracks",
                  params={"type": "popular_track"},
                  country_param="code2", country_value="US",
                  genre_loop=AMAZON_GENRES, genre_param="genre"),
    ChartEndpoint("amazon", "tracks_new_per_genre", "/api/charts/amazon/tracks",
                  params={"type": "new_track"},
                  country_param="code2", country_value="US",
                  genre_loop=AMAZON_GENRES, genre_param="genre"),
    ChartEndpoint("amazon", "albums_popular_per_genre", "/api/charts/amazon/albums",
                  params={"type": "popular_album"},
                  country_param="code2", country_value="US",
                  genre_loop=AMAZON_GENRES, genre_param="genre"),
    ChartEndpoint("amazon", "albums_new_per_genre", "/api/charts/amazon/albums",
                  params={"type": "new_album"},
                  country_param="code2", country_value="US",
                  genre_loop=AMAZON_GENRES, genre_param="genre"),

    # ========== Shazam ==========
    ChartEndpoint("shazam", "top_us", "/api/charts/shazam", params={}),
    ChartEndpoint("shazam", "top_us_per_genre", "/api/charts/shazam",
                  params={},
                  genre_loop=SHAZAM_GENRES, genre_param="genre"),

    # ========== TikTok (path sub-resources per Skylar @ Chartmetric 2026-04-03) ==========
    # CORRECTION 2026-04-11: TikTok is IN the user's plan. Skylar confirmed
    # via email that the 401 was a path issue, not a tier block.
    # Live tests discovered: TikTok charts are GLOBAL, NOT country-filtered —
    # rejects country_code entirely. Also: users sub-resource returns 500
    # with various param shapes — skipping for now. top-tracks is a genuine
    # 401 (different internal endpoint). Keeping /tracks and /videos which
    # both return 100 items.
    ChartEndpoint("tiktok", "tracks_weekly", "/api/charts/tiktok/tracks",
                  params={"interval": "weekly"}, country_param=None),
    ChartEndpoint("tiktok", "videos_weekly", "/api/charts/tiktok/videos",
                  params={"interval": "weekly"}, country_param=None),
    # Users sub-resource is broken — needs more investigation. See P1-080.
    ChartEndpoint("tiktok", "users_likes", "/api/charts/tiktok/users",
                  params={"user_chart_type": "likes", "interval": "weekly"},
                  entity_type="artist", country_param=None,
                  confirmed=False, notes="500 internal — users sub-resource quirks"),
    ChartEndpoint("tiktok", "users_followers", "/api/charts/tiktok/users",
                  params={"user_chart_type": "followers", "interval": "weekly"},
                  entity_type="artist", country_param=None,
                  confirmed=False, notes="500 internal — users sub-resource quirks"),

    # ========== TikTok top tracks (separate endpoint) ==========
    # Genuine 401 TIER — different internal endpoint, not the public API.
    ChartEndpoint("tiktok", "top_tracks", "/api/charts/tiktok/top-tracks",
                  params={"limit": 200}, country_param=None,
                  confirmed=False, notes="401 — different internal endpoint, not public"),

    # ========== YouTube (Thursday-only weekly) ==========
    # PROBE 2026-04-11: all 4 endpoints work (trends returned 30 items, the
    # other 3 returned EMPTY 200 — endpoint exists, just no data on the
    # specific Thursday tested).
    ChartEndpoint("youtube", "tracks", "/api/charts/youtube/tracks",
                  params={}, weekday="thursday"),
    ChartEndpoint("youtube", "artists", "/api/charts/youtube/artists",
                  params={}, weekday="thursday", entity_type="artist"),
    ChartEndpoint("youtube", "videos", "/api/charts/youtube/videos",
                  params={}, weekday="thursday"),
    ChartEndpoint("youtube", "trends", "/api/charts/youtube/trends",
                  params={}, weekday="thursday"),

    # ========== SoundCloud (Friday-only weekly, per-genre) ==========
    # CORRECTION 2026-04-11: live test confirmed `kind=top` / `kind=trending`
    # is the right param name (NOT `type=`). The doc agent was right about
    # kind. The first probe's 400 was because we passed an invalid genre.
    # Using `country_code=US` (uppercase) + `kind=top/trending` + genre fan-out.
    ChartEndpoint("soundcloud", "top_per_genre", "/api/charts/soundcloud",
                  params={"kind": "top"},
                  weekday="friday", country_value="US",
                  genre_loop=SOUNDCLOUD_GENRES, genre_param="genre"),
    ChartEndpoint("soundcloud", "trending_per_genre", "/api/charts/soundcloud",
                  params={"kind": "trending"},
                  weekday="friday", country_value="US",
                  genre_loop=SOUNDCLOUD_GENRES, genre_param="genre"),

    # ========== Deezer (US signal weak but cheap to pull) ==========
    # PROBE 2026-04-11: returned OK with 100 items.
    ChartEndpoint("deezer", "top", "/api/charts/deezer/", params={}),

    # ========== Beatport (electronic only, Friday weekly, no country) ==========
    # PROBE 2026-04-11: returned OK with 100 items.
    ChartEndpoint("beatport", "per_genre", "/api/charts/beatport",
                  params={},
                  country_param=None, weekday="friday",
                  genre_loop=BEATPORT_GENRES, genre_param="genre"),

    # ========== Twitch (music streamers — niche) ==========
    # PROBE 2026-04-11: both returned 401 TIER — not in user's plan.
    ChartEndpoint("twitch", "followers_daily", "/api/charts/twitch",
                  params={"type": "followers",    "duration": "daily", "limit": 200},
                  country_param=None, entity_type="artist",
                  confirmed=False, notes="401 TIER"),
    ChartEndpoint("twitch", "viewer_hours_daily", "/api/charts/twitch",
                  params={"type": "viewer_hours", "duration": "daily", "limit": 200},
                  country_param=None, entity_type="artist",
                  confirmed=False, notes="401 TIER"),

    # ========== Airplay (US RADIO) ==========
    # PROBE 2026-04-11: ALL 5 airplay endpoints returned 401 TIER. Radio data
    # is sold as an add-on. Confirm with Chartmetric what unlocks it. Worth
    # the upgrade — radio is a unique signal not available anywhere else.
    ChartEndpoint("radio", "airplay_monthly_listeners", "/api/charts/airplay",
                  params={"type": "monthly_listeners", "duration": "daily", "limit": 500},
                  entity_type="artist", confirmed=False, notes="401 TIER — radio add-on"),
    ChartEndpoint("radio", "airplay_popularity", "/api/charts/airplay",
                  params={"type": "popularity",         "duration": "daily", "limit": 500},
                  entity_type="artist", confirmed=False, notes="401 TIER — radio add-on"),
    ChartEndpoint("radio", "airplay_followers", "/api/charts/airplay",
                  params={"type": "followers",          "duration": "daily", "limit": 500},
                  entity_type="artist", confirmed=False, notes="401 TIER — radio add-on"),
    ChartEndpoint("radio", "airplay_playlist_count", "/api/charts/airplay",
                  params={"type": "playlist_count",     "duration": "daily", "limit": 500},
                  entity_type="artist", confirmed=False, notes="401 TIER — radio add-on"),
    ChartEndpoint("radio", "airplay_playlist_reach", "/api/charts/airplay",
                  params={"type": "playlist_reach",     "duration": "daily", "limit": 500},
                  entity_type="artist", confirmed=False, notes="401 TIER — radio add-on"),
]


# ---------- Date helpers ----------

def _snap_to_weekday(target: date, weekday_name: str) -> date:
    """
    Return the most recent date <= target that falls on the given weekday.

    Chartmetric YouTube/Fresh Find data only exists for Thursdays; SoundCloud
    and Beatport only for Fridays. Calling them with another date returns 404.
    """
    weekday_index = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }[weekday_name.lower()]
    delta = (target.weekday() - weekday_index) % 7
    return target - timedelta(days=delta)


# ---------- SCRAPER ----------

class ChartmetricDeepUSScraper(BaseScraper):
    """
    Comprehensive US-only Chartmetric scraper.

    Use the existing `ChartmetricScraper` for the small daily live cadence
    (every 4h). Use this one for the heavy backfill and the periodic deep
    refresh — it POSTs to `/api/v1/trending/bulk` with batches of records.
    """

    PLATFORM = "chartmetric"
    API_BASE = "https://api.chartmetric.com"
    TOKEN_URL = "https://api.chartmetric.com/api/token"
    # L004 (logged 2026-04-11, applied 2026-04-14 after rate-limit failures):
    # Chartmetric's "2 req/sec" headline is enforced via a tighter token
    # bucket. At 0.55s (≈1.8 req/sec) the deep scraper reliably hit 429
    # cascades that failed the whole run. 1.0s/req (1 rps) is the safer
    # steady-state. Slower backfills, zero 429 noise.
    REQUEST_DELAY = 1.0
    # If we hit a 429 mid-run, back off to this slower rate for the rest
    # of the run. Token bucket is empty, pushing harder just refills our
    # retry counter instead of our request count.
    REQUEST_DELAY_AFTER_THROTTLE = 2.0
    # The base class defaults to 5 retries on 429. Chartmetric's token
    # bucket can stay empty for 20+ seconds under bursty loads, and 5
    # retries with a 5s Retry-After = ~25s of waiting, not enough. Bump
    # to 10 so we survive a full 60s throttle window.
    MAX_RETRIES = 10
    BULK_BATCH_SIZE = 500    # records per bulk POST
    DATE_LOOKBACK_DAYS = 3   # try date → date-N if a chart has no data yet

    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        super().__init__(credentials, api_base_url, admin_key)
        self.access_token: str | None = None
        self._semaphore = asyncio.Semaphore(2)
        self._stats: dict[str, dict[str, int]] = {}  # per-endpoint counters
        self._buffer: list[dict[str, Any]] = []      # bulk-ingest staging buffer
        # Adaptive throttle: once True, stays True for the rest of the run.
        # Flipped by _on_throttle() when any request surfaces a 429.
        self._throttled = False

    def _current_delay(self) -> float:
        """Sleep duration between requests, adjusted for adaptive throttle."""
        return self.REQUEST_DELAY_AFTER_THROTTLE if self._throttled else self.REQUEST_DELAY

    def _on_throttle(self) -> None:
        """Mark this run as throttled so subsequent requests slow down."""
        if not self._throttled:
            logger.warning(
                "[%s-deep-us] 429 observed — switching to slow rate (%.2fs/req) "
                "for the rest of this run",
                self.PLATFORM, self.REQUEST_DELAY_AFTER_THROTTLE,
            )
            self._throttled = True

    # ----- Auth -----

    async def authenticate(self) -> None:
        api_key = self.credentials.get("api_key")
        if not api_key:
            raise AuthenticationError("Chartmetric credentials missing 'api_key' (refresh token)")
        try:
            resp = await self._rate_limited_request(
                "POST", self.TOKEN_URL, json={"refreshtoken": api_key},
            )
            data = resp.json()
            token = data.get("token") or data.get("access_token")
            if not token:
                raise AuthenticationError(f"Chartmetric token response missing 'token': {list(data.keys())}")
            self.access_token = token
            logger.info("[%s-deep-us] Authenticated", self.PLATFORM)
        except httpx.HTTPError as exc:
            raise AuthenticationError(f"Chartmetric auth failed: {exc}") from exc

    # ----- Live deep refresh (called by the scheduler periodically) -----

    async def collect_trending(self) -> list[RawDataPoint]:
        """
        Pulls today's data across the entire ENDPOINT_MATRIX once.

        Returns an empty list — this scraper does its own bulk ingest, so
        the BaseScraper.run() per-record POST loop is bypassed by overriding
        run() below.
        """
        if not self.access_token:
            raise AuthenticationError("Must authenticate first")
        target_date = date.today() - timedelta(days=1)  # Chartmetric data lags ~1 day
        await self._fetch_and_buffer_for_date(target_date)
        return []

    async def collect_entity_details(self, entity_id: str) -> dict:
        """Track-level detail call. Used for enrichment passes."""
        if not self.access_token:
            raise AuthenticationError("Must authenticate first")
        url = f"{self.API_BASE}/api/track/{entity_id}"
        async with self._semaphore:
            await asyncio.sleep(self._current_delay())
            try:
                resp = await self._rate_limited_request(
                    "GET", url, headers={"Authorization": f"Bearer {self.access_token}"},
                )
                return resp.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    self._on_throttle()
                return {"error": str(exc), "entity_id": entity_id}
            except httpx.HTTPError as exc:
                return {"error": str(exc), "entity_id": entity_id}

    async def run(self) -> dict[str, int]:
        """
        Override BaseScraper.run() — uses the bulk ingest path instead of
        the per-record POST loop. Returns aggregate counts.
        """
        try:
            await self.authenticate()
            await self.collect_trending()
            await self._flush_buffer()
            totals = self._aggregate_stats()
            logger.info("[%s-deep-us] Run complete: %s", self.PLATFORM, totals)
            return totals
        finally:
            await self.close()

    # ----- Backfill entry point -----

    async def backfill(self, start_date: date, end_date: date) -> dict[str, int]:
        """Pull every endpoint × every date in [start_date, end_date]."""
        await self.authenticate()
        try:
            current = start_date
            day_count = 0
            while current <= end_date:
                await self._fetch_and_buffer_for_date(current)
                day_count += 1
                if day_count % 5 == 0:
                    logger.info("[%s-deep-us] Backfilled %d days, current=%s",
                                self.PLATFORM, day_count, current.isoformat())
                    await self._flush_buffer()
                current += timedelta(days=1)
            await self._flush_buffer()
            return self._aggregate_stats()
        finally:
            await self.close()

    # ----- Internals -----

    async def _fetch_and_buffer_for_date(self, target: date) -> None:
        """Fetch every endpoint in the matrix for a given date, buffer the results."""
        for ep in ENDPOINT_MATRIX:
            # Snap weekday-restricted endpoints to the most recent valid weekday
            ep_date = _snap_to_weekday(target, ep.weekday) if ep.weekday else target

            if ep.genre_loop:
                # Fan out across the genre list
                for genre_value in ep.genre_loop:
                    await self._fetch_one(ep, ep_date, genre_value=genre_value)
            else:
                await self._fetch_one(ep, ep_date)

    async def _fetch_one(
        self, ep: ChartEndpoint, target: date, genre_value: str | None = None
    ) -> None:
        """Fetch a single chart slice and buffer the parsed records.

        Phase 1 L3: if ep.depth_pages > 1, paginate within a successful date
        by calling the endpoint repeatedly with offset=0, page_size, 2*page_size, ...
        Stops early on a partial page or empty response.
        """
        key = f"{ep.source_platform}/{ep.chart_type}" + (f"/{genre_value}" if genre_value else "")
        stats = self._stats.setdefault(key, {"calls": 0, "entries": 0, "empty": 0, "errors": 0})

        # For non-weekday endpoints we try the requested date then a few back
        # For weekday-snapped endpoints we use the snapped date directly
        attempt_dates: list[str]
        if ep.weekday:
            attempt_dates = [target.isoformat()]
        else:
            attempt_dates = [
                (target - timedelta(days=d)).isoformat()
                for d in range(self.DATE_LOOKBACK_DAYS)
            ]

        for attempt_date in attempt_dates:
            # First call at offset=0 to see if this date has data
            stats["calls"] += 1
            first_entries = await self._request_chart(
                ep, attempt_date, offset=0, genre_value=genre_value
            )
            if first_entries is None:  # 401/403/404 — endpoint not available, give up
                stats["errors"] += 1
                return
            if not first_entries:
                continue  # try next date in the fallback list

            # We have data for this date — parse the first page and paginate if needed
            all_entries = list(first_entries)

            # Paginate additional pages (if the endpoint supports depth and we got
            # a full first page — partial first page means the chart was shorter
            # than page_size and there's nothing more).
            if ep.depth_pages > 1 and len(first_entries) >= ep.page_size:
                for page_num in range(1, ep.depth_pages):
                    stats["calls"] += 1
                    offset_val = page_num * ep.page_size
                    page_entries = await self._request_chart(
                        ep, attempt_date, offset=offset_val, genre_value=genre_value
                    )
                    if page_entries is None or not page_entries:
                        break  # no more pages
                    all_entries.extend(page_entries)
                    if len(page_entries) < ep.page_size:
                        break  # partial page = end of chart

            buffered = 0
            for entry in all_entries:
                point = self._parse_entry(entry, ep, target, genre_value=genre_value)
                if point:
                    self._buffer.append(point)
                    buffered += 1
            stats["entries"] += buffered
            if len(self._buffer) >= self.BULK_BATCH_SIZE:
                await self._flush_buffer()
            return  # success on this date — done
        stats["empty"] += 1

    async def _request_chart(
        self,
        ep: ChartEndpoint,
        chart_date: str,
        *,
        offset: int = 0,
        genre_value: str | None = None,
    ) -> list[dict[str, Any]] | None:
        """Returns parsed list, [] if no data, or None on auth/permission failure.

        Phase 1 L3: `offset` is passed to Chartmetric for pagination. 0 is
        the first page; 50/100/150 reach deeper into Spotify's top-200 on
        the regional charts.
        """
        url = f"{self.API_BASE}{ep.path}"
        params: dict[str, Any] = {"date": chart_date}
        if ep.country_param:
            params[ep.country_param] = ep.country_value
        if genre_value and ep.genre_param:
            params[ep.genre_param] = genre_value
        if offset > 0:
            params["offset"] = offset
        params.update(ep.params or {})

        async with self._semaphore:
            await asyncio.sleep(self._current_delay())
            try:
                resp = await self._rate_limited_request(
                    "GET", url,
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    params=params,
                )
            except RateLimitError:
                # Exhausted all retries against the Chartmetric token
                # bucket on this endpoint. Trip adaptive throttle for
                # the rest of the run and skip this endpoint instead of
                # killing the whole scraper run (which is what happened
                # on 2026-04-14 — L004 manifesting).
                self._on_throttle()
                logger.warning(
                    "[%s-deep-us] rate-limit exhausted on %s (genre=%s) — "
                    "skipping, continuing run at slow rate",
                    self.PLATFORM, ep.chart_type, genre_value,
                )
                return []
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                if code == 429:
                    # Token bucket empty. Trip the adaptive throttle so
                    # the rest of this run runs at REQUEST_DELAY_AFTER_THROTTLE.
                    self._on_throttle()
                    return []
                if code in (401, 403, 404):
                    if ep.confirmed:
                        logger.warning("[%s-deep-us] %s %s on confirmed endpoint %s genre=%s",
                                       self.PLATFORM, code, ep.path, ep.chart_type, genre_value)
                    else:
                        logger.debug("[%s-deep-us] speculative %s %s -> %d (skipping)",
                                     self.PLATFORM, ep.source_platform, ep.chart_type, code)
                    return None
                if 500 <= code < 600:
                    return []
                return None

        try:
            data = resp.json()
        except Exception:
            return []

        # Chartmetric wraps chart data in obj.data; fall back to common keys
        if isinstance(data, dict):
            obj = data.get("obj")
            if isinstance(obj, dict) and "data" in obj:
                return obj["data"] or []
            for k in ("data", "charts", "tracks", "results", "items"):
                if k in data and isinstance(data[k], list):
                    return data[k]
        if isinstance(data, list):
            return data
        return []

    def _parse_entry(
        self,
        entry: dict[str, Any],
        ep: ChartEndpoint,
        snapshot: date,
        genre_value: str | None = None,
    ) -> dict[str, Any] | None:
        """Convert a Chartmetric entry into a TrendingIngest-shaped dict."""
        cm_track_id = entry.get("cm_track") or entry.get("cm_track_id") or entry.get("id")
        # Chartmetric returns cm_artist as a list when a track has multiple
        # artists (featured artists). Normalize to the primary (first) ID so
        # downstream code and SQL casts never see a JSON array.
        cm_artist_id = _primary_cm_artist_id(entry.get("cm_artist") or entry.get("cm_artist_id"))

        # Track or artist?
        if ep.entity_type == "artist":
            name = entry.get("name") or entry.get("artist_name")
            if not name:
                return None
            entity_identifier: dict[str, Any] = {
                "title": None,
                "artist_name": name,
            }
            if entry.get("spotify_artist_id"):
                entity_identifier["artist_spotify_id"] = entry["spotify_artist_id"]
            if cm_artist_id:
                entity_identifier["chartmetric_id"] = cm_artist_id
            entity_type = "artist"
            # An artist needs at least a name; remove the None title to satisfy schema
            entity_identifier.pop("title", None)
        else:
            name = entry.get("name") or entry.get("track_name") or entry.get("title")
            if not name:
                return None
            artist_names = entry.get("artist_names") or entry.get("artist_name") or entry.get("artist")
            if isinstance(artist_names, list):
                artist_name = ", ".join(str(a) for a in artist_names)
            else:
                artist_name = artist_names
            entity_identifier = {
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
            entity_type = "track"

        rank = entry.get("rank") or entry.get("position") or entry.get("chart_position")
        try:
            rank_int = int(float(rank)) if rank is not None else None
        except (ValueError, TypeError):
            rank_int = None

        spotify_pop = entry.get("spotify_popularity")
        if spotify_pop is not None:
            raw_score: float | None = float(spotify_pop)
        elif rank_int is not None:
            raw_score = max(0.0, 1000.0 - rank_int)
        else:
            raw_score = None

        return {
            "platform": "chartmetric",
            "entity_type": entity_type,
            "entity_identifier": entity_identifier,
            "raw_score": raw_score,
            "rank": rank_int,
            "snapshot_date": snapshot.isoformat(),
            "signals": {
                "chart_type": ep.chart_type,
                "source_platform": ep.source_platform,
                "cm_track_id": cm_track_id,
                "cm_artist_id": cm_artist_id,
                "source_rank": rank_int,
                "spotify_popularity": spotify_pop,
                "monthly_listeners": entry.get("monthly_listeners"),
                "followers": entry.get("followers"),
                "playlist_count": entry.get("playlist_count"),
                "playlist_reach": entry.get("playlist_reach"),
                "velocity": entry.get("velocity"),
                "current_plays": entry.get("current_plays"),
                "genre_filter": genre_value,
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
                        "[%s-deep-us] bulk POST: received=%d ingested=%d dupes=%d errors=%d created=%d elapsed=%dms",
                        self.PLATFORM,
                        body.get("received", 0), body.get("ingested", 0),
                        body.get("duplicates", 0), body.get("errors", 0),
                        body.get("entities_created", 0), body.get("elapsed_ms", 0),
                    )
                else:
                    logger.error("[%s-deep-us] bulk POST failed: HTTP %d %s",
                                 self.PLATFORM, resp.status_code, resp.text[:300])
            except httpx.HTTPError as exc:
                logger.error("[%s-deep-us] bulk POST error: %s", self.PLATFORM, exc)

    def _aggregate_stats(self) -> dict[str, int]:
        return {
            "endpoints": len(self._stats),
            "total_calls": sum(s["calls"] for s in self._stats.values()),
            "total_entries": sum(s["entries"] for s in self._stats.values()),
            "total_empty": sum(s["empty"] for s in self._stats.values()),
            "total_errors": sum(s["errors"] for s in self._stats.values()),
        }

    def per_endpoint_stats(self) -> dict[str, dict[str, int]]:
        return dict(self._stats)
