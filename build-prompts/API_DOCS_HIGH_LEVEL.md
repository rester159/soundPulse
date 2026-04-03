# SoundPulse API — High-Level Documentation

> Music Intelligence API for tracking and predicting music trends across platforms.

---

## What Is SoundPulse?

SoundPulse is a REST API that aggregates trending music data from six upstream platforms (Spotify, Apple Music, TikTok, Shazam, Radio, Chartmetric), normalizes it into a unified scoring system, and serves it through clean endpoints. A built-in prediction engine forecasts which artists, tracks, and genres are about to break out.

## Core Concepts

### Entities
SoundPulse tracks two entity types: **artists** and **tracks**. Each entity is deduplicated across platforms using ISRC codes, platform-specific IDs, and fuzzy name matching. A single "Drake" entry in SoundPulse maps to his Spotify artist ID, Apple Music ID, TikTok handle, and Chartmetric profile.

### Composite Score
Every entity gets a **composite_score** (0–100) calculated as a weighted combination of its performance across all platforms:

| Platform | Weight | Rationale |
|----------|--------|-----------|
| Spotify | 0.25 | Largest streaming platform, reliable data |
| TikTok | 0.25 | Leading indicator for viral breakouts |
| Shazam | 0.15 | Strong discovery signal — people Shazam before they stream |
| Apple Music | 0.15 | Premium audience, strong in certain demographics |
| Chartmetric | 0.10 | Cross-platform aggregator, fills data gaps |
| Radio | 0.10 | Lagging but validates mainstream crossover |

### Velocity
**Velocity** measures how fast an entity's score is changing. Positive velocity = gaining momentum. Calculated as the linear slope of the last 7 daily composite scores.

### Genre Taxonomy
SoundPulse uses a proprietary hierarchical taxonomy of 850+ genres organized under 12 root categories with dot-notation IDs (e.g., `electronic.house.tech-house`). Every genre maps bidirectionally to Spotify, Apple Music, MusicBrainz, and Chartmetric genre systems.

### Predictions
The prediction engine is a three-model ensemble (LightGBM + LSTM + XGBoost) combined via Ridge meta-learner. It produces forecasts at three horizons: 7-day, 30-day, and 90-day. Predictions include a calibrated confidence score. The system self-learns daily by comparing past predictions against actual outcomes and retraining when accuracy degrades.

---

## Endpoints Overview

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/trending` | Current trending artists or tracks | API key |
| `GET` | `/search` | Full-text search across entities | API key |
| `GET` | `/predictions` | Breakout predictions | API key |
| `GET` | `/genres` | Genre taxonomy tree | API key |
| `GET` | `/genres/{id}` | Single genre detail | API key |
| `POST` | `/trending` | Ingest data from scrapers | Admin key |
| `POST` | `/predictions/feedback` | Submit ground-truth | Admin key |

---

## Authentication

All requests require an API key in the `X-API-Key` header.

```
X-API-Key: sp_live_abc123...
```

Three tiers exist: **Free** (100 req/hour), **Pro** (1,000 req/hour), **Admin** (unlimited + write access).

---

## Rate Limiting

Limits are enforced per API key via sliding window. Response headers indicate remaining quota:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 73
X-RateLimit-Reset: 2026-03-21T12:15:00Z
```

---

## Data Freshness

- Trending data updates every 4–6 hours depending on platform
- Composite scores recalculate every 30 minutes
- Predictions regenerate daily at 06:30 UTC
- Genre taxonomy updates are manual and infrequent

A `data_freshness` field in responses indicates the age of the underlying data.

---

## Error Format

All errors follow a consistent structure:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Entity not found",
    "details": {}
  }
}
```

Common codes: `RATE_LIMIT_EXCEEDED`, `UNAUTHORIZED`, `NOT_FOUND`, `VALIDATION_ERROR`, `INTERNAL_ERROR`.

---

## Architecture at a Glance

```
Upstream APIs                    SoundPulse Core                    Consumers
─────────────                    ───────────────                    ─────────
Spotify      ──┐                ┌──────────────┐
Apple Music  ──┤  Scrapers →    │  PostgreSQL   │  → REST API  →   Frontend
TikTok       ──┤  (Celery)      │  + Redis      │                  Mobile App
Shazam       ──┤                │  Cache        │                  3rd Party
Chartmetric  ──┤                └──────┬───────┘
Radio        ──┘                       │
                                Prediction Engine
                                (daily self-learning)
```

---

## Upstream Data Sources

| Source | Access Method | Cost | Key Signal |
|--------|-------------|------|------------|
| Spotify | Web API (OAuth) | Free | Stream counts, playlist adds, audio features |
| Chartmetric | REST API | $150+/mo | Cross-platform charts, artist analytics |
| Shazam | RapidAPI | $10+/mo | Discovery intent (leading indicator) |
| Apple Music | MusicKit API | $99/yr (dev account) | Premium audience behavior |
| TikTok | Research API or fallback | Free (if approved) | Viral sound adoption patterns |
| MusicBrainz | Open API | Free | Metadata, ISRC, disambiguation |
| Radio/Luminate | Enterprise API | Enterprise pricing | Mainstream validation |

---

## Quick Start

```bash
# 1. Clone and configure
git clone <repo> && cd soundpulse
cp config/.env.example .env
cp config/credentials.yaml.example config/credentials.yaml
# Edit credentials.yaml with your API keys

# 2. Start services
docker compose up -d

# 3. Run migrations and seed genres
docker compose exec api python scripts/migrate.py upgrade head
docker compose exec api python scripts/seed_genres.py

# 4. Verify
curl -H "X-API-Key: $ADMIN_KEY" http://localhost:8000/genres | jq '.genres | length'
# Should return 850+

# 5. Trigger initial data collection
docker compose exec celery-worker celery -A scrapers.scheduler call scrapers.spotify.collect

# 6. Open frontend
open http://localhost:3000
```
