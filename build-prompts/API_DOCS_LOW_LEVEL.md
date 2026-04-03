# SoundPulse API — Low-Level Technical Reference

> Exhaustive endpoint specification. Every request field, response field, query parameter, edge case, and status code.
> **This document is designed to be ingested by Claude Code as a reference during implementation.**

---

## Base URL

```
Development: http://localhost:8000/api/v1
Production:  https://api.soundpulse.io/v1
```

All endpoints are prefixed with `/api/v1`.

---

## Authentication

Every request must include:
```
X-API-Key: sp_live_{32_char_hex}
```

Key format: `sp_live_` prefix + 32 hex chars. Admin keys: `sp_admin_` prefix.

**Key lookup**: Query `api_keys` table by key hash (SHA-256). Store raw keys only at creation time; DB stores hash + last-4 chars for display.

**Key tiers**:
| Tier | Prefix | Rate Limit | Permissions |
|------|--------|-----------|-------------|
| free | `sp_live_` | 100/hr | GET endpoints only |
| pro | `sp_live_` | 1,000/hr | GET endpoints only |
| admin | `sp_admin_` | unlimited | GET + POST endpoints |

**Error on invalid/missing key**:
```json
HTTP 401
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Invalid or missing API key",
    "details": {}
  }
}
```

---

## Rate Limiting

Implementation: Redis sliding window (sorted set per key, scored by timestamp).

