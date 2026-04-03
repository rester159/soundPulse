# SoundPulse Scrapers — Claude Code Build Prompt

> **Focused prompt for building the data collection and scraping layer only.**
> Assumes the core API is already running with POST /trending accepting data.

---

## CONTEXT

SoundPulse needs data flowing from 6+ upstream sources into its API. Each source has different access methods, rate limits, and failure modes. This prompt covers building all scrapers, fallback strategies, and the scheduling infrastructure.

The internal ingestion endpoint is `POST /api/v1/trending` (admin key required). All scrapers ultimately transform their data and POST it there.

---

## SCRAPER ARCHITECTURE

### Base Class

```python
# scrapers/base.py
import asyncio
import httpx
from abc import ABC, abstractmethod
from datetime import date
from typing import Any
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()

class RawDataPoint(BaseModel):
    """Raw data as received from upstream platform."""
    platform: str
    entity_type: str  # 'artist' or 'track'
    entity_identifier: dict  # platform-specific IDs + names
    raw_score: float | None = None
    rank: int | None = None
    signals: dict = {}
    snapshot_date: date

class BaseScraper(ABC):
    """
    All scrapers inherit from this.
    Provides: retry logic, rate limit awareness, credential refresh, structured logging.
    """
    
    PLATFORM: str  # override in subclass
    MAX_RETRIES: int = 5
    BASE_DELAY: float = 1.0  # exponential backoff base
    
    def __init__(self, credentials: dict, api_base_url: str, admin_key: str):
        self.credentials = credentials
        self.api_base_url = api_base_url
        self.admin_key = admin_key
        self.client = httpx.AsyncClient(timeout=30.0)
        self.log = logger.bind(scraper=self.PLATFORM)
    
    @abstractmethod
    async def authenticate(self) -> None:
        """Obtain/refresh access token. Called before each collection run."""
    
    @abstractmethod
    async def collect_trending(self) -> list[RawDataPoint]:
        """Fetch current trending data from upstream."""
    
    @abstractmethod
    async def collect_entity_details(self, entity_id: str) -> dict:
        """Fetch detailed info for a specific entity."""
    
    async def run(self):
        """Full pipeline: auth → collect → POST to SoundPulse API."""
        try:
            await self.authenticate()
            data_points = await self.collect_trending()
            self.log.info("collected", count=len(data_points))
            
            success, failed = 0, 0
            for point in data_points:
                try:
                    await self._post_to_api(point)
                    success += 1
                except Exception as e:
                    self.log.error("ingest_failed", error=str(e), entity=point.entity_identifier)
                    failed += 1
            
            self.log.info("ingestion_complete", success=success, failed=failed)
        except AuthenticationError:
            self.log.error("auth_failed")
            raise
        except Exception as e:
            self.log.error("collection_failed", error=str(e))
            raise
    
    async def _post_to_api(self, point: RawDataPoint):
        """POST a single data point to the SoundPulse ingestion endpoint."""
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = await self.client.post(
                    f"{self.api_base_url}/api/v1/trending",
                    json=point.model_dump(mode='json'),
                    headers={"X-API-Key": self.admin_key},
                )
                if resp.status_code == 201:
                    return
                elif resp.status_code == 409:
                    return  # duplicate, skip
                elif resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    await asyncio.sleep(retry_after)
                else:
                    resp.raise_for_status()
            except httpx.HTTPError:
                delay = self.BASE_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)
        raise IngestionError(f"Failed after {self.MAX_RETRIES} retries")
    
    async def _rate_limited_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make an upstream request with retry and rate limit handling."""
        for attempt in range(self.MAX_RETRIES):
            resp = await self.client.request(method, url, **kwargs)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                self.log.warning("rate_limited", retry_after=retry_after, url=url)
                await asyncio.sleep(retry_after)
                continue
            resp.raise_for_status()
            return resp
        raise RateLimitError(f"Rate limited after {self.MAX_RETRIES} retries: {url}")
```

### Implementation Priority Order

Build scrapers in this order. Each one should be independently testable.

---

### 1. SPOTIFY SCRAPER

