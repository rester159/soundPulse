# SoundPulse API — Claude Code Build Prompt

> **Copy this entire file into Claude Code as your initial prompt. It contains everything needed to build the full system autonomously.**

---

## IDENTITY & CONTEXT

You are building **SoundPulse**, a music intelligence API that aggregates trending music data from multiple upstream sources (Spotify, Apple Music, TikTok, Shazam, radio/Luminate, Chartmetric), normalizes it into a unified schema, and serves it through a REST API. The system also includes a self-learning prediction engine that forecasts which artists and genres will trend next.

The builder is Enrico. He builds proprietary intelligence layers on top of fragmented public data (prior projects: Vetted, Atlas). This is the same pattern — take messy, scattered music signals and turn them into a clean, opinionated data product.

---

## PHASE 0: PROJECT SCAFFOLD

```bash
mkdir -p soundpulse/{api,scrapers,prediction,frontend,shared,scripts,config,tests}
cd soundpulse
git init
```

### Tech Stack Decisions (DO NOT ask Enrico — just use these)
- **API**: Python 3.12 + FastAPI + Uvicorn
- **Database**: PostgreSQL 16 + SQLAlchemy 2.0 (async) + Alembic migrations
- **Cache**: Redis 7 (response cache + rate limiting)
- **Task Queue**: Celery + Redis broker (for scraper scheduling)
- **Prediction**: LightGBM + LSTM (PyTorch) + XGBoost ensemble, Ridge meta-learner
- **Frontend**: React 18 + Vite + TailwindCSS
- **Containerization**: Docker Compose for local dev
- **Testing**: pytest + pytest-asyncio

### Directory Structure
```
soundpulse/
├── api/
│   ├── main.py                    # FastAPI app entry
│   ├── config.py                  # Settings via pydantic-settings
│   ├── dependencies.py            # DB session, Redis, auth
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── artist.py
│   │   ├── track.py
│   │   ├── genre.py
│   │   ├── trending_snapshot.py
│   │   ├── prediction.py
│   │   └── feedback.py
│   ├── schemas/                   # Pydantic request/response schemas
│   │   ├── trending.py
│   │   ├── search.py
│   │   ├── predictions.py
│   │   └── genres.py
│   ├── routers/
│   │   ├── trending.py            # GET /trending, POST /trending
│   │   ├── search.py              # GET /search
│   │   ├── predictions.py         # GET /predictions, POST /predictions/feedback
│   │   └── genres.py              # GET /genres, GET /genres/{id}
│   ├── services/
│   │   ├── normalization.py       # Cross-platform score normalization
│   │   ├── entity_resolution.py   # Artist/track dedup across platforms
│   │   ├── genre_classifier.py    # Multi-signal genre classification engine
│   │   ├── aggregation.py         # Weighted signal combination
│   │   └── cache.py               # Redis caching layer
│   └── middleware/
│       ├── rate_limiter.py        # Tiered rate limiting
│       └── auth.py                # API key auth
├── scrapers/
│   ├── base.py                    # Abstract BaseScraper class
│   ├── spotify.py                 # Spotify Web API collector
│   ├── apple_music.py             # Apple Music API collector
│   ├── tiktok.py                  # TikTok Research API / fallback scraper
│   ├── shazam.py                  # Shazam via RapidAPI
│   ├── chartmetric.py             # Chartmetric aggregator
│   ├── radio.py                   # Luminate / radio airplay
│   ├── musicbrainz.py             # MusicBrainz metadata enrichment
│   ├── scheduler.py               # Celery beat schedule
│   └── fallback_strategies.py     # When APIs fail — headless browser, cached data
├── prediction/
│   ├── features/
│   │   ├── engineering.py         # ~70 engineered features
│   │   ├── leading_indicators.py  # Shazam-to-Spotify ratio, TikTok tier migration
│   │   └── temporal.py            # Rolling windows, lag features
│   ├── models/
│   │   ├── lightgbm_model.py      # Tabular model
│   │   ├── lstm_model.py          # Sequence model with attention
│   │   ├── xgboost_model.py       # Interaction features model
│   │   └── meta_learner.py        # Ridge regression ensemble
│   ├── calibration.py             # Isotonic regression confidence calibration
│   ├── cold_start.py              # New artist/genre ramp strategy
│   ├── training_loop.py           # Daily self-learning: predict → compare → retrain
│   ├── drift_detection.py         # PSI + KS tests for feature/prediction drift
│   └── backtesting.py             # Walk-forward validation framework
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── TrendingPanel.jsx
│   │   │   ├── SearchBar.jsx
│   │   │   ├── PredictionCard.jsx
│   │   │   ├── GenreBrowser.jsx
│   │   │   └── ApiTester.jsx
│   │   ├── hooks/
│   │   │   └── useSoundPulse.js   # API client hook
│   │   └── pages/
│   │       ├── Dashboard.jsx
│   │       └── Explore.jsx
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
├── shared/
│   ├── genre_taxonomy.py          # 850+ genres, 12 root categories, dot-notation IDs
│   └── constants.py               # Platform weights, normalization bounds
├── scripts/
│   ├── seed_genres.py             # Load taxonomy into DB
│   ├── api_key_setup.py           # Interactive credential collector
│   └── migrate.py                 # Alembic wrapper
├── config/
│   ├── .env.example
│   └── credentials.yaml.example
├── tests/
│   ├── test_api/
│   ├── test_scrapers/
│   ├── test_prediction/
│   └── conftest.py
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic.ini
└── README.md
```

