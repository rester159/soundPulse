# SoundPulse Technical Specification
## Fully Autonomous Virtual Record Label

**Version 1.0** — April 2026

This document specifies every system, API integration, data model, and automated workflow required to run a virtual record label with zero human intervention.

---

## Table of Contents

1. System Architecture Overview
2. Data Collection Layer (Phase 1 — BUILT)
3. Intelligence Layer (Phase 2 — IN PROGRESS)
4. Song Generation Layer (Phase 3)
5. Artist Creation & Management Layer (Phase 3)
6. Distribution Layer (Phase 3)
7. Marketing & Social Layer (Phase 3)
8. Rights & Royalty Layer (Phase 3)
9. Revenue & Analytics Layer (Phase 3)
10. AI Assistant Layer (BUILT)
11. Database Schema
12. API Reference
13. Deployment Architecture
14. Cost Model

---

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    SOUNDPULSE CORE                           │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  DATA    │  │ INTELLI- │  │  SONG    │  │ ARTIST   │   │
│  │COLLECTION│→ │  GENCE   │→ │GENERATION│→ │ CREATION │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│       ↑              │              │              │         │
│       │              ↓              ↓              ↓         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ REVENUE  │  │PREDICTION│  │DISTRIBUTE│  │MARKETING │   │
│  │& ANALYTICS│← │ MODELS  │  │          │  │& SOCIAL  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│       ↑                             │              │         │
│       │                             ↓              ↓         │
│  ┌──────────┐                 ┌──────────┐  ┌──────────┐   │
│  │ RIGHTS & │                 │ STREAMING│  │  SOCIAL  │   │
│  │ ROYALTIES│←────────────────│PLATFORMS │  │PLATFORMS │   │
│  └──────────┘                 └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Data Collection Layer

**Status: BUILT AND RUNNING**

### 2.1 Scrapers

| Scraper | Source | Frequency | Data Collected | Status |
|---|---|---|---|---|
| `chartmetric` | Chartmetric Charts API | Every 4h | Spotify/Shazam chart rankings (US), track metadata, genres | Running |
| `chartmetric_artists` | Chartmetric Artist Stats | Every 12h | Spotify followers/listeners, Instagram, TikTok, YouTube, Shazam, geographic audience | Running |
| `spotify` | Spotify Web API | Every 6h | Search-based trending across 12 genres, chart positions | Running |
| `spotify_audio` | Spotify Audio Analysis | Daily | Tempo, energy, key, mood, timbre vectors (12-dim), pitch vectors (12-dim), song structure sections | Running |
| `genius_lyrics` | Genius API + scraping | Daily | Lyrics text, theme classification (10 categories), vocabulary richness, section structure | Ready (needs GENIUS_API_KEY) |
| `kworb` | Kworb.net scraping | Daily | Spotify daily streaming charts with stream counts | Available |
| `radio` | Billboard.com scraping | Daily | Radio airplay, Hot 100, Country Airplay, Artist 100 | Available |
| `musicbrainz` | MusicBrainz API | Every 12h | ISRC codes, genre tags, release metadata | Available |

### 2.2 Data Flows

```
Chartmetric API ──→ Chart Scraper ──→ POST /api/v1/trending ──→ Entity Resolution ──→ DB
                                                                       ↓
                                                              Genre Classifier
                                                                       ↓
                                                              Composite Score Calc
                                                                       ↓
                                                              Velocity / Momentum
```

### 2.3 Entity Resolution Pipeline

1. ISRC match (exact)
2. Chartmetric ID match
3. Spotify/Platform ID match
4. Fuzzy name match (RapidFuzz, threshold >85%)
5. Disambiguation queue (manual review for low-confidence)
6. Learned blocklist (false positive exclusion)

### 2.4 Historical Backfill

- Chartmetric historical data goes back to 2020+
- Backfill script: `scripts/backfill_deep.py --days 730`
- Rate: ~350 records/day, 4 chart types
- 2-year backfill = ~255K snapshots
- Run via admin endpoint: `POST /api/v1/admin/backfill`

---

## 3. Intelligence Layer

**Status: IN PROGRESS**

### 3.1 Prediction Models