```python
# scrapers/spotify.py

class SpotifyScraper(BaseScraper):
    PLATFORM = "spotify"
    
    # --- Authentication ---
    # Flow: Client Credentials (no user auth needed)
    # POST https://accounts.spotify.com/api/token
    # Body: grant_type=client_credentials
    # Headers: Authorization: Basic base64(client_id:client_secret)
    # Token expires in 3600s — refresh before each run
    
    # --- Data Collection ---
    
    # STEP 1: Monitor curated playlists (primary trending signal)
    TRENDING_PLAYLISTS = {
        "37i9dQZF1DXcBWIGoYBM5M": "Today's Top Hits",
        "37i9dQZEVXbLiRSasKsNU9": "Viral 50 Global",
        "37i9dQZF1DX4JAvHpjipBk": "New Music Friday",
        "37i9dQZF1DX0XUsuxWHRQd": "RapCaviar",
        "37i9dQZF1DX4dyzvuaRJ0n": "mint",
        "37i9dQZF1DX1lVhptIYRda": "Hot Country",
        "37i9dQZF1DWXRqgorJj26U": "Rock This",
        "37i9dQZF1DX4SBhb3fqCJd": "Are & Be",
        "37i9dQZF1DX10zKzsJ2jva": "Viva Latino",
        "37i9dQZF1DX4o1oenSJRJd": "All Out 2020s",  
        # Add more per-genre playlists as discovered
    }
    
    # For each playlist:
    # GET https://api.spotify.com/v1/playlists/{id}/tracks?limit=100
    # Extract: track ID, track name, artist ID, artist name, position in playlist
    # The position IS the rank signal — position 1 in Today's Top Hits = very high signal
    
    # STEP 2: Get audio features for collected tracks
    # GET https://api.spotify.com/v1/audio-features?ids={comma_separated_ids}
    # Max 100 IDs per request
    # Extract: tempo, energy, valence, danceability, acousticness, instrumentalness
    # Store in Track.audio_features
    
    # STEP 3: Get artist details
    # GET https://api.spotify.com/v1/artists?ids={comma_separated_ids}
    # Max 50 IDs per request
    # Extract: followers, popularity, genres, images
    
    # STEP 4: Calculate signals
    # For each track:
    #   raw_score = sum of (1/position * playlist_reach) across all playlists it appears in
    #   This weights position AND playlist size
    #   signals = {
    #     "playlist_appearances": count,
    #     "best_playlist_position": min_position,
    #     "total_playlist_reach": sum of follower counts of playlists,
    #     "popularity": spotify_popularity_metric (0-100),
    #     "audio_features": { tempo, energy, valence, ... }
    #   }
    
    # Rate limit: 180 requests/minute with good token management
    # Implement: asyncio.Semaphore(3) — max 3 concurrent requests
    # Sleep 350ms between requests as safety margin
```

---

### 2. CHARTMETRIC SCRAPER

```python
# scrapers/chartmetric.py

class ChartmetricScraper(BaseScraper):
    PLATFORM = "chartmetric"
    
    # --- Authentication ---
    # POST https://api.chartmetric.com/api/token
    # Body: {"refreshtoken": "<api_key>"}
    # Returns: access_token (expires in 1 hour)
    
    # --- Data Collection ---
    
    # STEP 1: Fetch chart data across platforms
    # These endpoints give us cross-platform chart data through a single API:
    
    CHARTS_TO_MONITOR = [
        # Spotify charts via Chartmetric
        ("GET", "/api/charts/spotify/{type}/{date}", {"type": ["viral", "top"], "date": "today"}),
        
        # Apple Music charts via Chartmetric
        ("GET", "/api/charts/apple-music/{type}/{date}", {"type": ["top"], "date": "today"}),
        
        # TikTok charts via Chartmetric
        ("GET", "/api/charts/tiktok/{type}/{date}", {"type": ["viral"]}),
        
        # Shazam charts via Chartmetric  
        ("GET", "/api/charts/shazam/{type}/{date}", {"type": ["top"]}),
        
        # YouTube charts
        ("GET", "/api/charts/youtube/{type}/{date}", {"type": ["trending"]}),
    ]
    
    # STEP 2: For each charting entity, get cross-platform stats
    # GET /api/artist/{cm_artist_id}/stat/{platform}
    # Platforms: spotify, apple_music, tiktok, youtube, shazam, instagram
    # Returns: time series of metrics per platform
    
    # STEP 3: Get Chartmetric's own scoring
    # GET /api/artist/{cm_artist_id}/score
    # Returns: cm_score (proprietary composite), social mentions, playlist count
    
    # CRITICAL: Chartmetric is the BEST source for cross-platform coverage.
    # It lets us fill gaps for platforms where we don't have direct API access.
    # When ingesting Chartmetric data, POST to /trending with platform="chartmetric"
    # but ALSO post platform-specific data it provides (e.g., Apple Music chart data
    # from Chartmetric gets posted as platform="apple_music")
    
    # Rate limit: Varies by plan (Starter: 100 req/min, Pro: 300 req/min)
    # Implement: Track request count per minute, pause if approaching limit
```