---

## PHASE 1: DATABASE + CORE API (Build First)

### 1.1 Database Models

Create these SQLAlchemy models. Every model uses UUID primary keys and `created_at`/`updated_at` timestamps.

**`models/artist.py`**
```
Artist:
  - id: UUID (PK)
  - name: str (indexed)
  - spotify_id: str | None (unique, indexed)
  - apple_music_id: str | None (unique, indexed)
  - tiktok_handle: str | None
  - chartmetric_id: int | None
  - musicbrainz_id: str | None
  - image_url: str | None
  - genres: list[str]  # dot-notation genre IDs
  - metadata_json: dict  # overflow field for platform-specific data
  - canonical: bool = True  # False = duplicate, points to canonical via merge table
```

**`models/track.py`**
```
Track:
  - id: UUID (PK)
  - title: str (indexed)
  - artist_id: UUID (FK → Artist)
  - isrc: str | None (unique, indexed)  # International Standard Recording Code
  - spotify_id: str | None (unique, indexed)
  - apple_music_id: str | None
  - duration_ms: int | None
  - release_date: date | None
  - genres: list[str]
  - audio_features: dict | None  # tempo, energy, valence, etc from Spotify
  - metadata_json: dict
```

**`models/trending_snapshot.py`**
```
TrendingSnapshot:
  - id: UUID (PK)
  - entity_type: enum('artist', 'track')
  - entity_id: UUID (FK → Artist or Track)
  - snapshot_date: date (indexed)
  - platform: str  # 'spotify', 'apple_music', 'tiktok', 'shazam', 'radio', 'chartmetric'
  - platform_rank: int | None
  - platform_score: float | None  # raw platform metric
  - normalized_score: float  # 0-100 normalized
  - velocity: float | None  # rate of change vs previous snapshot
  - signals_json: dict  # platform-specific breakdown
  - composite_score: float | None  # weighted cross-platform score

  Table args: unique constraint on (entity_type, entity_id, snapshot_date, platform)
```

**`models/prediction.py`**
```
Prediction:
  - id: UUID (PK)
  - entity_type: enum('artist', 'track', 'genre')
  - entity_id: UUID | str  # UUID for artist/track, dot-notation string for genre
  - horizon: enum('7d', '30d', '90d')
  - predicted_score: float  # predicted composite_score at horizon end
  - confidence: float  # calibrated 0-1
  - model_version: str
  - features_json: dict  # feature values at prediction time (for explainability)
  - predicted_at: datetime
  - resolved_at: datetime | None
  - actual_score: float | None  # filled when horizon elapses
  - error: float | None  # predicted - actual
```