#### 3.1.1 Song Success Predictor

**Purpose:** Predict whether a track will break into the top-N charts within a given horizon.

**Architecture:**
- Phase 2: LightGBM (tabular features)
- Phase 3: Three-model ensemble (LightGBM + LSTM + XGBoost) with Ridge meta-learner

**Features (~70):**
- Per-platform momentum (7 platforms x 5 features = 35): score_7d_avg, velocity_7d, acceleration, score_vs_30d_avg, rank_change_7d
- Cross-platform (10): platform_count, score_variance, Shazam/Spotify ratio, TikTok/Spotify ratio, velocity_alignment, score_entropy
- Temporal (8): day_of_week, days_since_release, is_weekend, season (4 one-hot)
- Genre (7): genre_momentum, new_entry_rate, trending_count, rarity, saturation
- Entity history (10): age, peak_composite, days_since_peak, previous_breakout_count, streak, volatility

**Song DNA features (from audio + lyrics):**
- tempo, energy, valence, danceability, key, mode, acousticness
- chorus_ratio, vocabulary_richness, primary_theme, section_count

**Targets:**
| Target | Horizon | Threshold |
|---|---|---|
| spotify_top_50_us | 7 days | Top 50 |
| shazam_top_200_us | 7 days | Top 200 |
| billboard_hot_100 | 14 days | Top 100 |
| cross_platform_breakout | 14 days | 3+ platforms simultaneously |

**Training:**
- Daily at 3am UTC via Celery beat
- Temporal train/test split (80/20 by date)
- Minimum 500 labeled samples required
- Auto-retrain when 7-day precision drops >5% below 30-day moving average
- Model saved to `ml/saved_models/`

**Cold start:**
- <7 days history: rule-based heuristic, max confidence 0.5
- 7-14 days: ensemble with confidence cap 0.7
- 14+ days: full ensemble

#### 3.1.2 Artist Success Predictor

**Purpose:** Predict whether a proposed artist persona will gain traction in a given genre niche.

**Training data:** Real artist profiles from Chartmetric — demographic patterns, genre associations, visual aesthetics, social growth trajectories.

**Inputs:**
- Proposed genre niche
- Target demographic
- Persona type (mysterious, relatable, provocative, wholesome, etc.)
- Visual aesthetic category
- Market (US, UK, Global, Latin, K-pop, etc.)

**Output:**
- Predicted 90-day follower growth rate
- Audience engagement probability
- Genre-persona fit score

**This model is Phase 3 — needs significant real-artist training data from Chartmetric artist stats scraper.**

### 3.2 Genre Intelligence

- 850+ genres in hierarchical taxonomy
- 12 root categories: Pop, Rock, Electronic, Hip-Hop, R&B, Latin, Country, Jazz, Classical, African, Asian, Caribbean
- Bidirectional mappings to Spotify, Apple Music, MusicBrainz, Chartmetric
- Genre opportunity score = trending velocity x inverse saturation
- Per-genre sonic profile (average audio features across trending tracks)

### 3.3 Blueprint Generation

**Endpoint:** `POST /api/v1/blueprint/generate`

**Input:** `{ genre: "melodic.trap", model: "suno" }`

**Process:**
1. Query last 30-60 days of trending snapshots for the genre
2. Aggregate Song DNA across top performers
3. Compute average sonic profile (tempo, key, energy, mood, etc.)
4. Detect dominant lyrical themes
5. Generate model-specific prompt

**Output:**
```json
{
  "blueprint": {
    "genre": "melodic.trap",
    "sonic_profile": { "tempo": 145, "key": "C#", "mode": "minor", "energy": 0.72, "valence": 0.28 },
    "lyrical_profile": { "top_themes": ["introspection", "heartbreak"], "vocabulary_richness": 0.42 },
    "recommendation": { "mood": "dark, melancholic", "structure": "[Intro][Verse][Chorus]..." }
  },
  "prompt": "STYLE: Melodic trap, 145 BPM, C# minor...\n\n[Verse 1]\n..."
}
```

### 3.4 Model Validation / Backtesting

**Endpoint:** `GET /api/v1/backtesting/results`