---

### 3. SHAZAM SCRAPER

```python
# scrapers/shazam.py

class ShazamScraper(BaseScraper):
    PLATFORM = "shazam"
    
    # --- Authentication ---
    # RapidAPI key in X-RapidAPI-Key header
    # Host: shazam.p.rapidapi.com
    
    # --- Data Collection ---
    
    # STEP 1: Get global top Shazam charts
    # GET https://shazam.p.rapidapi.com/charts/track
    # Params: locale=en-US, pageSize=200, startFrom=0
    # Returns: top 200 most Shazamed tracks globally
    
    # STEP 2: Get country-specific charts for key markets
    MARKETS = ["US", "GB", "DE", "FR", "BR", "MX", "JP", "KR", "NG", "ZA", 
               "IN", "AU", "CA", "ES", "IT", "NL", "SE", "PL", "TR", "EG"]
    # For each: GET /charts/track with listId for that country
    
    # STEP 3: For each track, get details
    # GET https://shazam.p.rapidapi.com/tracks/get-details
    # Params: key={shazam_track_key}, locale=en-US
    # Returns: track metadata, Spotify/Apple Music links for entity resolution
    
    # KEY SIGNAL: shazam_to_spotify_ratio
    # Calculate: shazam_chart_position_inverse / spotify_streams_normalized
    # High ratio = people are discovering this track (Shazaming it) but haven't
    # started streaming it yet → STRONG leading indicator for breakout
    #
    # This is the single most valuable feature in the prediction model.
    # Track it meticulously.
    
    # Rate limit: Depends on RapidAPI plan
    # Basic (free): 500 requests/month — NOT ENOUGH, need Pro minimum
    # Pro ($10/mo): 10,000/month ≈ 330/day ≈ enough for 4x daily collection
    # Ultra ($50/mo): 100,000/month — comfortable
    # Monitor X-RateLimit-Requests-Remaining header
```

---

### 4. APPLE MUSIC SCRAPER

```python
# scrapers/apple_music.py

class AppleMusicScraper(BaseScraper):
    PLATFORM = "apple_music"
    
    # --- Authentication ---
    # MusicKit API uses JWT (ES256 signed)
    # Header: Authorization: Bearer {developer_token}
    # Token generation:
    #   payload = {"iss": team_id, "iat": now, "exp": now + 15777000}
    #   header = {"alg": "ES256", "kid": key_id}
    #   token = jwt.encode(payload, private_key, algorithm="ES256")
    # Token valid for 6 months — generate once and cache
    
    # --- Data Collection ---
    
    # STEP 1: Get charts by storefront
    STOREFRONTS = ["us", "gb", "de", "fr", "jp", "br", "mx", "kr", "au", "ca"]
    # GET https://api.music.apple.com/v1/catalog/{storefront}/charts
    # Params: types=songs,albums&limit=100
    # Returns: chart position + track metadata
    
    # STEP 2: Get artist details for charting artists
    # GET https://api.music.apple.com/v1/catalog/{storefront}/artists/{id}
    # Returns: name, genres, artwork
    
    # NOTE: Apple Music API is limited compared to Spotify.
    # No stream counts, no playlist data, no audio features.
    # The main signal is chart position across storefronts.
    # Chartmetric often provides better Apple Music data than Apple's own API.
    
    # raw_score: null (no stream counts available)
    # rank: chart position
    # signals: { chart_name, storefront, chart_type }
    
    # Rate limit: Not officially documented but ~20 req/sec seems safe
```

---

### 5. TIKTOK SCRAPER