**`models/genre.py`**
```
Genre:
  - id: str (PK)  # dot-notation: "electronic.house.tech-house"
  - name: str
  - parent_id: str | None (FK → Genre, self-referential)
  - root_category: str  # one of 12 roots
  - depth: int  # 0 = root, 1, 2, 3
  - spotify_genres: list[str]  # mapped Spotify genre strings
  - apple_music_genres: list[str]
  - musicbrainz_tags: list[str]
  - chartmetric_genres: list[str]
  - audio_profile: dict | None  # expected tempo range, energy, valence
  - adjacent_genres: list[str]  # cross-branch related genre IDs
  - status: enum('active', 'deprecated', 'proposed')
```

### 1.2 API Endpoints

Build these endpoints in this exact order:

#### `GET /genres`
- Returns the full genre taxonomy tree
- Query params: `root` (filter by root category), `depth` (max depth), `status`
- Response: nested tree structure with `children` arrays
- Cache: 24 hours (taxonomy changes rarely)

#### `GET /genres/{genre_id}`
- Returns single genre with full cross-platform mappings and adjacent genres
- Cache: 24 hours

#### `POST /trending`
- **This is the data ingestion endpoint — called by scrapers, not end users**
- Auth: requires admin API key
- Body:
```json
{
  "platform": "spotify",
  "entity_type": "track",
  "entity_identifier": {
    "spotify_id": "4uLU6hMCjMI75M1A2tKUQC",
    "isrc": "USRC11600001",
    "title": "Never Gonna Give You Up",
    "artist_name": "Rick Astley"
  },
  "raw_score": 85432,
  "rank": 3,
  "signals": {
    "streams_24h": 2400000,
    "playlist_adds": 450,
    "save_rate": 0.12
  },
  "snapshot_date": "2026-03-21"
}
```
- **Entity resolution logic**: Match by platform ID first → ISRC → fuzzy title+artist match (Levenshtein ≥ 0.85). Create new entity if no match.
- **Normalization**: Convert raw_score to 0-100 using per-platform min-max with exponential decay on historical bounds. Store both raw and normalized.
- **Composite scoring**: After ingesting, recalculate composite_score using platform weights:
  - Spotify: 0.25
  - Apple Music: 0.15
  - TikTok: 0.25 (social virality is a leading indicator)
  - Shazam: 0.15 (strong leading indicator)
  - Radio: 0.10
  - Chartmetric: 0.10

#### `GET /trending`
- Returns current trending entities
- Query params:
  - `entity_type`: 'artist' | 'track' (required)
  - `genre`: filter by genre ID (matches any depth in hierarchy)
  - `platform`: filter to single platform's ranking
  - `time_range`: 'today' | '7d' | '30d'
  - `limit`: 10-100 (default 50)
  - `offset`: pagination
  - `sort`: 'composite_score' | 'velocity' | 'platform_rank'
  - `min_platforms`: minimum number of platforms entity must appear on (default 1)
- Response includes:
  - Entity details (name, image, genres, IDs)
  - Composite score and per-platform breakdown
  - Velocity (trend direction)
  - Position change vs previous period
- Cache: 15 minutes for 'today', 1 hour for '7d', 6 hours for '30d'

#### `GET /search`
- Full-text search across artists and tracks
- Query params: `q` (search string), `type` ('artist' | 'track' | 'all'), `limit`
- Uses PostgreSQL `tsvector` + trigram similarity
- Returns matching entities with their latest trending data
- Cache: 5 minutes

#### `GET /predictions`
- Returns current predictions
- Query params: `entity_type`, `horizon`, `genre`, `min_confidence`, `limit`, `sort`
- Response:
```json
{
  "predictions": [
    {
      "entity": { "id": "...", "name": "...", "type": "artist" },
      "horizon": "7d",
      "predicted_score": 78.4,
      "confidence": 0.82,
      "current_score": 45.2,
      "predicted_change": "+73.5%",
      "top_signals": [
        {"feature": "shazam_to_spotify_ratio", "value": 3.2, "impact": "high"},
        {"feature": "tiktok_creator_tier_migration", "value": 0.45, "impact": "medium"}
      ],
      "model_version": "v0.3.1",
      "predicted_at": "2026-03-21T06:00:00Z"
    }
  ],
  "meta": { "total": 150, "horizon": "7d", "generated_at": "..." }
}
```