**Headers on every response**:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 73
X-RateLimit-Reset: 2026-03-21T12:15:00Z
```

**Error on limit exceeded**:
```json
HTTP 429
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Resets at 2026-03-21T12:15:00Z",
    "details": {
      "limit": 100,
      "remaining": 0,
      "reset_at": "2026-03-21T12:15:00Z",
      "tier": "free"
    }
  }
}
```

---

## Common Response Envelope

All successful responses:
```json
{
  "data": { ... },          // or "data": [ ... ] for lists
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2026-03-21T10:30:00Z",
    "data_freshness": "2026-03-21T10:15:00Z",  // when underlying data was last updated
    "total": 150,            // for paginated lists
    "limit": 50,
    "offset": 0
  }
}
```

---

## ENDPOINT: GET /trending

Returns currently trending artists or tracks with composite scores and per-platform breakdowns.

### Query Parameters

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `entity_type` | string | YES | — | `"artist"` or `"track"` |
| `genre` | string | no | — | Genre ID (dot-notation). Matches entity at any depth: filtering by `"electronic"` returns entities tagged `"electronic.house.deep-house"` |
| `platform` | string | no | — | Filter to single platform's data: `"spotify"`, `"apple_music"`, `"tiktok"`, `"shazam"`, `"radio"`, `"chartmetric"` |
| `time_range` | string | no | `"today"` | `"today"`, `"7d"`, `"30d"` |
| `limit` | int | no | 50 | 10–100 |
| `offset` | int | no | 0 | Pagination offset |
| `sort` | string | no | `"composite_score"` | `"composite_score"`, `"velocity"`, `"platform_rank"` |
| `min_platforms` | int | no | 1 | Minimum number of platforms entity appears on (1–6). Higher = more validated trends. |

### Response (200 OK)

```json
{
  "data": [
    {
      "entity": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "type": "track",
        "name": "Espresso",
        "artist": {
          "id": "660e8400-e29b-41d4-a716-446655440001",
          "name": "Sabrina Carpenter"
        },
        "image_url": "https://i.scdn.co/image/ab67616d0000b273...",
        "genres": ["pop.dance-pop", "pop.synth-pop"],
        "isrc": "USUM72401011",
        "platform_ids": {
          "spotify": "2qSkIjg1o9h3YT9RAgYN75",
          "apple_music": "1742990379",
          "tiktok_sound_id": "7352109850290381614"
        }
      },
      "scores": {
        "composite_score": 87.3,
        "composite_score_previous": 82.1,
        "position_change": +2,
        "velocity": 4.2,
        "acceleration": 0.8,
        "platforms": {
          "spotify": {
            "normalized_score": 91.2,
            "raw_score": 4200000,
            "rank": 2,
            "signals": {
              "streams_24h": 4200000,
              "playlist_adds_7d": 1200,
              "save_rate": 0.14
            },
            "last_updated": "2026-03-21T08:00:00Z"
          },
          "tiktok": {
            "normalized_score": 85.6,
            "raw_score": 280000,
            "rank": 5,
            "signals": {
              "video_count_24h": 28000,
              "creator_tier_distribution": {
                "nano": 0.45,
                "micro": 0.30,
                "mid": 0.15,
                "macro": 0.08,
                "mega": 0.02
              },
              "geo_spread": 42
            },
            "last_updated": "2026-03-21T06:00:00Z"
          },
          "shazam": {
            "normalized_score": 78.4,
            "raw_score": 52000,
            "rank": 8,
            "signals": {
              "shazams_24h": 52000,
              "shazam_to_spotify_ratio": 0.012
            },
            "last_updated": "2026-03-21T06:00:00Z"
          },
          "apple_music": {
            "normalized_score": 82.0,
            "raw_score": null,
            "rank": 4,
            "signals": {},
            "last_updated": "2026-03-21T02:00:00Z"
          }
        },
        "platform_count": 4
      },
      "sparkline_7d": [72.1, 74.5, 76.2, 79.8, 82.1, 85.0, 87.3]
    }
  ],
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2026-03-21T10:30:00Z",
    "data_freshness": "2026-03-21T10:15:00Z",
    "total": 500,
    "limit": 50,
    "offset": 0,
    "time_range": "today",
    "entity_type": "track",
    "filters_applied": {
      "genre": null,
      "platform": null,
      "min_platforms": 1
    }
  }
}
```

### Edge Cases
- If `genre` filter matches no entities → return empty `data: []` with `total: 0`, NOT 404
- If `platform` filter specified, `composite_score` is still the multi-platform composite (not the single-platform score). The platform filter just limits which entities appear (must have data on that platform).
- `sparkline_7d` may have `null` entries for days with no data (new entities)
- `position_change` is relative to same `time_range` in previous period (today vs yesterday, this week vs last week)

### Caching
- `time_range=today`: cache 15 minutes
- `time_range=7d`: cache 1 hour
- `time_range=30d`: cache 6 hours
- Cache key: `trending:{entity_type}:{genre}:{platform}:{time_range}:{sort}:{limit}:{offset}:{min_platforms}`

---

## ENDPOINT: POST /trending

**Admin only.** Ingests raw data from scrapers.

### Request Body

```json
{
  "platform": "spotify",
  "entity_type": "track",
  "entity_identifier": {
    "spotify_id": "2qSkIjg1o9h3YT9RAgYN75",
    "apple_music_id": null,
    "tiktok_sound_id": null,
    "isrc": "USUM72401011",
    "title": "Espresso",
    "artist_name": "Sabrina Carpenter",
    "artist_spotify_id": "74KM79TiuVKeVCqs8QtB0B"
  },
  "raw_score": 4200000,
  "rank": 2,
  "signals": {
    "streams_24h": 4200000,
    "playlist_adds_7d": 1200,
    "save_rate": 0.14
  },
  "snapshot_date": "2026-03-21"
}
```

### Field Details

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `platform` | string | YES | One of: `spotify`, `apple_music`, `tiktok`, `shazam`, `radio`, `chartmetric` |
| `entity_type` | string | YES | `"artist"` or `"track"` |
| `entity_identifier` | object | YES | At least one platform ID or title+artist_name combo |
| `entity_identifier.spotify_id` | string | no | Spotify track/artist ID |
| `entity_identifier.apple_music_id` | string | no | Apple Music ID |
| `entity_identifier.tiktok_sound_id` | string | no | TikTok sound ID |
| `entity_identifier.isrc` | string | no | ISRC (tracks only) |
| `entity_identifier.title` | string | no | Track title (for fuzzy matching) |
| `entity_identifier.artist_name` | string | no | Artist name (for fuzzy matching) |
| `entity_identifier.artist_spotify_id` | string | no | Artist Spotify ID (for track→artist linking) |
| `raw_score` | float | no | Platform-specific raw metric (streams, plays, etc) |
| `rank` | int | no | Platform chart position |
| `signals` | object | no | Platform-specific signal breakdown (freeform) |
| `snapshot_date` | string (YYYY-MM-DD) | YES | Date this data represents |

### Entity Resolution Logic (executed on POST)

```
Priority order for matching existing entities:

1. Platform ID match (exact):
   - If entity_identifier.spotify_id matches existing Track.spotify_id → match
   - Same for apple_music_id, tiktok_sound_id
   
2. ISRC match (exact):
   - If entity_identifier.isrc matches existing Track.isrc → match
   
3. Fuzzy name match:
   - Normalize: lowercase, strip "(feat. ...)", strip "- Remaster", strip punctuation
   - Compare title + artist_name using Levenshtein ratio
   - Threshold: ratio ≥ 0.85 → match
   - If multiple matches above threshold, pick highest ratio
   
4. No match:
   - Create new Artist/Track entity
   - If platform ID available, store it
   - Queue MusicBrainz enrichment task for metadata fill
```

### Normalization Logic (executed on POST)

```
Per-platform normalization to 0-100 scale:

For each (platform, entity_type) pair, maintain rolling 90-day statistics:
  - p99: 99th percentile of raw_scores
  - p50: 50th percentile
  - p5: 5th percentile

normalized_score = ((raw_score - p5) / (p99 - p5)) * 100
Clamp to [0, 100].

Special case: If raw_score is null (rank-only data like Apple Music):
  normalized_score = max(0, 100 - (rank * 2))  // rank 1 = 98, rank 50 = 0
```

### Composite Score Recalculation

After any POST, schedule composite recalculation for the affected entity:

```
composite_score = Σ (platform_weight[p] * normalized_score[p]) for all platforms
                  / Σ (platform_weight[p]) for platforms with data

Only include platforms with data from the last 48 hours.
```

### Response (201 Created)

```json
{
  "data": {
    "entity_id": "550e8400-e29b-41d4-a716-446655440000",
    "entity_type": "track",
    "entity_name": "Espresso",
    "matched_by": "spotify_id",
    "is_new_entity": false,
    "normalized_score": 91.2,
    "snapshot_id": "770e8400-e29b-41d4-a716-446655440002"
  }
}
```

### Error Cases
- 400: Missing required fields, invalid platform string, invalid entity_type
- 401: Not admin key
- 409: Duplicate snapshot (same entity + platform + date already exists) → return existing snapshot_id
- 422: entity_identifier has no usable identifiers (all null and no title+artist_name)

---

## ENDPOINT: GET /search

Full-text search across artists and tracks.

### Query Parameters

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `q` | string | YES | — | Search query (min 2 chars) |
| `type` | string | no | `"all"` | `"artist"`, `"track"`, `"all"` |
| `limit` | int | no | 20 | 1–50 |

### Implementation

```sql
-- PostgreSQL full-text search with trigram fallback
-- First try tsvector match
SELECT * FROM artists 
WHERE to_tsvector('english', name) @@ plainto_tsquery('english', :q)

UNION ALL

SELECT * FROM tracks
WHERE to_tsvector('english', title || ' ' || artist_name) @@ plainto_tsquery('english', :q)

-- If < 5 results, supplement with trigram similarity
SELECT * FROM artists
WHERE similarity(name, :q) > 0.3
ORDER BY similarity(name, :q) DESC