```python
# scrapers/tiktok.py

class TikTokScraper(BaseScraper):
    PLATFORM = "tiktok"
    
    # --- PATH A: TikTok Research API (if approved) ---
    # Base URL: https://open.tiktokapis.com/v2
    # Auth: OAuth 2.0 client_credentials
    # POST /oauth/token → access_token
    
    # Data collection with Research API:
    # POST /research/video/query/
    # Body: {
    #   "query": { "and": [{"field_name": "music_id", "field_values": [...]}] },
    #   "start_date": "20260314",
    #   "end_date": "20260321",
    #   "max_count": 100,
    #   "fields": "id,create_time,like_count,view_count,share_count,music_id"
    # }
    #
    # For each trending sound:
    #   - Count videos using it
    #   - Analyze creator follower distribution (tier migration)
    #   - Track geographic spread
    #   - Calculate engagement rates
    
    # --- PATH B: Fallback if Research API not available ---
    
    # Option 1: TikTok Creative Center (headless browser)
    # URL: https://ads.tiktok.com/business/creativecenter/inspiration/popular/music/pc/en
    # This page shows trending sounds — scrape with Playwright/Selenium
    # Extract: sound name, artist, usage count, trend direction
    
    # Option 2: Chartmetric TikTok data (already handled by chartmetric scraper)
    # This is the easiest fallback — just make sure ChartmetricScraper POSTs
    # TikTok data with platform="tiktok" in addition to platform="chartmetric"
    
    # Option 3: Third-party TikTok analytics
    # tokboard.com, tokchart.com — web scrape for trending sounds
    # Lower quality but available without API approval
    
    # KEY SIGNALS unique to TikTok:
    # - creator_tier_migration_rate: Calculated as:
    #   (macro_creator_count_today - macro_creator_count_7d_ago) / total_creators
    #   If bigger creators start using a sound that was previously only used by
    #   small creators, this is a STRONG breakout signal.
    # - geo_spread: Number of distinct countries. Rapid geo expansion = viral potential.
    # - video_count_velocity: d(video_count)/dt — acceleration of content creation
```

---

### 6. MUSICBRAINZ ENRICHER

```python
# scrapers/musicbrainz.py

class MusicBrainzEnricher(BaseScraper):
    PLATFORM = "musicbrainz"
    
    # NOT a trending data source — this is a METADATA ENRICHER.
    # Called on-demand when new entities are created to fill in:
    # - ISRC codes
    # - Correct canonical artist names
    # - Release dates
    # - Genre tags
    # - Disambiguation (which "The National" is this?)
    
    # Base URL: https://musicbrainz.org/ws/2
    # Auth: User-Agent header (required, must identify your app)
    # User-Agent: SoundPulse/1.0 (enrico@soundpulse.io)
    
    # CRITICAL: Rate limit is 1 request per second. Hard limit. IP ban if exceeded.
    # Implement: asyncio.sleep(1.1) between ALL requests. No parallelism.
    
    # Enrichment flow for new tracks:
    # 1. Search by ISRC (if available):
    #    GET /recording?query=isrc:{isrc}&fmt=json
    #
    # 2. Search by title + artist (fallback):
    #    GET /recording?query=recording:{title} AND artist:{artist}&fmt=json
    #
    # 3. Get recording details:
    #    GET /recording/{mbid}?inc=artists+releases+isrcs+tags&fmt=json
    #
    # 4. Update SoundPulse entity:
    #    - Fill ISRC if missing
    #    - Fill release_date from earliest release
    #    - Add MusicBrainz tags to genre classification
    #    - Set musicbrainz_id on Artist/Track
    
    # Enrichment flow for new artists:
    # 1. Search: GET /artist?query=artist:{name}&fmt=json
    # 2. Disambiguate by matching genre + active period
    # 3. Get details: GET /artist/{mbid}?inc=tags+genres&fmt=json
    # 4. Update: musicbrainz_id, additional genre tags
```

---

### 7. RADIO/LUMINATE SCRAPER

```python
# scrapers/radio.py

class RadioScraper(BaseScraper):
    PLATFORM = "radio"
    
    # --- PATH A: Luminate API (enterprise, if obtained) ---
    # Contact luminate.support@luminate.com for API access
    # Provides: radio airplay data, BDS spins, audience impressions
    
    # --- PATH B: Billboard Airplay Charts (web scrape) ---
    # URL: https://www.billboard.com/charts/radio-songs/
    # Also: https://www.billboard.com/charts/pop-airplay/
    #       https://www.billboard.com/charts/country-airplay/
    #       https://www.billboard.com/charts/adult-contemporary/
    
    # Scrape with: httpx + BeautifulSoup (Billboard doesn't heavy JS render)
    # Or: Playwright if needed
    
    # Extract per chart entry:
    #   - rank (chart position)
    #   - title
    #   - artist
    #   - peak_position
    #   - weeks_on_chart
    
    # raw_score: null (no spin counts from scraping)
    # rank: chart position
    # signals: { chart_name, peak_position, weeks_on_chart }
    
    # Schedule: Once daily (radio charts update weekly on Billboard but we
    #           check daily to catch updates promptly)
    
    # --- PATH C: Radiomonitor API (paid alternative) ---
    # https://www.radiomonitor.com/
    # Provides real-time airplay monitoring across 3500+ stations
    # More expensive but real-time data vs Billboard's weekly
```