#### `POST /predictions/feedback`
- Allows manual ground-truth submission (for cases where automated resolution is insufficient)
- Auth: admin API key
- Body: `{ "prediction_id": "...", "actual_score": 72.1, "notes": "..." }`

### 1.3 Cross-Cutting Concerns

**Rate Limiting** (implement via Redis sliding window):
- Free tier: 100 requests/hour
- Pro tier: 1,000 requests/hour
- Admin: unlimited
- Return `X-RateLimit-Remaining` and `X-RateLimit-Reset` headers

**Authentication**:
- API key in `X-API-Key` header
- Keys stored in DB with tier, owner, created_at, last_used_at
- Admin keys can POST to ingestion endpoints; regular keys are read-only

**Error Responses** (consistent format):
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Resets at 2026-03-21T12:15:00Z",
    "details": { "limit": 100, "remaining": 0, "reset_at": "..." }
  }
}
```

---

## PHASE 2: SCRAPERS & DATA COLLECTION

### Build Order
1. Spotify (most complete API, best for bootstrapping)
2. Chartmetric (aggregator, fills gaps)
3. Shazam via RapidAPI (critical leading indicator)
4. Apple Music
5. TikTok
6. MusicBrainz (metadata enrichment)
7. Radio/Luminate (if API access obtained)

### 2.1 Base Scraper Class

```python
# scrapers/base.py
class BaseScraper(ABC):
    """
    All scrapers inherit from this.
    Handles: retry logic (exponential backoff), rate limit awareness,
    credential refresh, error reporting, structured logging.
    """
    
    @abstractmethod
    async def collect(self, params: CollectParams) -> list[RawDataPoint]:
        """Fetch raw data from upstream."""
    
    @abstractmethod
    async def transform(self, raw: list[RawDataPoint]) -> list[NormalizedRecord]:
        """Transform platform-specific data into SoundPulse schema."""
    
    async def ingest(self, params: CollectParams):
        """Full pipeline: collect → transform → POST to /trending."""
        raw = await self.collect(params)
        normalized = await self.transform(raw)
        for record in normalized:
            await self.post_to_api(record)
    
    async def post_to_api(self, record: NormalizedRecord):
        """POST to internal /trending endpoint with admin key."""
```

### 2.2 Scraper Implementations

**Spotify** (`scrapers/spotify.py`):
- Credentials: Client ID + Client Secret (client_credentials flow)
- Endpoints to hit:
  - `GET /browse/new-releases` — new releases (weekly)
  - `GET /playlists/{id}/tracks` — monitor viral/trending playlists:
    - "Today's Top Hits" (37i9dQZF1DXcBWIGoYBM5M)
    - "Viral 50 Global" (37i9dQZEVXbLiRSasKsNU9)
    - "New Music Friday" (37i9dQZF1DX4JAvHpjipBk)
    - + 20 more genre-specific playlists (discover and store IDs)
  - `GET /artists/{id}` — artist metadata
  - `GET /audio-features/{id}` — audio features for tracks
  - `GET /search` — resolve entities
- Rate limit: Spotify allows 180 req/min with proper token management
- Schedule: Every 6 hours for playlist monitoring, daily for full catalog scan

**Chartmetric** (`scrapers/chartmetric.py`):
- Credentials: API key (paid plan required for full access)
- Endpoints:
  - `GET /charts/spotify/viral` — Spotify viral charts
  - `GET /charts/apple-music/top` — Apple Music charts via Chartmetric
  - `GET /charts/tiktok/viral` — TikTok viral
  - `GET /artist/{id}/stats` — cross-platform stats for artist
  - `GET /track/{id}/stats` — cross-platform stats for track
- This is the most valuable single source — covers multiple platforms in one API
- Schedule: Every 4 hours

**Shazam** (`scrapers/shazam.py`):
- Credentials: RapidAPI key (Shazam Core API)
- Endpoints:
  - `GET /charts/list` — available chart types
  - `GET /charts/track` — top Shazamed tracks globally + by country
  - `GET /search` — entity resolution
- CRITICAL: Shazam-to-Spotify ratio is the #1 leading indicator for breakout tracks. A track being Shazamed heavily but not yet streaming big = about to blow up.
- Schedule: Every 4 hours
- Rate limit: Depends on RapidAPI plan (Basic: 500/month, Pro: 10,000/month)

**Apple Music** (`scrapers/apple_music.py`):
- Credentials: Apple Developer account → MusicKit API key (JWT signed with private key)
- Endpoints:
  - `GET /v1/catalog/{storefront}/charts` — top charts
  - `GET /v1/catalog/{storefront}/search` — search
  - `GET /v1/catalog/{storefront}/artists/{id}` — artist details
- Schedule: Every 6 hours
- Note: Apple Music API is more restrictive. Chartmetric is often better for Apple Music chart data.

**TikTok** (`scrapers/tiktok.py`):
- PRIMARY: TikTok Research API (requires application approval — academic/commercial)
  - If approved: `POST /research/video/query` with sound_id filters
  - Tracks: video count per sound, creator tier distribution, geographic spread
- FALLBACK (if Research API not available):
  - Chartmetric TikTok charts (already covered above)
  - TikTok Creative Center trending page (headless browser scrape)
  - tokboard.com or similar third-party TikTok analytics (web scrape)
- Key signals: sound usage count, creator tier migration (micro → mid → macro creators using a sound), geographic velocity
- Schedule: Every 4 hours for charts, daily for deep sound analysis

**MusicBrainz** (`scrapers/musicbrainz.py`):
- Credentials: None (open API, 1 req/sec rate limit)
- Use for: ISRC lookups, artist disambiguation, release metadata, genre tags
- Schedule: On-demand (called by entity_resolution service when new entities appear)

**Radio / Luminate** (`scrapers/radio.py`):
- Luminate (formerly Nielsen/BDS): Enterprise API, requires sales conversation
- Alternative: Radiomonitor API, or Mediabase
- If no API access: scrape publicly available radio charts (Billboard Airplay charts via web)
- Schedule: Daily (radio data updates slowly)

### 2.3 Fallback Strategies

When APIs are down or credentials aren't available:

```python
# scrapers/fallback_strategies.py