For each monthly evaluation period:
1. Use data before that date to predict
2. Compare against what actually happened
3. Track MAE, RMSE, precision, recall, F1, AUC-ROC
4. Filterable by genre and entity type
5. Frontend visualization: predicted vs actual over time

---

## 4. Song Generation Layer

**Status: Phase 3 — NOT YET BUILT**

### 4.1 Generation Pipeline

```
Blueprint ──→ Artist DNA Merge ──→ Prompt Assembly ──→ Generation API ──→ Audio File
                                                              │
                                                    ┌─────────┴──────────┐
                                                    │ Quality Check      │
                                                    │ - Duration OK?     │
                                                    │ - No silence?      │
                                                    │ - Genre match?     │
                                                    │ - Audio features   │
                                                    │   match blueprint? │
                                                    └─────────┬──────────┘
                                                              │
                                                    Pass ──→ Distribution Pipeline
                                                    Fail ──→ Regenerate (max 3 attempts)
```

### 4.2 Music Generation APIs

#### Primary: Suno (via third-party wrapper)

**Endpoint:** `POST https://api.sunoapi.org/v1/songs/generate` (or similar wrapper)

**Request:**
```json
{
  "style": "{artist_dna.production_style}, {blueprint.tempo} BPM, {blueprint.key_display}, {blueprint.mood}",
  "prompt": "[Verse 1]\n{generated_lyrics}\n\n[Chorus]\n{generated_hook}",
  "vocalGender": "{artist_dna.gender}",
  "negativeTags": "{artist_dna.anti_influences}",
  "styleWeight": 0.8,
  "model": "chirp-v5-5"
}
```

**Response:** Audio file URL (MP3/WAV), ~30-40 seconds for streaming, 2-3 minutes for download.

**Cost:** ~$0.05-0.10 per generation (Suno Pro subscription + API wrapper fees)

#### Secondary: SOUNDRAW

**Endpoint:** `POST https://soundraw.io/api/v2/musics/compose`

**Request:**
```json
{
  "mood": "Sad",
  "genre": "Hip Hop",
  "tempo": 145,
  "energy_levels": "medium",
  "length": 180
}
```

**Response:** Audio file URL. Royalty-free.

#### Tertiary: MusicGen (self-hosted, instrumental only)

```python
from audiocraft.models import MusicGen
model = MusicGen.get_pretrained("facebook/musicgen-melody")
model.set_generation_params(duration=30, temperature=0.8)
wav = model.generate_with_chroma(descriptions=["melodic trap, dark mood, 145 BPM"], melody_wavs=reference)
```

### 4.3 Lyrics Generation

Before sending to Suno, generate lyrics using Groq/Llama:

**Prompt template:**
```
Write song lyrics for a {genre} track.
Theme: {blueprint.lyrical_profile.primary_theme}
Mood: {blueprint.sonic_profile.mood}
Vocabulary style: {vocabulary_description}
Structure: {blueprint.recommendation.structure}
Artist voice: {artist_dna.lyrical_voice}

Write in the style of {artist_dna.influences}, maintaining {artist_dna.persona} voice.
Include section headers [Verse 1], [Chorus], [Bridge], etc.
```

### 4.4 Quality Assurance

After generation, analyze the output:
1. Run Spotify Audio Features API on the generated audio (or local equivalent)
2. Compare against blueprint: tempo within ±10%, energy within ±0.15, valence within ±0.15
3. Check duration (>90 seconds, <300 seconds)
4. Check for silence gaps (>3 seconds of silence = reject)
5. If fail: regenerate with adjusted parameters (max 3 attempts)
6. If 3 fails: flag for human review or skip this blueprint

---

## 5. Artist Creation & Management Layer

**Status: Phase 3 — NOT YET BUILT**

### 5.1 Artist Creation Pipeline

