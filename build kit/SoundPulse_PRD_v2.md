# SoundPulse
## A Fully Autonomous Virtual Record Label

**Complete Product & Technical Specification** — April 2026

*SoundPulse is a virtual record label with zero employees. It analyzes what makes music succeed, generates songs that will succeed, distributes them to every platform, and collects the royalties. No humans in the loop.*

---

## Table of Contents

### Part I — Vision & Strategy
1. [The Vision](#1-the-vision)
2. [The Complete Pipeline](#2-the-complete-pipeline)
3. [Artist Portfolio Strategy](#3-artist-portfolio-strategy)
4. [Phased Rollout](#4-phased-rollout)
5. [Success Metrics](#5-success-metrics)
6. [Unit Economics & Revenue Model](#6-unit-economics--revenue-model)

### Part II — Intelligence & Data
7. [Data Collection Layer](#7-data-collection-layer)
8. [Song DNA — The Complete Feature Set](#8-song-dna--the-complete-feature-set)
9. [Genre Intelligence](#9-genre-intelligence)
10. [Prediction Models](#10-prediction-models)
11. [Blueprint Generation](#11-blueprint-generation)
12. [Model Validation & Backtesting](#12-model-validation--backtesting)

### Part III — Creation & Production
13. [Song Generation](#13-song-generation)
14. [Lyrics Generation](#14-lyrics-generation)
15. [Artist Creation & Management](#15-artist-creation--management)
16. [Visual Identity & Image Generation](#16-visual-identity--image-generation)

### Part IV — Distribution & Revenue
17. [Distribution](#17-distribution)
18. [Marketing & Social](#18-marketing--social)
19. [Rights, Royalties & Legal](#19-rights-royalties--legal)
20. [Revenue & Analytics](#20-revenue--analytics)

### Part V — Platform & Infrastructure
21. [AI Assistant](#21-ai-assistant)
22. [API Reference](#22-api-reference)
23. [Database Schema](#23-database-schema)
24. [Deployment Architecture](#24-deployment-architecture)
25. [Cron Schedule](#25-cron-schedule)
26. [Operating Costs](#26-operating-costs)
27. [External API Dependencies](#27-external-api-dependencies)

---

# Part I — Vision & Strategy

---

## 1. The Vision

SoundPulse is not a tool for record labels. It IS a record label — one that runs entirely on software.

The complete pipeline, end to end, with no human intervention:

1. **Analyze** — What sonic, cultural, and release characteristics are driving success in any given micro-genre right now?
2. **Predict** — Which artist persona + song combination has the highest probability of success?
3. **Create** — Generate the artist (if new) and the song, with consistent identity across releases
4. **Distribute** — Upload the finished track to every streaming platform via distribution API
5. **Market** — Post TikTok teasers, Instagram content, YouTube visualizers automatically
6. **Register** — Register the song with PROs for royalty collection
7. **Optimize** — Monitor performance, adjust future blueprints based on what's working
8. **Collect** — Royalties flow back automatically from streams, sync placements, and radio play
9. **Reinvest** — Revenue funds the next generation cycle

The output of SoundPulse is not a dashboard. It is revenue.

---

## 2. The Complete Pipeline

```
┌─────────────────────────────────────────────────────┐
│ 1. ANALYZE — What's working now?                     │
│    - Trending analysis per micro-genre               │
│    - Song DNA decomposition of top performers        │
│    - Artist social growth trajectory patterns        │
│    - Cross-platform cascade timing                   │
│    - Genre-level momentum and saturation detection   │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ 2. PREDICT — What will succeed?                      │
│    - Artist Success Predictor (persona → growth)     │
│    - Song Success Predictor (blueprint → streams)    │
│    - Combined score: artist_prob × song_prob         │
│    - Only green-light high-probability combinations  │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ 3. CREATE — Generate the music + artist              │
│    - Select existing artist or create new persona    │
│    - Generate Song DNA blueprint from genre trends   │
│    - Merge Artist DNA + Song DNA → generation prompt │
│    - Suno/Udio API → master audio                    │
│    - DALL-E/Flux → cover art + promo images          │
│    - Quality check: does output match blueprint?     │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ 4. DISTRIBUTE — Push to every platform               │
│    - Upload master + metadata via distribution API   │
│    - Spotify, Apple Music, TikTok, YouTube, Amazon,  │
│      Deezer, Tidal, 150+ platforms                   │
│    - Optimal release timing per genre                │
│    - Platform: Revelator or LabelGrid API            │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ 5. MARKET — Viral promotion                          │
│    - TikTok: 15-sec hook clip, 3 days before release │
│    - Instagram: mood photos, release announcements   │
│    - YouTube: lyric videos, audio visualizers        │
│    - AI-generated social content per artist persona  │
│    - Monitor viral signals, boost what's working     │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ 6. REGISTER — Royalty collection setup               │
│    - Register with PROs (ASCAP/BMI) via TuneRegistry │
│    - Publishing admin via Revelator or Songtrust     │
│    - ISRC + UPC code assignment                      │
│    - YouTube Content ID for UGC monetization         │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ 7. OPTIMIZE + COLLECT — Monitor and reinvest         │
│    - Track streams, revenue, social growth per song  │
│    - Compare actual performance vs predictions       │
│    - Feed results back to prediction model           │
│    - Reinvest revenue into next generation cycle     │
│    - Manage artist portfolio: grow / retire / evolve │
└────────────────────┬────────────────────────────────┘
                     │
                     └──── LOOP BACK TO STEP 1 ────────┘
```

### End-to-End Example

```
SoundPulse detects: "Melodic trap in C# minor at 140-150 BPM is accelerating.
  Top performers share: sparse verse → dense chorus, autotuned vocals,
  808 sub-bass, introspective/heartbreak themes, short intros (<15 sec).
  TikTok adoption rate for this profile: 3.2x average."

Artist decision: Assign to existing artist "VOIDBOY" (melodic trap, 12 songs,
  8K monthly listeners, growing). Genre match: 92%. Brand coherence: 87%.

Blueprint: 145 BPM, C# minor, energy 0.72, valence 0.28
  Themes: introspection, heartbreak. Structure: Intro-Verse-Chorus-Verse-Bridge-Chorus
  Vocal: VOIDBOY's warm raspy tenor, medium autotune, whispered doubles

Song generated via Suno. Quality check: tempo 143 (±1.4%), energy 0.69 (±4%). PASS.

Cover art generated: dark purple, abstract figure, neon accents (VOIDBOY brand).

Distributed via LabelGrid → Spotify, Apple Music, TikTok, YouTube, +147 platforms.
Release date: Friday. ISRC assigned. Registered with ASCAP.

TikTok teaser posted Tuesday (15-sec chorus clip, #melodictrap #newmusic).
Instagram release post Friday. YouTube visualizer Saturday.

Day 7: 2,400 streams. Day 30: 18,000 streams. Revenue: $72.
Results fed back to model. VOIDBOY catalog: 13 songs, $340/month total.
```

---

## 3. Artist Portfolio Strategy

SoundPulse doesn't just create songs — it creates and manages a roster of AI artists. Each artist is a persistent persona with a genre niche, visual identity, social presence, and growing discography.

### Artist DNA vs Song DNA

**Artist DNA** (persistent — defines who the artist IS):

| Category | Fields |
|---|---|
| **Identity** | Stage name, legal name, age, gender, ethnicity, provenance, languages |
| **Voice** | Timbre, vocal range, delivery style, accent, autotune level, ad-libs, Suno persona ID |
| **Genre** | Primary genre, adjacent genres, influences, anti-influences |
| **Production** | Signature sonic elements (e.g., "always uses 808s, spacey reverb") |
| **Lyrics** | Recurring themes, vocabulary level, perspective, recurring motifs |
| **Visual** | Face description, fashion style, color palette (#hex), art direction, tattoos/piercings |
| **Persona** | Backstory, personality traits, social voice, posting style, controversy stance |
| **Fashion** | Clothing aesthetic, brands, accessories, seasonal style |
| **Looks** | Hair, build, distinctive features — consistent across all generated images |
| **Background** | Origin story, cultural references, formative experiences |
| **Relationship** | Status, how it affects their art/persona narrative |

**Song DNA** (varies per track — defined by the blueprint):

| Category | Fields |
|---|---|
| **Sonic** | Tempo, key, mode, energy, valence, danceability, acousticness |
| **Structure** | Section arrangement, chorus ratio, intro length |
| **Theme** | What THIS specific song is about |
| **Lyrics** | Actual lyric content (generated per song) |
| **Features** | Any one-off production choices specific to this track |

**Generation = Artist DNA + Song DNA merged into one prompt.**

### Artist Lifecycle

| Stage | Description | Actions |
|---|---|---|
| **Birth** | Genre opportunity detected, no suitable existing artist | Generate full persona, create social accounts, produce first 2-3 songs |
| **Growth** | First 5-10 songs, building audience | Aggressive TikTok marketing, playlist pitching, high release cadence |
| **Maturity** | 10+ songs, established audience | Consistent releases, cross-promote with label roster, explore sync |
| **Evolution** | Genre trends shift | Gradually evolve sound, or create "side project" persona |
| **Retirement** | Declining audience, genre saturated | Reduce releases, let catalog generate passive revenue |

### Artist Decision Model

For each new blueprint, decide: assign to existing artist or create new?

- Genre match > 80% AND brand coherence > 70% AND release cadence OK → **assign to existing**
- Otherwise → **create new artist**

### Two Prediction Models

| Model | Question | Inputs | Output |
|---|---|---|---|
| **Artist Success** | "Will this persona gain traction?" | Genre, aesthetic, persona type, market | 90-day follower growth, engagement probability |
| **Song Success** | "Will this track chart?" | Song DNA features | Streaming trajectory, breakout probability |
| **Combined** | "Should we make this?" | Both scores + genre timing | Green light / red light + expected ROI |

---

## 4. Phased Rollout

### Phase 1 — Data Foundation (Weeks 1–8) ✅ BUILT
- Chartmetric as primary backbone + Spotify/Shazam enrichment
- Chart data scraping every 4–6 hours
- Entity resolution, composite scoring, genre classification
- React dashboard, API playground, historical backfill
- Deployment: Railway + Neon

### Phase 2 — Prediction + Song DNA (Weeks 9–20) 🔄 IN PROGRESS
- LightGBM prediction model trained on historical data
- Spotify Audio Analysis enrichment (timbre, structure)
- Genius lyrics enrichment (themes, vocabulary)
- Chartmetric artist social stats (growth trajectories)
- Model Validation backtesting system
- AI Assistant (Groq/Llama)
- Song Lab (blueprint generation + prompt output)

### Phase 3 — Full Autonomous Pipeline (Weeks 21–40) 📋 SPECIFIED
- Suno API integration for song generation
- Artist creation system (persona, visuals, accounts)
- Revelator/LabelGrid distribution API
- TikTok/Instagram/YouTube marketing automation
- PRO registration via TuneRegistry
- Revenue tracking and reinvestment logic
- Cover art generation (DALL-E/Flux)

---

## 5. Success Metrics

### Phase 1
| Metric | Target |
|---|---|
| Data freshness | <6 hours stale |
| Entity match rate | >85% cross-platform |
| API uptime | >99% |

### Phase 2
| Metric | Target |
|---|---|
| 7-day breakout precision | >60% at 50% recall |
| Song DNA coverage | Audio features for >90% of top 200 tracks |
| Lyrics coverage | Themes for >70% of top 200 tracks |

### Phase 3
| Metric | Target |
|---|---|
| Songs generated per month | >50 across genre niches |
| Distribution success rate | >95% delivered to all DSPs |
| TikTok teaser engagement | >1% avg engagement rate |
| Autonomous uptime | Full pipeline runs 30+ days without intervention |
| First revenue | At least 1 song generating >$1/month |
| Break-even | Portfolio reaches $2K+/month within 6 months |

---

## 6. Unit Economics & Revenue Model

### Per-Song Economics

| Item | Cost |
|---|---|
| Song generation (Suno) | ~$0.10 |
| Cover art (DALL-E) | ~$0.05 |
| Distribution (Revelator/LabelGrid) | ~$0.50-2.00 |
| Marketing (social posts) | ~$0.00 (API costs included in infra) |
| **Total per song** | **~$0.60-2.15** |

### Revenue Per Stream

| Platform | Per-Stream Payout |
|---|---|
| Spotify | $0.003-0.005 |
| Apple Music | $0.007-0.01 |
| YouTube Music | $0.002-0.004 |
| TikTok | $0.002-0.003 |
| Average | ~$0.004 |

### Portfolio Revenue Projection

| Songs | Avg Streams/Song/Mo | Revenue/Mo | Costs/Mo | Net |
|---|---|---|---|---|
| 50 | 1,000 | $200 | $830 | -$630 |
| 200 | 3,000 | $2,400 | $1,400 | +$1,000 |
| 500 | 5,000 | $10,000 | $2,200 | +$7,800 |
| 1,000 | 10,000 | $40,000 | $4,000 | +$36,000 |
| 5,000 | 10,000 | $200,000 | $10,400 | +$189,600 |

**Break-even:** ~200 songs at 3K avg streams/month = ~4-6 months after Phase 3 launch.

### Reinvestment Logic

```
Monthly profit = revenue - costs
40% → new song generation
30% → marketing (TikTok ads, playlist pitching)
20% → infrastructure
10% → cash reserve
```

---

# Part II — Intelligence & Data

---

## 7. Data Collection Layer

**Status: BUILT AND RUNNING**

### Scrapers

| Scraper | Source | Frequency | Data | Status |
|---|---|---|---|---|
| `chartmetric` | Chartmetric Charts API | Every 4h | Spotify/Shazam charts (US), track metadata, genres | ✅ Running |
| `chartmetric_artists` | Chartmetric Artist Stats | Every 12h | Social metrics across 5 platforms + geographic audience | ✅ Running |
| `spotify` | Spotify Web API | Every 6h | Search-based trending across 12 genres | ✅ Running |
| `spotify_audio` | Spotify Audio Analysis | Daily | Tempo, energy, timbre, pitch, song structure | ✅ Running |
| `genius_lyrics` | Genius API + scraping | Daily | Lyrics, themes, vocabulary, structure | ✅ Ready |
| `kworb` | Kworb.net | Daily | Spotify streaming charts with counts | Available |
| `radio` | Billboard.com | Daily | Radio airplay, Hot 100, Country Airplay | Available |
| `musicbrainz` | MusicBrainz API | Every 12h | ISRC codes, genre tags, release metadata | Available |

### Data Strategy — Chartmetric as Backbone

Chartmetric ($350/month, 2 req/sec = ~170K req/day) is the primary data source. Covers Spotify, Apple Music, TikTok, YouTube, Shazam, Instagram, Twitter. Direct APIs (Spotify, Shazam, Genius) add depth Chartmetric doesn't provide.

### Entity Resolution

Chartmetric handles most cross-platform matching. For non-Chartmetric entities: ISRC → Platform ID → Fuzzy match (RapidFuzz >85%) → Manual disambiguation queue.

### Historical Backfill

Chartmetric data goes back to 2020+. Backfill script pulls 730 days of daily chart data. Run via `POST /api/v1/admin/backfill`.

---

## 8. Song DNA — The Complete Feature Set

### Sonic Features (Spotify Audio Analysis)

| Feature | Source |
|---|---|
| Tempo, time signature, beat regularity | Audio Analysis (beats, bars, tatums) |
| Energy, loudness contour, dynamic range | Audio Features + Analysis (segments) |
| Key, mode, valence, danceability | Audio Features |
| Acousticness, instrumentalness, speechiness | Audio Features |
| 12-dim timbre vectors (instrument texture) | Audio Analysis (segments.timbre) |
| Song structure (verse/chorus/bridge) | Audio Analysis (sections) + Genius |
| 12-dim pitch vectors (harmonic content) | Audio Analysis (segments.pitches) |

### Lyrical Features (Genius)

| Feature | What It Captures |
|---|---|
| Primary themes | Love, heartbreak, party, flex, introspection, social, nostalgia, empowerment |
| Vocabulary richness | Unique/total words — higher = literary, lower = catchy |
| Chorus repetition ratio | How formulaic the structure is |
| Section structure | Verse count, chorus count, bridge presence |
| Word density | Sparse (electronic) vs dense (rap) |

### Social & Cultural Context (Chartmetric)

| Feature | Source |
|---|---|
| Artist social growth velocity | `/stat/` endpoints across 5 platforms |
| Geographic audience | `/where-people-listen` |
| Playlist ecosystem | Playlist tracking |
| Cross-platform cascade timing | Platform-specific snapshot sequences |
| Collaboration network | Artist relationship data |

### Arrangement (Future — Deeper Analysis)

Vocal style, instrument palette, build patterns, hook placement, sonic similarity — via audio ML models and timbre clustering.

---

## 9. Genre Intelligence

- 850+ genres, hierarchical, 12 root categories
- Bidirectional mappings to Spotify, Apple Music, MusicBrainz, Chartmetric
- Genre opportunity score = trending velocity × inverse saturation
- Per-genre sonic profile (average features across trending tracks)
- Genre classifier auto-assigns tracks on ingest

---

## 10. Prediction Models

### Song Success Predictor

**Architecture:** LightGBM (Phase 2) → Ensemble (Phase 3: LightGBM + LSTM + XGBoost + Ridge meta-learner)

**~70 features:** per-platform momentum (35), cross-platform (10), temporal (8), genre (7), entity history (10), Song DNA (~10)

**Targets:** spotify_top_50_us (7d), shazam_top_200_us (7d), billboard_hot_100 (14d), cross_platform_breakout (14d)

**Training:** Daily 3am UTC. Temporal train/test split. Auto-retrain on accuracy drop >5%.

**Cold start:** Rule-based heuristic (<7 days), confidence-capped ensemble (7-14 days), full ensemble (14+ days).

### Artist Success Predictor (Phase 3)

Predicts 90-day follower growth for proposed personas. Trained on real artist profiles from Chartmetric.

### Platform Weighting

| Signal | Weight | Type |
|---|---|---|
| TikTok | 25% | Leading |
| Spotify | 25% | Concurrent |
| Shazam | 15% | Leading |
| Apple Music | 15% | Concurrent |
| Social velocity | 10% | Composite |
| Radio | 10% | Lagging |

Validated via Granger causality tests. Re-evaluated quarterly.

---

## 11. Blueprint Generation

**Endpoint:** `POST /api/v1/blueprint/generate`

1. Query 30-60 days of trending snapshots for the genre
2. Aggregate Song DNA across top performers
3. Compute sonic profile (avg tempo, dominant key, mean energy/valence)
4. Detect dominant lyrical themes
5. Translate to model-specific prompt (Suno/Udio/SOUNDRAW/MusicGen)

---

## 12. Model Validation & Backtesting

For each monthly evaluation period: predict using historical data, compare against actuals.

Metrics: MAE, RMSE, precision, recall, F1. Filterable by genre and entity type. Frontend page with charts.

---

# Part III — Creation & Production

---

## 13. Song Generation

### Pipeline

```
Blueprint + Artist DNA → Prompt Assembly → Suno/Udio API → Audio File → Quality Check → Pass/Fail
```

### Music Generation APIs

| Model | Input | Best For | Cost | API |
|---|---|---|---|---|
| **Suno** | Style text + lyrics + vocal gender + negative tags | Full songs with vocals | ~$0.10/song | Third-party wrappers |
| **Udio** | Prompt + lyrics + audio conditioning | Style transfer | Similar | Third-party wrappers |
| **SOUNDRAW** | Mood, genre, tempo, energy params | Batch instrumental | ~$0.02/song | Official REST API |
| **MusicGen** | Text prompt + melody reference | Self-hosted instrumental | Compute cost | Open source |

### Quality Assurance

After generation: compare audio features against blueprint (tempo ±10%, energy ±0.15). Check duration (90-300s), silence gaps. Max 3 regeneration attempts.

---

## 14. Lyrics Generation

Generate via Groq/Llama before sending to Suno:

```
Theme: {blueprint.primary_theme}
Mood: {blueprint.mood}
Vocabulary: {artist_dna.vocabulary_level}
Structure: {blueprint.section_structure}
Voice: {artist_dna.lyrical_voice}
Style: {artist_dna.influences}
```

---

## 15. Artist Creation & Management

### Creation Pipeline

Genre opportunity → Artist Success Predictor → Generate profile (demographics, voice, visual, persona, narrative) → Generate visual assets (portrait, photos, banners) → Create platform accounts → First 2-3 songs

### Comprehensive Artist Profile

**Demographics:** Stage name, legal name, age, gender, ethnicity, provenance, relationship status, languages

**Voice DNA:** Timbre, vocal range, delivery style, accent, autotune level, ad-libs, Suno persona ID

**Visual DNA:** Face (consistent features for image generation), fashion style, color palette, art direction, tattoos/piercings, reference image IDs

**Genre:** Primary + adjacent genres, influences, anti-influences, production signature

**Persona:** Backstory, personality traits, social voice, posting style, controversy stance, fan nickname, narrative arcs

**Lyrical:** Recurring themes, vocabulary level, perspective, recurring motifs

### Artist Decision Model

```python
For each blueprint:
  1. Score all existing artists: genre_match × coherence × momentum
  2. If best score > 0.6 AND cadence OK (>14 days since last release): assign
  3. Otherwise: create new artist
```

### Data Model

```sql
ai_artists: id, stage_name, legal_name, demographics (JSON), voice_dna (JSON),
            visual_dna (JSON), genre_home[], influences[], persona (JSON),
            social accounts, status, portfolio_role

ai_artist_releases: id, artist_id, track_title, song_dna (JSON),
                    generation_prompt, audio_url, cover_art_url,
                    distribution_status, isrc, upc, streams, revenue
```

---

## 16. Visual Identity & Image Generation

### Image Pipeline

```
Artist Visual DNA → Image Model → Consistent outputs:
  ├── Cover art (3000x3000, per-song mood + brand colors)
  ├── Profile photos (Spotify, Instagram, TikTok)
  ├── Banner images (YouTube, social headers)
  ├── Social content (promotional posts, stories)
  └── Video elements (lyric overlays, visualizers)
```

### Image Models

| Model | Strength | API | Consistency Method |
|---|---|---|---|
| **DALL-E 3** | Official API, good quality | OpenAI REST API | Detailed prompts |
| **Midjourney** | Best quality | Discord bot / unofficial | `--cref` character reference |
| **Stable Diffusion + IP-Adapter** | Self-hosted, best face consistency | ComfyUI | IP-Adapter face lock |
| **Flux** | Emerging, high quality | fal.ai / Replicate | Prompt engineering |

---

# Part IV — Distribution & Revenue

---

## 17. Distribution

### Distribution APIs

| Service | API | Pricing | Verdict |
|---|---|---|---|
| **Revelator** | Full REST, public docs | Custom SaaS | TOP PICK — distribution + rights + royalties |
| **LabelGrid** | Full REST, sandbox | $1,428/yr starter | BUDGET PICK — transparent, public docs |
| **limbo/ Music** | REST, JSON:API spec | Custom | Strong API, good docs |
| **VerseOne Pro** | REST, Swagger | Premium tier | Good for automation |

**Not suitable (no API):** DistroKid, Amuse, UnitedMasters, LANDR, RouteNote

### Distribution Pipeline

Song → Cover art → Metadata assembly (title, ISRC, UPC, genre, credits, release date) → Distribution API → 150+ DSPs → Delivery confirmation

### Release Timing

- Friday for Spotify algorithmic playlists
- TikTok teaser 3 days before
- Pre-save campaign 7 days before
- Avoid major artist release dates

---

## 18. Marketing & Social

### TikTok Pipeline

Song → Extract 15-sec hook → Generate video (lyric overlay / visualizer) → Post via TikTok Content Posting API → Monitor sound adoption → Boost if viral

### Social Content Calendar (Per Artist)

| Day | Platform | Content |
|---|---|---|
| Mon | Instagram | Mood photo |
| Tue | TikTok | Narrative clip |
| Wed | Instagram Story | Poll / interactive |
| Thu | TikTok | Teaser (if release coming) |
| Fri | All | Release announcement |
| Sat | YouTube | Lyric video / visualizer |
| Sun | Instagram | Fan engagement |

### Social APIs

TikTok Content Posting API, Instagram Graph API, YouTube Data API v3, X API v2

---

## 19. Rights, Royalties & Legal

### Registration Flow

Song distributed → Revelator (rights management) → TuneRegistry (ASCAP/BMI registration) → SoundExchange (digital performance) → YouTube Content ID

### AI Music & PROs

ASCAP/BMI accept AI-assisted works with "meaningful human creative contribution." Fully AI works NOT eligible. SoundPulse model: human selects genre, approves blueprint. Legal gray area — needs counsel.

### No PRO Has a Public API

Registration via TuneRegistry dashboard (automate with browser automation) or Songtrust. Revelator API handles rights management side.

---

## 20. Revenue & Analytics

### Revenue Tracking

```sql
revenue_events: id, release_id, artist_id, platform, territory,
                period_start, period_end, stream_count, revenue_cents,
                royalty_type, source
```

### Revenue Sources

Streaming royalties (Spotify, Apple, etc.), mechanical royalties (MLC), performance royalties (ASCAP/BMI), sync licensing, YouTube Content ID

---

# Part V — Platform & Infrastructure

---

## 21. AI Assistant

**Status: BUILT**

Groq/Llama 3.3 70B chat interface. Gathers DB context (trending, genres, stats, scrapers), answers questions in natural language.

Example: "If I wanted a Christian rock single, what should the artist and song look like?" → queries genre data, generates blueprint-style recommendation.

---

## 22. API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/trending` | Trending artists/tracks with composite scores |
| `GET` | `/search` | Full-text search across entities |
| `GET` | `/predictions` | Breakout predictions with confidence |
| `GET` | `/predictions/{id}` | Live prediction for single entity |
| `GET` | `/genres` | Genre taxonomy (tree or flat) |
| `GET` | `/genres/{id}` | Single genre detail |
| `POST` | `/blueprint/generate` | Generate Song DNA blueprint + prompt |
| `GET` | `/blueprint/genres` | Genre opportunity rankings |
| `POST` | `/assistant/chat` | AI assistant (Groq/Llama) |
| `GET` | `/backtesting/results` | Model validation timeline |
| `POST` | `/backtesting/run` | Trigger backtest evaluation |
| `GET` | `/backtesting/genres` | Per-genre accuracy breakdown |
| `GET` | `/admin/scraper-config` | Scraper status and scheduling |
| `GET` | `/admin/model-config` | Model hyperparameters |
| `POST` | `/admin/backfill` | Trigger historical data backfill |
| `GET` | `/health` | Service health check |

Auth: `X-API-Key` header. Tiers: Free (100 req/hr), Pro (1K), Admin (unlimited).

---

## 23. Database Schema

### Current Tables (BUILT)

| Table | Purpose |
|---|---|
| `artists` | Artist entities with platform IDs, genres |
| `tracks` | Track entities with audio features, platform IDs |
| `trending_snapshots` | Daily data per entity per platform |
| `predictions` | Stored predictions with outcomes |
| `backtest_results` | Model validation per period |
| `genres` | 850+ genre taxonomy |
| `scraper_configs` | Scraper scheduling |
| `api_keys` | Authentication |
| `feedback` | Prediction feedback |

### Phase 3 Tables (TO BUILD)

| Table | Purpose |
|---|---|
| `ai_artists` | Full AI artist profiles (persona, voice, visual, social) |
| `ai_artist_releases` | Songs with generation details, distribution status, revenue |
| `revenue_events` | Royalty tracking per song per platform |
| `social_posts` | Scheduled/posted social content |
| `generation_logs` | Generation attempts and quality scores |

---

## 24. Deployment Architecture

### Current (RUNNING)

| Service | Platform | Role |
|---|---|---|
| API (FastAPI) | Railway | Serves all endpoints |
| UI (React) | Railway | Dashboard, Song Lab, Assistant |
| Celery Worker | Railway | Processes scraper + training tasks |
| Celery Beat | Railway | Cron scheduler |
| Redis | Railway | Message broker + cache |
| PostgreSQL | Neon (serverless) | Persistent storage |
| GitHub | Auto-deploy | Push to `main` → deploy |

### Phase 3 Additions

GPU compute (MusicGen), Object storage (S3 for audio/images), CDN

---

## 25. Cron Schedule

| Task | Schedule | What It Does |
|---|---|---|
| Chartmetric charts | Every 4h | Trending chart data |
| Chartmetric artist stats | Every 12h | Social metrics per artist |
| Spotify search | Every 6h | Search-based trending |
| Spotify audio analysis | Daily | Deep audio features |
| Genius lyrics | Daily | Lyrics + themes |
| Model training | Daily 3am UTC | Retrain prediction model |
| Predictions | Every 6h | Predict for top 50 entities |
| Backtesting | Daily 4:30am UTC | Evaluate model accuracy |
| **Phase 3:** | | |
| Song generation | Daily 6am UTC | Generate from top blueprints |
| Distribution | Daily 9am UTC | Submit ready songs |
| Social posting | Per artist schedule | Marketing content |
| Revenue collection | Weekly | Pull royalty reports |
| Portfolio review | Weekly | Artist performance evaluation |

---

## 26. Operating Costs

| Phase | Infra | APIs | Generation | Distribution | Total |
|---|---|---|---|---|---|
| Phase 1 (now) | $70 | $360 | — | — | **$430** |
| Phase 2 | $170 | $400 | — | — | **$570** |
| Phase 3 (50 songs/mo) | $300 | $400 | $30 | $100 | **$830** |
| Phase 3 (500 songs/mo) | $500 | $400 | $300 | $1,000 | **$2,200** |
| Phase 3 (5K songs/mo) | $2,000 | $400 | $3,000 | $5,000 | **$10,400** |

---

## 27. External API Dependencies

| API | Purpose | Cost | Status |
|---|---|---|---|
| Chartmetric | Primary data backbone | $350/mo | ✅ Active |
| Spotify Web API | Charts, search, audio | Free | ✅ Active |
| Spotify Audio Analysis | Deep audio features | Free | ✅ Active |
| Shazam (RapidAPI) | Discovery signals | $10-50/mo | ✅ Active |
| Genius | Lyrics + themes | Free | ✅ Ready |
| Groq | AI Assistant (Llama) | Free | ✅ Active |
| MusicBrainz | Metadata enrichment | Free | Available |
| **Phase 3:** | | | |
| Suno (wrapper) | Song generation | ~$50-100/mo | Planned |
| SOUNDRAW | Batch instrumental | ~$20-50/mo | Planned |
| Revelator/LabelGrid | Distribution | ~$120-760/mo | Planned |
| DALL-E / Flux | Cover art + images | ~$10-30/mo | Planned |
| TikTok Content API | Social posting | Free | Planned |
| Instagram Graph API | Social posting | Free | Planned |
| YouTube Data API | Video upload | Free | Planned |
| TuneRegistry | PRO registration | ~$20-50/mo | Planned |

---

*SoundPulse: software eating the music industry, one generated hit at a time.*