class FallbackChain:
    """
    Each platform has a priority-ordered list of data sources.
    If #1 fails, try #2, etc.
    """
    SPOTIFY = [
        SpotifyDirectAPI,       # Best: direct API
        ChartmetricSpotify,     # Good: Chartmetric's Spotify data
        SpotifyPlaylistScrape,  # OK: headless browser on open.spotify.com
        CachedSpotifyData,      # Last resort: serve stale data with staleness flag
    ]
    
    TIKTOK = [
        TikTokResearchAPI,      # Best: research API (if approved)
        ChartmetricTikTok,      # Good: Chartmetric's TikTok data
        TikTokCreativeCenter,   # OK: scrape creative center trending page
        TokboardScrape,         # Fallback: third-party analytics
        CachedTikTokData,       # Last resort
    ]
    
    SHAZAM = [
        ShazamRapidAPI,         # Best: official via RapidAPI
        ChartmetricShazam,      # Good: Chartmetric's Shazam data  
        ShazamChartsScrape,     # OK: scrape shazam.com/charts
        CachedShazamData,       # Last resort
    ]
```

### 2.4 Celery Schedule

```python
# scrapers/scheduler.py
CELERYBEAT_SCHEDULE = {
    'spotify-collect': {'task': 'scrapers.spotify.collect', 'schedule': crontab(hour='*/6')},
    'chartmetric-collect': {'task': 'scrapers.chartmetric.collect', 'schedule': crontab(hour='*/4')},
    'shazam-collect': {'task': 'scrapers.shazam.collect', 'schedule': crontab(hour='*/4')},
    'apple-music-collect': {'task': 'scrapers.apple_music.collect', 'schedule': crontab(hour='*/6')},
    'tiktok-collect': {'task': 'scrapers.tiktok.collect', 'schedule': crontab(hour='*/4')},
    'musicbrainz-enrich': {'task': 'scrapers.musicbrainz.enrich_new', 'schedule': crontab(hour=2)},
    'radio-collect': {'task': 'scrapers.radio.collect', 'schedule': crontab(hour=6)},
    'composite-recalc': {'task': 'api.services.aggregation.recalculate', 'schedule': crontab(minute='*/30')},
    'prediction-daily': {'task': 'prediction.training_loop.run', 'schedule': crontab(hour=6, minute=30)},
}
```

---

## PHASE 3: CREDENTIAL ACQUISITION AGENT

Build an interactive CLI tool that helps Enrico obtain all necessary API keys. It should guide through each provider, open the right URLs, explain what's needed, and store credentials securely.

### `scripts/api_key_setup.py`

```
Interactive flow:

1. SPOTIFY
   - Open: https://developer.spotify.com/dashboard
   - Need: Client ID + Client Secret
   - Flow: Create app → Copy credentials
   - Test: Try client_credentials token exchange
   - Store in: config/credentials.yaml (encrypted at rest)

2. CHARTMETRIC
   - Open: https://api.chartmetric.com/apidoc/
   - Need: API key (requires paid subscription)
   - Plans: Starter ($150/mo), Pro ($400/mo), Enterprise (custom)
   - Recommendation: Start with Starter, upgrade when hitting limits
   - Test: Try /charts/spotify/viral endpoint
   
3. SHAZAM (via RapidAPI)
   - Open: https://rapidapi.com/apidojo/api/shazam
   - Need: RapidAPI key
   - Plans: Basic (free, 500 req/mo), Pro ($10/mo, 10K req/mo), Ultra ($50/mo, 100K)
   - Recommendation: Pro plan minimum for meaningful data
   - Test: Try /charts/track endpoint

4. APPLE MUSIC
   - Open: https://developer.apple.com/musickit/
   - Need: Apple Developer account ($99/yr) → MusicKit private key
   - Flow: Developer portal → Keys → Create MusicKit key → Download .p8 file
   - JWT generation: Sign with ES256 using Team ID + Key ID + Private Key
   - Test: Try /v1/catalog/us/charts
   
5. TIKTOK RESEARCH API
   - Open: https://developers.tiktok.com/products/research-api/
   - Need: Apply for access (academic or commercial use case)
   - Timeline: 2-6 weeks for approval
   - Fallback: Flag as "pending" — system will use Chartmetric TikTok data meanwhile
   
6. MUSICBRAINZ
   - No key needed — just set User-Agent header
   - User-Agent: "SoundPulse/1.0 (enrico@soundpulse.io)"
   - Rate limit: 1 request/second (hard limit, will get IP banned if exceeded)