-- Requires: CREATE EXTENSION pg_trgm;
-- And GIN indexes on tsvector columns + GiST indexes on name/title for trigram
```

### Response (200 OK)

```json
{
  "data": [
    {
      "entity": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "type": "track",
        "name": "Espresso",
        "artist": {
          "id": "660e8400-e29b-41d4-a716-446655440001",
          "name": "Sabrina Carpenter"
        },
        "genres": ["pop.dance-pop"],
        "image_url": "https://..."
      },
      "latest_scores": {
        "composite_score": 87.3,
        "velocity": 4.2,
        "platform_count": 4,
        "last_updated": "2026-03-21T10:15:00Z"
      },
      "relevance_score": 0.95
    }
  ],
  "meta": {
    "request_id": "req_def456",
    "timestamp": "2026-03-21T10:30:00Z",
    "total": 3,
    "query": "espresso sabrina",
    "type_filter": "all"
  }
}
```

### Edge Cases
- Query < 2 chars → 400 VALIDATION_ERROR
- No results → empty `data: []`, NOT 404
- Special characters in query are stripped before search
- Cache: 5 minutes, key: `search:{hash(q)}:{type}:{limit}`

---

## ENDPOINT: GET /predictions

Returns current breakout predictions.

### Query Parameters

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `entity_type` | string | no | `"all"` | `"artist"`, `"track"`, `"genre"`, `"all"` |
| `horizon` | string | no | `"7d"` | `"7d"`, `"30d"`, `"90d"` |
| `genre` | string | no | — | Filter by genre ID |
| `min_confidence` | float | no | 0.0 | 0.0–1.0, filter predictions below threshold |
| `limit` | int | no | 50 | 10–200 |
| `offset` | int | no | 0 | Pagination |
| `sort` | string | no | `"predicted_change"` | `"predicted_change"`, `"confidence"`, `"predicted_score"` |

### Response (200 OK)

```json
{
  "data": [
    {
      "prediction_id": "880e8400-e29b-41d4-a716-446655440003",
      "entity": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "type": "artist",
        "name": "Emerging Artist X",
        "genres": ["hip-hop.trap.melodic-trap"],
        "image_url": "https://..."
      },
      "horizon": "7d",
      "current_score": 32.5,
      "predicted_score": 67.8,
      "predicted_change_pct": 108.6,
      "predicted_change_abs": 35.3,
      "confidence": 0.78,
      "confidence_interval": {
        "low": 52.1,
        "high": 83.5
      },
      "top_signals": [
        {
          "feature": "shazam_to_spotify_ratio",
          "value": 3.2,
          "impact": "high",
          "description": "Shazam activity 3.2x higher than streaming suggests — strong discovery signal"
        },
        {
          "feature": "tiktok_creator_tier_migration",
          "value": 0.45,
          "impact": "high",
          "description": "Mid-tier and macro creators adopting sound at accelerating rate"
        },
        {
          "feature": "cross_platform_velocity_alignment",
          "value": 0.91,
          "impact": "medium",
          "description": "All platforms trending in same direction — synchronized momentum"
        }
      ],
      "model_version": "v0.3.1",
      "predicted_at": "2026-03-21T06:30:00Z",
      "horizon_ends_at": "2026-03-28T06:30:00Z"
    }
  ],
  "meta": {
    "request_id": "req_ghi789",
    "timestamp": "2026-03-21T10:30:00Z",
    "total": 150,
    "limit": 50,
    "offset": 0,
    "horizon": "7d",
    "model_version": "v0.3.1",
    "model_accuracy": {
      "mae_7d": 10.2,
      "mae_30d": 16.8,
      "calibration_score": 0.82
    }
  }
}
```

### Field Explanations

- `predicted_change_pct`: `((predicted_score - current_score) / current_score) * 100`
- `predicted_change_abs`: `predicted_score - current_score`
- `confidence`: Calibrated via isotonic regression. A confidence of 0.80 means "80% of the time, the actual score falls within the confidence_interval"
- `confidence_interval`: {low, high} representing the predicted range at the stated confidence level
- `top_signals`: The 3 most influential features for this prediction (from SHAP values or feature importance). Each has a human-readable description.
- `model_accuracy`: Rolling 30-day accuracy metrics of the active model

### Edge Cases
- Predictions for `entity_type=genre` use genre IDs instead of UUIDs for `entity.id`
- New entities (< 7 days) have max confidence capped at 0.50
- If prediction model hasn't run today (e.g., training loop failure), serve yesterday's predictions with a `stale_predictions: true` flag in meta
- Cache: 1 hour (predictions update daily)

---

## ENDPOINT: POST /predictions/feedback

**Admin only.** Submit manual ground-truth data for prediction resolution.

### Request Body

```json
{
  "prediction_id": "880e8400-e29b-41d4-a716-446655440003",
  "actual_score": 72.1,
  "notes": "Manual correction: viral TikTok moment on day 5 caused spike not captured by automated resolution"
}
```

### Response (200 OK)

```json
{
  "data": {
    "prediction_id": "880e8400-e29b-41d4-a716-446655440003",
    "predicted_score": 67.8,
    "actual_score": 72.1,
    "error": -4.3,
    "resolved_at": "2026-03-21T10:30:00Z"
  }
}
```

### Error Cases
- 404: prediction_id not found
- 409: prediction already resolved (actual_score already set)
- 400: actual_score not in 0-100 range

---

## ENDPOINT: GET /genres

Returns the full genre taxonomy.

### Query Parameters

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `root` | string | no | — | Filter to single root category (e.g., `"electronic"`) |
| `depth` | int | no | — | Max depth to return (0 = roots only, 1 = roots + first children, etc.) |
| `status` | string | no | `"active"` | `"active"`, `"deprecated"`, `"proposed"`, `"all"` |
| `flat` | bool | no | `false` | If true, return flat list instead of nested tree |

### Response (200 OK) — Tree format (default)

```json
{
  "data": {
    "genres": [
      {
        "id": "electronic",
        "name": "Electronic",
        "depth": 0,
        "status": "active",
        "genre_count": 120,
        "children": [
          {
            "id": "electronic.house",
            "name": "House",
            "depth": 1,
            "status": "active",
            "genre_count": 35,
            "children": [
              {
                "id": "electronic.house.deep-house",
                "name": "Deep House",
                "depth": 2,
                "status": "active",
                "genre_count": 8,
                "children": [...]
              },
              {
                "id": "electronic.house.tech-house",
                "name": "Tech House",
                "depth": 2,
                "status": "active",
                "genre_count": 5,
                "children": [...]
              }
            ]
          }
        ]
      }
    ],
    "root_categories": [
      "pop", "rock", "electronic", "hip-hop", "r-and-b", "latin",
      "country", "jazz", "classical", "african", "asian", "caribbean"
    ],
    "total_genres": 853
  },
  "meta": {
    "request_id": "req_jkl012",
    "timestamp": "2026-03-21T10:30:00Z"
  }
}
```

### Cache: 24 hours

---

## ENDPOINT: GET /genres/{genre_id}

Returns a single genre with full cross-platform mappings and relationships.

### Path Parameters
- `genre_id`: Dot-notation genre ID (e.g., `electronic.house.tech-house`)

### Response (200 OK)

```json
{
  "data": {
    "id": "electronic.house.tech-house",
    "name": "Tech House",
    "parent_id": "electronic.house",
    "root_category": "electronic",
    "depth": 2,
    "status": "active",
    "platform_mappings": {
      "spotify": ["tech house", "minimal tech house"],
      "apple_music": ["Tech House"],
      "musicbrainz": ["tech house"],
      "chartmetric": ["Tech House"]
    },
    "audio_profile": {
      "tempo_range": [120, 130],
      "energy_range": [0.6, 0.85],
      "valence_range": [0.3, 0.7],
      "danceability_range": [0.7, 0.9]
    },
    "adjacent_genres": [
      {
        "id": "electronic.house.deep-house",
        "name": "Deep House",
        "relationship": "sibling",
        "affinity": 0.85
      },
      {
        "id": "electronic.techno.minimal-techno",
        "name": "Minimal Techno",
        "relationship": "cross-branch",
        "affinity": 0.72
      }
    ],
    "children": [
      {
        "id": "electronic.house.tech-house.afro-tech",
        "name": "Afro Tech",
        "status": "active"
      },
      {
        "id": "electronic.house.tech-house.minimal-tech-house",
        "name": "Minimal Tech House",
        "status": "active"
      }
    ],
    "trending_stats": {
      "current_momentum": 72.3,
      "trending_artists_count": 45,
      "trending_tracks_count": 120,
      "7d_change": 5.2
    }
  },
  "meta": {
    "request_id": "req_mno345",
    "timestamp": "2026-03-21T10:30:00Z"
  }
}
```

### Error Cases
- 404 if genre_id doesn't exist in taxonomy

---

## DATA NORMALIZATION REFERENCE

### Per-Platform Signal Definitions

**Spotify signals** (stored in `signals_json`):
```json
{
  "streams_24h": int,           // total streams in last 24h
  "streams_7d": int,            // total streams in last 7 days
  "playlist_adds_7d": int,      // new playlist additions in 7 days
  "playlist_reach": int,        // total followers of playlists track is on
  "save_rate": float,           // saves / streams ratio
  "skip_rate": float,           // skips / plays ratio (lower = better)
  "monthly_listeners": int,     // artist only
  "follower_count": int,        // artist only
  "popularity": int             // Spotify's own 0-100 popularity metric
}
```

**TikTok signals**:
```json
{
  "video_count_24h": int,       // videos created using this sound in 24h
  "video_count_7d": int,
  "total_video_count": int,
  "creator_tier_distribution": {
    "nano": float,              // < 1K followers
    "micro": float,             // 1K - 10K
    "mid": float,               // 10K - 100K
    "macro": float,             // 100K - 1M
    "mega": float               // > 1M
  },
  "geo_spread": int,            // distinct countries
  "avg_video_views": int,
  "avg_engagement_rate": float
}
```

**Shazam signals**:
```json
{
  "shazams_24h": int,
  "shazams_7d": int,
  "chart_position": int,        // global chart position
  "country_charts": [           // countries where it charts
    {"country": "US", "position": 5},
    {"country": "GB", "position": 12}
  ],
  "shazam_to_spotify_ratio": float  // calculated: shazams_7d / spotify_streams_7d
}
```

**Apple Music signals**:
```json
{
  "chart_position": int,
  "chart_name": string,         // "Top 100: Global", "Top 100: USA", etc.
  "storefront": string          // country code
}
```

**Radio signals**:
```json
{
  "spins_24h": int,             // radio plays in 24h
  "spins_7d": int,
  "stations_count": int,        // distinct stations playing
  "audience_impressions": int,  // estimated listeners reached
  "format": string              // "CHR/Top 40", "Urban", "Country", etc.
}
```

**Chartmetric signals**:
```json
{
  "cm_artist_score": float,     // Chartmetric's proprietary artist score
  "cm_track_score": float,
  "social_mentions": int,
  "playlist_count": int,        // total playlists across platforms
  "chart_entries": int          // total chart entries across platforms
}
```

### Velocity Calculation

```python
def calculate_velocity(scores_7d: list[float]) -> float:
    """
    Linear regression slope of last 7 daily composite scores.
    Positive = gaining momentum, negative = declining.
    
    scores_7d: [oldest, ..., newest] — exactly 7 values (nulls interpolated)
    Returns: slope (units: score points per day)
    """
    if len(scores_7d) < 3:
        return 0.0
    # Fill nulls with linear interpolation
    filled = interpolate_nulls(scores_7d)
    x = np.arange(len(filled))
    slope, _ = np.polyfit(x, filled, 1)
    return round(slope, 2)