---

## FALLBACK CHAIN

```python
# scrapers/fallback_strategies.py

from enum import Enum

class DataQuality(Enum):
    LIVE = "live"          # Direct API, real-time data
    AGGREGATED = "agg"     # Via aggregator (Chartmetric), slight delay  
    SCRAPED = "scraped"    # Web scrape, less reliable
    CACHED = "cached"      # Stale data from last successful collection

class FallbackChain:
    """
    For each platform, try sources in order until one succeeds.
    Tag data with quality level so downstream consumers know freshness.
    """
    
    CHAINS = {
        "spotify": [
            (SpotifyScraper, DataQuality.LIVE),
            (ChartmetricSpotifyAdapter, DataQuality.AGGREGATED),
            # No web scrape — Spotify's web player requires auth
            (CachedDataFallback, DataQuality.CACHED),
        ],
        "apple_music": [
            (AppleMusicScraper, DataQuality.LIVE),
            (ChartmetricAppleMusicAdapter, DataQuality.AGGREGATED),
            (CachedDataFallback, DataQuality.CACHED),
        ],
        "tiktok": [
            (TikTokResearchAPIScraper, DataQuality.LIVE),
            (ChartmetricTikTokAdapter, DataQuality.AGGREGATED),
            (TikTokCreativeCenterScraper, DataQuality.SCRAPED),
            (CachedDataFallback, DataQuality.CACHED),
        ],
        "shazam": [
            (ShazamRapidAPIScraper, DataQuality.LIVE),
            (ChartmetricShazamAdapter, DataQuality.AGGREGATED),
            (ShazamWebScraper, DataQuality.SCRAPED),  # shazam.com/charts
            (CachedDataFallback, DataQuality.CACHED),
        ],
        "radio": [
            (LuminateScraper, DataQuality.LIVE),
            (RadiomonitorScraper, DataQuality.LIVE),
            (BillboardAirplayScraper, DataQuality.SCRAPED),
            (CachedDataFallback, DataQuality.CACHED),
        ],
    }
    
    async def collect(self, platform: str) -> tuple[list[RawDataPoint], DataQuality]:
        for scraper_class, quality in self.CHAINS[platform]:
            try:
                scraper = scraper_class(...)
                data = await scraper.collect_trending()
                if data:
                    return data, quality
            except Exception as e:
                logger.warning("fallback_triggered", 
                              platform=platform,
                              failed_source=scraper_class.__name__,
                              error=str(e))
                continue
        return [], DataQuality.CACHED
```

---

## HEADLESS BROWSER SCRAPERS (for web-only fallbacks)

When API access isn't available, some sources can be scraped with a headless browser.

```python
# scrapers/browser_base.py
# Use Playwright (async) for headless scraping

# pip install playwright
# playwright install chromium

from playwright.async_api import async_playwright

class BrowserScraper:
    """Base class for headless browser scrapers."""
    
    async def scrape(self, url: str, extract_fn) -> list[dict]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...",
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle")
            
            # Wait for dynamic content to load
            await page.wait_for_timeout(3000)
            
            data = await extract_fn(page)
            await browser.close()
            return data

# Example: TikTok Creative Center scraper
class TikTokCreativeCenterScraper(BrowserScraper):
    URL = "https://ads.tiktok.com/business/creativecenter/inspiration/popular/music/pc/en"
    
    async def collect_trending(self):
        data = await self.scrape(self.URL, self._extract_trending_sounds)
        return [self._to_raw_data_point(item) for item in data]
    
    async def _extract_trending_sounds(self, page):
        # Extract trending sounds from the Creative Center page
        # The page renders a table/grid of trending sounds
        # Extract: sound_name, artist_name, usage_count, trend_indicator
        items = await page.query_selector_all("[class*='music-card'], [class*='trending-item']")
        results = []
        for item in items:
            # ... extract data from each card
            pass
        return results
```