```
Genre Opportunity Detected (no suitable existing artist)
        │
        ▼
Artist Success Predictor: "What persona works for this genre?"
        │
        ▼
Generate Artist Profile:
  ├── Demographics (age, gender, ethnicity, provenance)
  ├── Name generation (Groq/Llama: genre-appropriate stage name)
  ├── Backstory generation (Groq/Llama: compelling narrative)
  ├── Voice DNA (timbre, style, accent, autotune, ad-libs)
  ├── Visual DNA (face, fashion, color palette, art direction)
  ├── Genre home + influences + anti-influences
  ├── Social voice (posting style, personality traits)
  └── Lyrical voice (themes, vocabulary, perspective)
        │
        ▼
Generate Visual Assets:
  ├── Base portrait (Midjourney/DALL-E/Flux: consistent face)
  ├── Profile photos (3-5 variations for different platforms)
  ├── Banner images (YouTube, Spotify, social media)
  └── Store reference image ID for future consistency
        │
        ▼
Create Platform Accounts:
  ├── Spotify for Artists (manual initially, automate later)
  ├── TikTok account
  ├── Instagram account
  ├── YouTube channel
  └── Store handles in artist profile
```

### 5.2 Artist Decision Model

When a new song blueprint is ready:

```python
def decide_artist(blueprint: Blueprint, roster: list[Artist]) -> Artist | NewArtistSpec:
    candidates = []
    for artist in roster:
        genre_match = compute_genre_overlap(blueprint.genre, artist.genre_home)
        if genre_match < 0.5:
            continue

        coherence = predict_brand_coherence(artist.catalog, blueprint)
        audience_momentum = artist.follower_growth_rate_30d
        time_since_last = days_since(artist.last_release_date)
        cadence_ok = time_since_last >= 14  # min 2 weeks between releases

        if cadence_ok:
            score = 0.4 * genre_match + 0.3 * coherence + 0.3 * audience_momentum
            candidates.append((artist, score))

    if candidates:
        best_artist, best_score = max(candidates, key=lambda x: x[1])
        if best_score > 0.6:
            return best_artist

    # No suitable existing artist — create new one
    return generate_new_artist_spec(blueprint)
```

### 5.3 Artist Data Model

```sql
CREATE TABLE ai_artists (
    id UUID PRIMARY KEY,
    stage_name VARCHAR(200) NOT NULL,
    legal_name VARCHAR(200),

    -- Demographics
    age INTEGER,
    gender VARCHAR(20),
    ethnicity VARCHAR(100),
    provenance VARCHAR(500),  -- "Atlanta, raised in Seoul"
    languages TEXT[],

    -- Voice DNA (JSON)
    voice_dna JSONB NOT NULL DEFAULT '{}',
    -- { timbre, vocal_range, delivery_style, accent, autotune_level, ad_libs, suno_persona_id }

    -- Visual DNA (JSON)
    visual_dna JSONB NOT NULL DEFAULT '{}',
    -- { face_description, fashion_style, color_palette, art_direction, tattoos, reference_image_ids }

    -- Genre & Music
    genre_home TEXT[] NOT NULL,
    adjacent_genres TEXT[],
    influences TEXT[],
    anti_influences TEXT[],
    production_signature JSONB DEFAULT '{}',
    lyrical_voice JSONB DEFAULT '{}',
    -- { themes, vocabulary_level, perspective, recurring_motifs }

    -- Persona
    backstory TEXT,
    personality_traits TEXT[],
    social_voice JSONB DEFAULT '{}',
    -- { posting_style, caption_format, emoji_usage, controversy_stance }

    -- Social Accounts
    spotify_artist_id VARCHAR(100),
    tiktok_handle VARCHAR(100),
    instagram_handle VARCHAR(100),
    youtube_channel_id VARCHAR(100),

    -- Management
    status VARCHAR(20) DEFAULT 'active',  -- active, growth, mature, retired
    portfolio_role VARCHAR(20) DEFAULT 'growth',  -- growth, cash_cow, experimental
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ai_artist_releases (
    id UUID PRIMARY KEY,
    artist_id UUID REFERENCES ai_artists(id),
    track_title VARCHAR(500),
    song_dna JSONB NOT NULL,  -- full blueprint used
    generation_model VARCHAR(50),  -- suno, udio, soundraw
    generation_prompt TEXT,
    audio_file_url VARCHAR(1000),
    cover_art_url VARCHAR(1000),

    -- Distribution
    distributed_at TIMESTAMPTZ,
    distribution_service VARCHAR(50),  -- revelator, labelgrid
    isrc VARCHAR(20),
    upc VARCHAR(20),

    -- Performance (updated by scrapers)
    total_streams BIGINT DEFAULT 0,
    spotify_streams BIGINT DEFAULT 0,
    apple_streams BIGINT DEFAULT 0,
    tiktok_creates INTEGER DEFAULT 0,
    shazam_lookups INTEGER DEFAULT 0,
    revenue_cents BIGINT DEFAULT 0,

    released_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 6. Distribution Layer

**Status: Phase 3 — NOT YET BUILT**

### 6.1 Distribution Pipeline

```
Generated Audio + Metadata
        │
        ▼