```

### Composite Score Weights

```python
PLATFORM_WEIGHTS = {
    "spotify": 0.25,
    "tiktok": 0.25,
    "shazam": 0.15,
    "apple_music": 0.15,
    "chartmetric": 0.10,
    "radio": 0.10,
}

def composite_score(platform_scores: dict[str, float]) -> float:
    """
    Weighted average of available platform scores.
    Only includes platforms with data from last 48 hours.
    Normalizes weights to sum to 1.0 based on available platforms.
    """
    available = {p: s for p, s in platform_scores.items() if s is not None}
    if not available:
        return 0.0
    total_weight = sum(PLATFORM_WEIGHTS[p] for p in available)
    return sum(PLATFORM_WEIGHTS[p] * s / total_weight for p, s in available.items())
```

---

## DATABASE INDEXES

```sql
-- Critical query indexes
CREATE INDEX idx_trending_entity_date ON trending_snapshots (entity_id, snapshot_date DESC);
CREATE INDEX idx_trending_platform_date ON trending_snapshots (platform, snapshot_date DESC);
CREATE INDEX idx_trending_composite ON trending_snapshots (composite_score DESC) WHERE composite_score IS NOT NULL;
CREATE INDEX idx_artist_spotify ON artists (spotify_id) WHERE spotify_id IS NOT NULL;
CREATE INDEX idx_artist_name_trgm ON artists USING gist (name gist_trgm_ops);
CREATE INDEX idx_track_isrc ON tracks (isrc) WHERE isrc IS NOT NULL;
CREATE INDEX idx_track_spotify ON tracks (spotify_id) WHERE spotify_id IS NOT NULL;
CREATE INDEX idx_track_title_trgm ON tracks USING gist (title gist_trgm_ops);
CREATE INDEX idx_track_fts ON tracks USING gin (to_tsvector('english', title));
CREATE INDEX idx_prediction_horizon ON predictions (horizon, predicted_at DESC);
CREATE INDEX idx_prediction_entity ON predictions (entity_id, horizon);
CREATE INDEX idx_genre_parent ON genres (parent_id);
CREATE INDEX idx_genre_root ON genres (root_category);
```

---

## PREDICTION MODEL SPECIFICATION

### Feature Vector (~70 features)

**Group 1: Momentum (per platform, 6 platforms × 5 features = 30)**
- `{platform}_score_7d_avg`
- `{platform}_velocity_7d`
- `{platform}_acceleration`
- `{platform}_score_vs_30d_avg`
- `{platform}_rank_change_7d`

**Group 2: Cross-Platform (10 features)**
- `platform_count`
- `platform_score_variance`
- `shazam_to_spotify_ratio` ← primary leading indicator
- `tiktok_to_spotify_ratio`
- `apple_to_spotify_ratio`
- `cross_platform_velocity_alignment`
- `max_platform_score`
- `min_platform_score`
- `platform_score_range`
- `weighted_platform_entropy`

**Group 3: TikTok-Specific (5 features)**
- `tiktok_creator_tier_migration_rate`
- `tiktok_geo_spread`
- `tiktok_video_count_velocity`
- `tiktok_macro_creator_adoption`
- `tiktok_avg_engagement_rate`

**Group 4: Temporal (8 features)**
- `day_of_week` (one-hot encoded → 7)
- `days_since_release`
- `is_holiday_period`
- `season_q1/q2/q3/q4`

**Group 5: Genre (7 features)**
- `genre_overall_momentum`
- `genre_new_entry_rate`
- `genre_trending_count`
- `artist_genre_rarity`
- `genre_depth`
- `genre_cross_branch_momentum` (avg momentum of adjacent genres)
- `genre_saturation` (how crowded is this genre in trending)

**Group 6: Entity History (10 features)**
- `entity_age_days`
- `peak_composite_score_ever`
- `days_since_peak`
- `score_30d_trend` (overall 30-day trajectory)
- `previous_breakout_count` (times entity exceeded 80 composite score)
- `avg_time_between_peaks`
- `current_streak_days` (consecutive days of positive velocity)
- `highest_platform_ever`
- `fastest_rise_rate_ever`
- `recovery_rate` (how fast entity rebounds after dips)

### Model Ensemble

```
LightGBM (tabular)     → prediction_lgbm
LSTM+Attention (seq)    → prediction_lstm  
XGBoost (interactions)  → prediction_xgb