7. LUMINATE / RADIO (Optional)
   - Enterprise sales process — no self-serve
   - Contact: luminate.support@luminate.com
   - Alternative: Radiomonitor (https://www.radiomonitor.com/)
   - Fallback: Web scrape Billboard Airplay charts

After setup, verify all keys and print status:
✅ Spotify: Connected (Client Credentials flow working)
✅ Chartmetric: Connected (Starter plan)
✅ Shazam: Connected (Pro plan, 10K req/mo)
✅ Apple Music: Connected (JWT generation working)
⏳ TikTok: Pending approval (using Chartmetric fallback)
✅ MusicBrainz: Ready (no auth needed)
❌ Luminate: Not configured (using Billboard scrape fallback)
```

### Credential Storage

```yaml
# config/credentials.yaml.example
spotify:
  client_id: ""
  client_secret: ""
  
chartmetric:
  api_key: ""
  
shazam:
  rapidapi_key: ""
  
apple_music:
  team_id: ""
  key_id: ""
  private_key_path: "./keys/apple_music.p8"
  
tiktok:
  client_key: ""
  client_secret: ""
  status: "pending"  # pending | approved | denied
  
musicbrainz:
  user_agent: "SoundPulse/1.0 (enrico@soundpulse.io)"
  
luminate:
  api_key: ""
  status: "not_configured"  # not_configured | active

# Redis
redis:
  url: "redis://localhost:6379/0"
  
# PostgreSQL
database:
  url: "postgresql+asyncpg://soundpulse:password@localhost:5432/soundpulse"

# API keys for SoundPulse itself
soundpulse:
  admin_key: ""  # auto-generated on first run
  free_tier_keys: []
  pro_tier_keys: []
```

---

## PHASE 4: GENRE TAXONOMY

### The 12 Root Categories
```
pop, rock, electronic, hip-hop, r-and-b, latin, country, jazz, classical, 
african, asian, caribbean
```

### Taxonomy Structure
- **Dot-notation IDs**: `electronic.house.tech-house.afro-tech`
- **850+ genres** total across all roots
- **Max depth**: 4 levels
- **Each genre has**:
  - Bidirectional mappings to Spotify, Apple Music, MusicBrainz, Chartmetric genre strings
  - Audio feature profile (expected tempo range, energy range, valence range)
  - Adjacency list (related genres across branches, e.g., "electronic.house.afro-house" ↔ "african.afrobeats")

### Implementation

Build `shared/genre_taxonomy.py` as a Python data structure (list of dicts). Then `scripts/seed_genres.py` loads it into the Genre table.

The taxonomy must be exhaustive but practical. Focus on:
- **Depth where it matters**: Electronic music needs 4 levels (electronic.house.deep-house). Classical needs 3 (classical.orchestral.symphonic).
- **Cross-platform mapping quality**: Every genre should map to at least Spotify and one other platform.
- **Adjacent genre graph**: Enable "listeners who like X also like Y" at the genre level.

---

## PHASE 5: PREDICTION ENGINE

### Architecture
```
Raw Data (TrendingSnapshots) 
  → Feature Engineering (~70 features)
    → 3 Base Models (parallel):
       ├── LightGBM (tabular features)
       ├── LSTM with Attention (time series sequences)
       └── XGBoost (hand-crafted interaction features)
    → Ridge Meta-Learner (combines base model outputs)
      → Isotonic Regression (confidence calibration)
        → Final Prediction
```

### Key Features to Engineer

**Momentum features** (per entity, per platform):
- score_7d_avg, score_30d_avg
- velocity_7d (linear slope of last 7 daily scores)
- acceleration (velocity change rate)
- score_vs_7d_avg, score_vs_30d_avg (ratio to moving average)

**Cross-platform features**:
- platform_count (how many platforms entity appears on)
- platform_score_variance (consistency across platforms)
- shazam_to_spotify_ratio ← **#1 LEADING INDICATOR**: high ratio = discovery happening but streams haven't caught up yet
- tiktok_to_spotify_ratio
- cross_platform_velocity_alignment (are all platforms trending same direction?)

**TikTok-specific**:
- tiktok_creator_tier_migration_rate: rate at which higher-tier creators adopt a sound (micro→mid→macro = signal of breakout)
- tiktok_geo_spread: number of distinct countries using sound
- tiktok_video_count_velocity

**Temporal features**:
- day_of_week, is_weekend
- days_since_release
- season (Q1-Q4 have different music patterns)
- is_holiday_period

**Genre features**:
- genre_overall_momentum (is this genre trending?)
- genre_new_entry_rate (are new artists entering this genre?)
- artist_genre_rarity (how niche is the artist within trending pool?)

### Three Prediction Horizons
- **7-day**: Next week trending prediction
- **30-day**: Next month trajectory
- **90-day**: Quarterly outlook (lower confidence, wider intervals)

### Self-Learning Loop (runs daily at 06:30 UTC)
```
1. Generate today's predictions for all horizons
2. Resolve predictions whose horizon has elapsed:
   - Compare predicted_score vs actual composite_score at horizon date
   - Calculate error metrics (MAE, RMSE, calibration)
3. Evaluate retrain triggers:
   - MAE increased >15% vs 30-day rolling average → retrain
   - PSI on any top-10 feature > 0.2 → retrain
   - KS test on prediction distribution p < 0.01 → retrain
4. If retrain triggered:
   - Pull last 180 days of training data
   - Walk-forward split: train on days 1-150, validate on 151-180
   - Train all 3 base models
   - Fit meta-learner on validation set predictions
   - Run calibration on held-out set
   - Compare new model vs champion on validation set
   - If new model wins: promote to champion, archive old
   - If new model loses: keep champion, log for investigation
5. Update prediction API with new predictions
```

### Cold Start Strategy
New entities (< 14 days of data):
- Use genre-level priors as baseline
- Weight cross-platform breadth heavily (appearing on 3+ platforms fast = strong signal)
- Apply confidence discount: max confidence = 0.5 for entities < 7 days old, 0.7 for < 14 days

### Acceptance Criteria
- 7-day predictions: MAE < 12 on 0-100 scale
- 30-day predictions: MAE < 18
- 90-day predictions: MAE < 25
- Calibration: predicted 80% confidence intervals should contain actual value ~80% of the time

---

## PHASE 6: REACT FRONTEND

Build a single-page React app that serves as an API testing dashboard AND a visual demo.

### Pages

**Dashboard** (`/`):
- Hero section: "SoundPulse" branding, current date, data freshness indicator
- Trending panel: Top 20 trending tracks/artists (toggle), real-time updating
- Mini charts: sparkline for each entity showing 7-day score trajectory
- Genre heatmap: visual grid of root categories, colored by momentum
- Prediction highlights: top 5 "about to break out" predictions with confidence bars

**Explore** (`/explore`):
- Search bar with autocomplete (hits /search endpoint)
- Genre browser: expandable tree of full taxonomy, click to filter trending
- Filtering: by platform, time range, genre, entity type
- Detail view: click any entity to see full cross-platform breakdown + predictions

**API Tester** (`/api-tester`):
- Interactive API playground
- Endpoint selector (dropdown of all endpoints)
- Parameter builder (auto-generates form fields from endpoint schema)
- Request/response viewer (formatted JSON with syntax highlighting)
- History: recent API calls with response times
- cURL export button

### Technical Requirements
- All API calls go through a `useSoundPulse` hook that handles base URL, API key injection, error handling
- API key input: stored in localStorage, settable from a settings drawer
- Responsive: works on mobile (collapsible sidebar)
- Dark mode default (music industry aesthetic)
- Loading states: skeleton screens, not spinners

---

## PHASE 7: DOCKER COMPOSE

```yaml
# docker-compose.yml
services:
  api:
    build: .
    ports: ["8000:8000"]
    depends_on: [db, redis]
    env_file: .env
    volumes: ["./config:/app/config"]
    
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: soundpulse
      POSTGRES_USER: soundpulse
      POSTGRES_PASSWORD: soundpulse_dev
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    
  celery-worker:
    build: .
    command: celery -A scrapers.scheduler worker --loglevel=info
    depends_on: [db, redis]
    env_file: .env
    
  celery-beat:
    build: .
    command: celery -A scrapers.scheduler beat --loglevel=info
    depends_on: [redis]
    env_file: .env
    
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [api]

volumes:
  pgdata:
```

---

## BUILD ORDER (execute sequentially)

1. `docker-compose.yml` + `Dockerfile` + `pyproject.toml` — get containers running
2. Database models + Alembic migrations — schema up
3. Genre taxonomy + seed script — populate genres
4. Core API endpoints (genres first, then trending, search, predictions) — API serving
5. Entity resolution service — dedup logic
6. Normalization + aggregation services — scoring pipeline
7. Spotify scraper (first data source) — initial data flowing
8. Chartmetric scraper — cross-platform coverage
9. Shazam scraper — leading indicator data
10. Remaining scrapers (Apple Music, TikTok, MusicBrainz)
11. Prediction feature engineering — build feature pipeline
12. Base models (LightGBM first, then LSTM, then XGBoost)
13. Meta-learner + calibration — ensemble
14. Training loop + drift detection — self-learning
15. React frontend — visual layer
16. Rate limiting + auth middleware — production readiness
17. End-to-end tests — confidence
18. Credential setup script — operational

---

## DECISIONS YOU CAN MAKE AUTONOMOUSLY

- Library versions and minor dependency choices
- Database index strategy (but index all foreign keys and common query filters)
- Exact Celery retry policies (use exponential backoff, max 5 retries)
- CSS/styling choices for frontend (dark mode, music industry aesthetic)
- Test fixture data
- Logging format and levels
- Git commit granularity

## DECISIONS TO ASK ENRICO ABOUT

- Chartmetric pricing tier (affects data access)
- TikTok Research API application details (needs his organization info)
- Apple Developer account (needs his Apple ID)
- Whether to deploy to AWS, GCP, or Railway (not covered in this spec — focus on local dev first)
- Custom domain for API
- Whether to add WebSocket support for real-time trending updates (nice to have, not MVP)