Cover Art Generation (DALL-E API)
  Input: song mood + artist visual DNA + color palette
  Output: 3000x3000 JPEG for DSP requirements
        │
        ▼
Metadata Assembly:
  ├── Track title (from blueprint or Groq-generated)
  ├── Artist name (from artist profile)
  ├── ISRC code (auto-generated or from distributor)
  ├── UPC code (from distributor)
  ├── Genre tags (from blueprint)
  ├── Release date (optimized by genre-timing model)
  ├── Copyright: "© 2026 SoundPulse Records"
  ├── Label: "SoundPulse Records"
  └── Composer/lyricist credits
        │
        ▼
Distribution API (Revelator or LabelGrid):
  POST /releases
  {
    audio_file: <WAV upload>,
    metadata: { title, artist, isrc, genre, ... },
    release_date: "2026-05-15",
    territories: ["worldwide"],
    platforms: ["spotify", "apple_music", "tiktok", "youtube", "amazon", "deezer", "tidal"]
  }
        │
        ▼
Delivery Confirmation → Store release ID in database
```

### 6.2 Distribution API Integration

**Primary: Revelator**
- Endpoint: `https://api.revelator.com/v2/` (docs at developers.revelator.com)
- Auth: OAuth2 bearer token
- Upload: multipart form with audio file + JSON metadata
- Delivery tracking: webhook or polling

**Backup: LabelGrid**
- Endpoint: `https://api.labelgrid.com/v1/` (docs at docs.labelgrid.com)
- Auth: API key
- Sandbox available for testing
- DDEX feed support for automated catalog ingestion

### 6.3 Release Timing Optimization

The genre-timing model recommends optimal release dates:

- **Friday releases** for Spotify algorithmic playlist consideration (New Music Friday)
- **Genre-specific windows:** EDM peaks Thursday/Friday, Hip-Hop performs well Monday
- **Avoid:** Major artist release dates (detect from Chartmetric upcoming releases)
- **TikTok teaser:** 3 days before full release
- **Pre-save campaign:** 7 days before release

---

## 7. Marketing & Social Layer

**Status: Phase 3 — NOT YET BUILT**

### 7.1 TikTok Marketing Pipeline

```
Song Generated
        │
        ▼
Extract Hook Clip:
  - Analyze audio for catchiest 15-second segment
  - Use section analysis (chorus typically) or highest-energy segment
  - Apply TikTok-optimized compression
        │
        ▼
Generate TikTok Video:
  - Lyric overlay on background (artist visual DNA colors)
  - Audio visualizer animation
  - Or: AI-generated video clip using Runway/Pika
        │
        ▼
Post to TikTok:
  - TikTok Content Posting API (developer access)
  - Caption: generated by Groq using artist social voice
  - Hashtags: genre + trending + custom
  - Sound: link to full track
        │
        ▼
Monitor Performance:
  - Track view count, likes, shares, sound usage
  - If sound gets adopted by creators → signal to boost
  - Feed performance data back to blueprint model
```

### 7.2 Social Content Calendar

For each active artist, generate and post:

| Day | Platform | Content Type | Generated By |
|---|---|---|---|
| Mon | Instagram | Mood photo (artist + quote) | DALL-E + Groq |
| Tue | TikTok | Behind-the-scenes narrative | Groq script + Runway video |
| Wed | Instagram Story | Poll / interactive | Template + Groq copy |
| Thu | TikTok | Teaser clip (if release upcoming) | Audio extraction + overlay |
| Fri | All platforms | Release announcement | Template + cover art |
| Sat | YouTube | Lyric video or visualizer | Audio + lyrics + motion template |
| Sun | Instagram | Fan engagement / repost | Groq-generated caption |