Ridge Meta-Learner:
  final_prediction = α * prediction_lgbm + β * prediction_lstm + γ * prediction_xgb
  (α, β, γ learned via Ridge regression on validation set predictions)

Isotonic Regression (calibration):
  calibrated_confidence = isotonic_model.predict(raw_confidence)
```

### Retraining Triggers (any one triggers retrain)
1. 7-day rolling MAE increases > 15% over 30-day rolling MAE
2. Population Stability Index (PSI) > 0.2 on any top-10 feature
3. Kolmogorov-Smirnov test on prediction distribution: p < 0.01
4. Manual trigger via admin endpoint

---

## ERROR CODE REFERENCE

| HTTP | Code | When |
|------|------|------|
| 400 | `VALIDATION_ERROR` | Invalid params, missing required fields |
| 401 | `UNAUTHORIZED` | Missing/invalid API key |
| 403 | `FORBIDDEN` | Valid key but insufficient permissions (e.g., free key hitting POST) |
| 404 | `NOT_FOUND` | Entity or genre not found |
| 409 | `CONFLICT` | Duplicate resource (e.g., duplicate snapshot) |
| 422 | `UNPROCESSABLE_ENTITY` | Valid JSON but semantically invalid (e.g., no usable identifiers) |
| 429 | `RATE_LIMIT_EXCEEDED` | Rate limit hit |
| 500 | `INTERNAL_ERROR` | Unexpected server error |
| 503 | `SERVICE_UNAVAILABLE` | Database or Redis down |