---

## CELERY SCHEDULE

```python
# scrapers/scheduler.py
from celery import Celery
from celery.schedules import crontab

app = Celery('soundpulse', broker='redis://localhost:6379/0')

app.conf.beat_schedule = {
    # Primary data collection
    'spotify-every-6h': {
        'task': 'scrapers.spotify.run',
        'schedule': crontab(hour='0,6,12,18', minute=0),
    },
    'chartmetric-every-4h': {
        'task': 'scrapers.chartmetric.run',
        'schedule': crontab(hour='*/4', minute=15),  # offset from Spotify
    },
    'shazam-every-4h': {
        'task': 'scrapers.shazam.run',
        'schedule': crontab(hour='*/4', minute=30),
    },
    'apple-music-every-6h': {
        'task': 'scrapers.apple_music.run',
        'schedule': crontab(hour='1,7,13,19', minute=0),
    },
    'tiktok-every-4h': {
        'task': 'scrapers.tiktok.run',
        'schedule': crontab(hour='*/4', minute=45),
    },
    'radio-daily': {
        'task': 'scrapers.radio.run',
        'schedule': crontab(hour=6, minute=0),
    },
    
    # Metadata enrichment
    'musicbrainz-enrich-new': {
        'task': 'scrapers.musicbrainz.enrich_pending',
        'schedule': crontab(hour=2, minute=0),  # off-peak
    },
    
    # Composite score recalculation
    'recalc-composite': {
        'task': 'api.services.aggregation.recalculate_all',
        'schedule': crontab(minute='*/30'),
    },
    
    # Health check
    'scraper-health-check': {
        'task': 'scrapers.health.check_all',
        'schedule': crontab(minute='*/15'),
    },
}

# Stagger tasks to avoid thundering herd
# Each scraper runs at a different minute offset within its hour window
```

---

## HEALTH MONITORING

```python
# scrapers/health.py

class ScraperHealthCheck:
    """
    Runs every 15 minutes. Checks:
    1. Each platform has data from last expected_interval
    2. Entity count is growing (not stuck)
    3. No scraper has been failing for > 2 consecutive runs
    4. Rate limit headroom is sufficient
    """
    
    EXPECTED_FRESHNESS = {
        "spotify": timedelta(hours=7),       # runs every 6h + 1h buffer
        "chartmetric": timedelta(hours=5),   
        "shazam": timedelta(hours=5),
        "apple_music": timedelta(hours=7),
        "tiktok": timedelta(hours=5),
        "radio": timedelta(hours=25),        # daily
    }
    
    async def check_all(self):
        alerts = []
        for platform, max_age in self.EXPECTED_FRESHNESS.items():
            latest = await get_latest_snapshot(platform)
            if latest is None or (now() - latest.created_at) > max_age:
                alerts.append(f"STALE: {platform} data is {age} old (max: {max_age})")
        
        if alerts:
            # Log alerts, could also send to Slack/email
            for alert in alerts:
                logger.error("health_alert", message=alert)
```

---

## TESTING STRATEGY

```python
# tests/test_scrapers/conftest.py

# Use VCR.py or respx to record/replay HTTP interactions
# This lets you test scraper logic without hitting real APIs

@pytest.fixture
def spotify_scraper(mock_credentials):
    return SpotifyScraper(
        credentials=mock_credentials["spotify"],
        api_base_url="http://localhost:8000",
        admin_key="sp_admin_test123"
    )

# Test: authentication flow
# Test: data collection parses response correctly
# Test: entity_identifier construction is complete
# Test: rate limit handling backs off correctly
# Test: fallback chain tries next source on failure
# Test: duplicate snapshot handling (409 response)
# Test: health check alerts on stale data
```

---

## ENV VARS FOR SCRAPERS

```bash
# Upstream API credentials
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
CHARTMETRIC_API_KEY=
SHAZAM_RAPIDAPI_KEY=
APPLE_MUSIC_TEAM_ID=
APPLE_MUSIC_KEY_ID=
APPLE_MUSIC_PRIVATE_KEY_PATH=./keys/apple_music.p8
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=

# SoundPulse internal
SOUNDPULSE_API_URL=http://localhost:8000
SOUNDPULSE_ADMIN_KEY=

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Playwright (for browser scrapers)
PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
```