### 7.3 Social API Integrations

| Platform | API | Capabilities |
|---|---|---|
| **TikTok** | Content Posting API | Upload videos, set captions/hashtags, add sound |
| **Instagram** | Instagram Graph API | Post images/reels, stories, captions |
| **YouTube** | YouTube Data API v3 | Upload videos, set metadata, thumbnails |
| **Twitter/X** | X API v2 | Post text, images, schedule tweets |

---

## 8. Rights & Royalty Layer

**Status: Phase 3 — NOT YET BUILT**

### 8.1 Rights Registration Flow

```
Song Distributed
        │
        ▼
Rights Registration:
  ├── Revelator API: register rights, set ownership splits
  ├── TuneRegistry: register with ASCAP/BMI/SESAC (browser automation)
  ├── SoundExchange: digital performance royalties
  ├── The MLC: mechanical royalties
  └── YouTube Content ID: claim monetization on UGC
        │
        ▼
Royalty Monitoring:
  - Revelator API: periodic royalty report pulls
  - Track revenue per song, per platform, per territory
  - Dashboard visualization in SoundPulse UI
```

### 8.2 Copyright & AI Music Legal Considerations

- ASCAP/BMI require "meaningful human creative contribution" for AI-generated works
- SoundPulse's model: human selects genre, approves blueprint, curates output
- Recommended: have a human "sign off" on each release (can be minimal — approve/reject)
- Legal structure: form an LLC as the publishing entity
- All songs registered under "SoundPulse Records" or similar label name

---

## 9. Revenue & Analytics Layer

### 9.1 Revenue Tracking

```sql
CREATE TABLE revenue_events (
    id UUID PRIMARY KEY,
    release_id UUID REFERENCES ai_artist_releases(id),
    artist_id UUID REFERENCES ai_artists(id),
    platform VARCHAR(50),  -- spotify, apple_music, youtube, etc.
    territory VARCHAR(10),  -- US, GB, DE, etc.
    period_start DATE,
    period_end DATE,
    stream_count BIGINT DEFAULT 0,
    revenue_cents BIGINT DEFAULT 0,  -- in USD cents
    royalty_type VARCHAR(20),  -- streaming, mechanical, performance, sync
    source VARCHAR(50),  -- revelator, soundexchange, ascap, etc.
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 9.2 Unit Economics

| Metric | Value | Source |
|---|---|---|
| Average per-stream payout (Spotify) | $0.003-0.005 | Industry average |
| Average per-stream payout (Apple Music) | $0.007-0.01 | Industry average |
| Song generation cost | ~$0.10 | Suno API |
| Distribution cost per song | ~$0.50-2.00 | Revelator/LabelGrid |
| Break-even streams per song | ~500-1000 | At $0.004 avg |
| Target monthly streams per song | 10,000 | $30-40/month revenue |
| Portfolio target | 500 songs | $15K-20K/month passive |

### 9.3 Reinvestment Logic

```python
def allocate_budget(monthly_revenue: float, operating_costs: float) -> dict:
    profit = monthly_revenue - operating_costs
    if profit <= 0:
        return {"generation": 10, "marketing": 0}  # minimum viable output

    return {
        "generation": int(profit * 0.4 / 0.60),  # 40% of profit → new songs ($0.60/song all-in)
        "marketing": profit * 0.3,  # 30% → TikTok ads, playlist pitching
        "infrastructure": profit * 0.2,  # 20% → API costs, compute
        "reserve": profit * 0.1,  # 10% → cash reserve
    }
```

---

## 10. AI Assistant Layer

**Status: BUILT**

### 10.1 Architecture

```
User Question ──→ Context Gatherer (DB queries) ──→ Groq API (Llama 3.3 70B) ──→ Answer
```

### 10.2 Context Gathering

The assistant automatically queries:
- Top 15 trending tracks (last 30 days)
- Genre distribution with average scores
- Database statistics (track/artist/snapshot counts)
- Scraper health status
- Conversation history (last 6 messages)

### 10.3 Capabilities

- "What genres are trending?" → queries genre distribution
- "What should a Christian rock artist look like?" → uses genre data + artist success model
- "Compare song A vs song B" → queries both entities' performance data
- "Generate a blueprint for indie pop" → triggers blueprint API internally
- "How much revenue has artist X generated?" → queries revenue_events (Phase 3)

---

## 11. Database Schema Summary

### Current Tables (BUILT)
- `artists` — artist entities with platform IDs, genres
- `tracks` — track entities with audio features, platform IDs
- `trending_snapshots` — daily snapshot data per entity per platform
- `predictions` — stored predictions with confidence and actual outcomes
- `backtest_results` — model validation results per evaluation period
- `genres` — 850+ genre taxonomy (hierarchical)
- `scraper_configs` — scraper scheduling and status
- `api_keys` — API authentication
- `feedback` — prediction feedback for model improvement

### Phase 3 Tables (TO BUILD)
- `ai_artists` — AI-generated artist profiles (full persona)
- `ai_artist_releases` — songs released by AI artists
- `revenue_events` — royalty and streaming revenue tracking
- `social_posts` — scheduled/posted social media content
- `generation_logs` — song generation attempts and quality scores

---

## 12. Cron Schedule (Complete)

| Task | Schedule | What It Does |
|---|---|---|
| Chartmetric charts | Every 4h | Scrape trending chart data |
| Chartmetric artist stats | Every 12h | Scrape social/streaming metrics per artist |
| Spotify search | Every 6h | Search-based trending discovery |
| Spotify audio analysis | Daily | Deep audio features for new tracks |
| Genius lyrics | Daily | Lyrics + theme extraction |
| Model training | Daily 3am UTC | Retrain prediction model |
| Prediction generation | Every 6h | Predict for top 50 entities |
| Backtesting | Daily 4:30am UTC | Evaluate model accuracy |
| **Phase 3 additions:** | | |
| Song generation | Daily 6am UTC | Generate songs from top blueprints |
| Distribution check | Daily 9am UTC | Submit ready songs to distribution |
| Social posting | Per artist schedule | Post marketing content |
| Revenue collection | Weekly | Pull royalty reports |
| Artist portfolio review | Weekly | Evaluate artist performance, create/retire |

---

## 13. Deployment Architecture

### Current (RUNNING)
- **Railway** — 5 services: API, UI, Celery Worker, Celery Beat, Redis
- **Neon** — Serverless PostgreSQL
- **GitHub** — Auto-deploy on push to `main`

### Phase 3 Additions
- **GPU compute** — for MusicGen self-hosted (if needed), or use Replicate
- **Object storage** — S3 or Railway volumes for generated audio files
- **CDN** — for serving audio files and images

---

## 14. Cost Model

### Monthly Operating Costs by Phase

| Phase | Infrastructure | APIs | Generation | Distribution | Total |
|---|---|---|---|---|---|
| Phase 1 (now) | $70 | $360 | $0 | $0 | **$430** |
| Phase 2 | $170 | $400 | $0 | $0 | **$570** |
| Phase 3 (50 songs/mo) | $300 | $400 | $30 | $100 | **$830** |
| Phase 3 (500 songs/mo) | $500 | $400 | $300 | $1,000 | **$2,200** |
| Phase 3 (5000 songs/mo) | $2,000 | $400 | $3,000 | $5,000 | **$10,400** |

### Revenue Projection

| Songs in Catalog | Avg Streams/Song/Month | Revenue/Month | Net After Costs |
|---|---|---|---|
| 50 | 1,000 | $200 | -$630 |
| 200 | 3,000 | $2,400 | +$1,570 |
| 500 | 5,000 | $10,000 | +$7,800 |
| 1,000 | 10,000 | $40,000 | +$29,600 |
| 5,000 | 10,000 | $200,000 | +$189,600 |

**Break-even:** ~200 songs in catalog at 3K avg streams/month = ~4-6 months after Phase 3 launch.

---

*This specification will be updated as each component is built and validated.*
