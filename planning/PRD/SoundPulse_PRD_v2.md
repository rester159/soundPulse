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

### Phase 1 — Data Foundation (Weeks 1–8) 🔄 90% COMPLETE
**Built:** Chartmetric scraper, Spotify scraper, entity resolution, composite scoring, 959-genre taxonomy, React dashboard (6 pages), API (16 endpoints), Railway deployment (5 services), Neon database, historical backfill scripts, Docker local dev.

**Remaining:** Production data pipeline stability (ingest endpoint timeout on Neon needs optimization), continuous daily data accumulation (backfill running, need 60+ days of daily snapshots for model training), genre classifier producing empty results on most tracks (Chartmetric data has genre strings in signals but classifier expects structured platform genre arrays).

**Data velocity is faster than expected:** Chartmetric paid tier at 2 req/sec (170K/day) means we can backfill 2 years of data in hours, not weeks. 9,031 snapshots across 40 dates already in production.

### Phase 2 — Prediction + Song DNA (Weeks 9–20) 🔄 40% COMPLETE
**Built:** Spotify Audio Analysis scraper, Genius lyrics scraper, Chartmetric artist social stats scraper, Model Validation/backtesting system, AI Assistant (Groq/Llama), Song Lab (blueprint generation), automated training cron (daily 3am), model config system.

**Remaining:** LightGBM model actually producing useful predictions (needs stable daily data), backtesting showing meaningful accuracy metrics, Song Lab showing genre data (blocked by genre classification), audio features populated for top tracks, lyrics themes populated.

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

### Per-Song Economics (Researched April 2026)

| Item | Cost | Source |
|---|---|---|
| Song generation (Suno Premier direct) | ~$0.015/song (10K credits/mo = ~2K songs at $30/mo) | suno.com/pricing |
| Song generation (via API wrapper — EvoLink) | ~$0.11/song | evolink.ai |
| Song generation (via API wrapper — CometAPI) | ~$0.14/song | cometapi.com |
| Cover art (DALL-E 3) | ~$0.04/image | OpenAI API pricing |
| Distribution (LabelGrid) | ~$0.12/song ($1,428/yr ÷ 1000 songs) | labelgrid.com |
| Promotion (Playlist Push campaign) | ~$300/campaign (yields 6-8K streams) | playlistpush.com |
| **Total per song (generation + distribution only)** | **~$0.17-0.30** |
| **Total per song (with $300 promo campaign)** | **~$300.30** |

**Key insight:** Song generation is nearly free ($0.015-0.14/song). The real cost is PROMOTION — getting anyone to listen. A $300 Playlist Push campaign per song is the dominant cost.

**Suno commercial rights caveat:** Post Warner Music deal (late 2025), Suno grants a perpetual commercial license but retains technical authorship. US Copyright Office does not recognize raw AI-generated audio as copyrightable. This is an evolving legal area.

### Revenue Per Stream

| Platform | Per-Stream Payout |
|---|---|
| Spotify | $0.003-0.005 |
| Apple Music | $0.007-0.01 |
| YouTube Music | $0.002-0.004 |
| TikTok | $0.002-0.003 |
| Average | ~$0.004 |

### Portfolio Revenue Projection (Recalibrated)

**Reality check:** The average independent release gets ~200 total streams. Getting to 3K streams/month requires active promotion (~$300-500 per song in the first month). After the initial push, songs that get algorithmic traction can sustain streams organically. Songs that don't get traction generate near-zero ongoing revenue.

**Conservative model (20% of songs get traction, 80% don't):**

| Catalog Size | Songs Getting Traction | Avg Streams/Mo (Traction) | Revenue/Mo | Infra/Mo | Promo Spend | Net |
|---|---|---|---|---|---|---|
| 50 | 10 | 3,000 | $120 | $830 | $15,000 initial | -$710/mo |
| 200 | 40 | 5,000 | $800 | $1,400 | $60,000 cumulative | -$600/mo |
| 500 | 100 | 8,000 | $3,200 | $2,200 | $150,000 cumulative | +$1,000/mo |
| 1,000 | 200 | 10,000 | $8,000 | $4,000 | $300,000 cumulative | +$4,000/mo |

**Key assumptions:**
- 20% hit rate (songs that get algorithmic traction after initial promo push)
- Songs with traction grow streams organically month-over-month
- Songs without traction cost the promo spend but generate near-zero ongoing revenue
- Initial promo budget: ~$300/song for Playlist Push + Meta ads
- Infrastructure costs scale with catalog size

**Break-even:** ~500 songs in catalog with 100 getting traction at 8K avg streams = ~12-18 months of cumulative investment.

**How to improve the hit rate:** The entire prediction model exists to push this from 20% toward 40%+. Better genre targeting + better blueprints + better timing = higher traction rate = faster break-even.

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

### Chartmetric Import Scope (current — 2026-04-11)

**The scraper (`scrapers/chartmetric.py`) queries exactly these 6 chart endpoints, all US-only:**

| # | Source | Chart type | Endpoint | Typical size |
|---|---|---|---|---|
| 1 | spotify | regional | `/api/charts/spotify?type=regional&country_code=us` | ~200 tracks |
| 2 | spotify | viral | `/api/charts/spotify?type=viral&country_code=us` | ~50 tracks |
| 3 | spotify | plays | `/api/charts/spotify?type=plays&country_code=us` | ~200 tracks |
| 4 | shazam | top | `/api/charts/shazam?country_code=us` | ~200 tracks |
| 5 | apple_music | top | `/api/charts/applemusic/tracks?type=top&country_code=us` | ~100–200 tracks |
| 6 | tiktok | viral | `/api/charts/tiktok/tracks?country_code=us` | ~100–200 tracks |

**Backfill scripts (`backfill_chartmetric.py`, `backfill_deep.py`) only run the first 4** — no Apple Music or TikTok historical pulls.

**Addressable daily volume:** ~600–1,200 chart entries → **~300–600 unique tracks/day** after cross-chart dedup.

**Rate budget consumption:** Daily scraper uses ~24 API calls/day. Backfill uses 4 calls × N days. **Current consumption is <2% of the 170K/day rate budget** — there is enormous headroom to expand scope.

**Definition (canonical):** SoundPulse's data corpus is "the top performers of the US Spotify, Shazam, Apple Music, and TikTok charts on each given day, plus their cross-chart overlap." It is **not** "all songs on streaming." The long tail is intentionally excluded at the source.

### Coverage Expansion Plan (Phase 1.E)

The current scope is the bottleneck for ML training quality and for genre breadth. Expansion priorities, in order:

1. **Multi-country**: add GB, DE, JP, BR, MX, FR, KR, IN to the country list → 8 countries × 6 charts ≈ 9,600 entries/day → ~2K unique tracks/day. **~50× current volume.** Costs ~192 API calls/day (still <0.2% of budget).
2. **Genre-specific charts**: query Chartmetric's per-genre Spotify charts (if available on the tier) for the top of each of the 906 genres. Long-tail discovery — fills the gap between "top 200 mainstream" and our 906-genre taxonomy.
3. **Billboard verticals**: add Billboard Hot 100, country, R&B, dance, rock charts via Chartmetric.
4. **Chart depth**: if Chartmetric supports top-1000 instead of top-200 (`limit` param), use it on the regional charts.
5. **Backfill**: re-run `backfill_deep.py` against the expanded scope after AUD-002 (sync classifier in async ingest) is fixed — without that fix, large-scale backfill will time out on Neon.

**Order of execution is mandatory**: fix ingest perf (AUD-002, P1-022/023) BEFORE expanding scope, otherwise backfill collapses. See `tasks.md` P1.E.

### 7.2. Chartmetric Deep US Coverage — MECE Definition

**Goal:** exhaust the Chartmetric paid-tier API for **US-only** data so the SoundPulse corpus contains every track that is currently or historically charting on any US-tracked platform. The MECE space below defines exactly what is in scope and what is not. Implementation lives in `scrapers/chartmetric_deep_us.py` (the deep scraper) and `scripts/backfill_chartmetric_deep_us.py` (the backfill runner). A discovery probe lives in `scripts/chartmetric_probe.py`.

**Source of truth:** the official Chartmetric apidoc (`api.chartmetric.com/apidoc`) cross-referenced against the `musicfox/pycmc` Python client and the Mixture Labs `chartmetric-cli` reference (which mirrors every documented endpoint 1-to-1). The endpoint matrix below is what those sources confirm — speculation has been removed.

**Critical corrections vs the v1 of this section** (recorded for posterity):
- **Spotify `type=plays` is NOT a valid value.** `/charts/spotify` only accepts `regional` or `viral`. The existing `scrapers/chartmetric.py` has been silently failing on `plays` for months — flagged in `tasks.md` as a follow-up cleanup.
- **Billboard charts are NOT exposed via Chartmetric API.** Confirmed by absence from the entire `cm charts` CLI subcommand list. If you want Billboard, use a separate scraper.
- **City-level Spotify top-tracks does NOT exist.** Spotify itself does not publish per-city top-200. The only per-city Spotify signal is `/artist/{id}/where-people-listen` (per-artist listener counts by city).
- **Charts have NO `limit` param** — chart depth is fixed by the upstream provider (200 for Spotify, Apple Music, Shazam, iTunes, Amazon; 100 for YouTube, Deezer). To go deeper, use `offset` pagination. List endpoints (`/artist/list`, `/track/list`) DO accept `limit` (max 100/page) and paginate exhaustively via `offset`.
- **Amazon uses `code2`, not `country_code`,** for the country param.
- **Several charts are weekday-restricted:** YouTube + Spotify Fresh Find = Thursday only; SoundCloud + Beatport = Friday only. Calling them on the wrong weekday returns 404.

#### The MECE space

The atomic unit of a "pull" is one tuple:

```
(source_platform, chart_type, country, genre_filter, snapshot_date)
```

Every cell in the cross-product is either fetched once, or explicitly skipped (not in tier / not supported / wrong weekday). No cell is ever fetched twice for the same tuple. Below is the cross-product, decomposed by axis.

##### Axis 1 — Track charts (verified against official apidoc)

| source_platform | chart_type | endpoint | weekday | params | notes |
|---|---|---|---|---|---|
| spotify | regional_daily | `/api/charts/spotify` | — | `type=regional&interval=daily` | top 200 |
| spotify | viral_daily | `/api/charts/spotify` | — | `type=viral&interval=daily` | top 200 |
| spotify | regional_weekly | `/api/charts/spotify` | — | `type=regional&interval=weekly` | top 200 |
| spotify | viral_weekly | `/api/charts/spotify` | — | `type=viral&interval=weekly` | top 200 |
| spotify | freshfind | `/api/charts/spotify/freshfind` | thursday | — | editorial new music |
| apple_music | tracks_top × 24 genres | `/api/charts/applemusic/tracks` | — | `insight=top&genre={g}` | 24 Apple genre strings |
| apple_music | tracks_daily × 24 genres | `/api/charts/applemusic/tracks` | — | `insight=daily&genre={g}` | playlist-based |
| apple_music | albums × 24 genres | `/api/charts/applemusic/albums` | — | `genre={g}` | speculative — probe |
| apple_music | videos | `/api/charts/applemusic/videos` | — | — | speculative |
| itunes | tracks × 24 genres | `/api/charts/itunes/tracks` | — | `genre={g}` | purchases signal |
| itunes | albums × 24 genres | `/api/charts/itunes/albums` | — | `genre={g}` | |
| itunes | videos | `/api/charts/itunes/videos` | — | — | |
| amazon | tracks_popular × 24 genres | `/api/charts/amazon/tracks` | — | `insight=popular_track&genre={g}&code2=US` | |
| amazon | tracks_new × 24 genres | `/api/charts/amazon/tracks` | — | `insight=new_track&genre={g}&code2=US` | |
| amazon | albums_popular × 24 genres | `/api/charts/amazon/albums` | — | `insight=popular_album&genre={g}&code2=US` | |
| amazon | albums_new × 24 genres | `/api/charts/amazon/albums` | — | `insight=new_album&genre={g}&code2=US` | |
| shazam | top_us | `/api/charts/shazam` | — | — | top 200 |
| shazam | top_us × 4 genres | `/api/charts/shazam` | — | `genre={g}` | alternative/rock/house/pop |
| tiktok | tracks_weekly | `/api/charts/tiktok` | — | `type=tracks&interval=weekly` | canonical form |
| tiktok | tracks_daily | `/api/charts/tiktok` | — | `type=tracks&interval=daily` | |
| tiktok | videos_weekly | `/api/charts/tiktok` | — | `type=videos&interval=weekly` | |
| tiktok | top_tracks | `/api/charts/tiktok/top-tracks` | — | `limit=200` | separate chart |
| youtube | tracks | `/api/charts/youtube/tracks` | thursday | — | weekly |
| youtube | videos | `/api/charts/youtube/videos` | thursday | — | weekly |
| youtube | trends | `/api/charts/youtube/trends` | thursday | — | weekly |
| soundcloud | top × 10 genres | `/api/charts/soundcloud` | friday | `kind=top&genre={g}` | weekly |
| soundcloud | trending × 10 genres | `/api/charts/soundcloud` | friday | `kind=trending&genre={g}` | weekly |
| deezer | top | `/api/charts/deezer/` | — | — | weak US signal |
| beatport | top × 14 genres | `/api/charts/beatport` | friday | `genre={g}` | electronic, no country param |

##### Axis 2 — Artist charts (verified against official apidoc)

| source_platform | chart_type | endpoint | params | notes |
|---|---|---|---|---|
| spotify | artists_monthly_listeners | `/api/charts/spotify/artists` | `type=monthly_listeners&interval=daily` | **biggest single missed signal** |
| spotify | artists_popularity | `/api/charts/spotify/artists` | `type=popularity&interval=daily` | |
| spotify | artists_followers | `/api/charts/spotify/artists` | `type=followers&interval=daily` | |
| spotify | artists_playlist_count | `/api/charts/spotify/artists` | `type=playlist_count&interval=daily` | |
| spotify | artists_playlist_reach | `/api/charts/spotify/artists` | `type=playlist_reach&interval=daily` | |
| youtube | artists | `/api/charts/youtube/artists` | thursday | |
| tiktok | users_likes | `/api/charts/tiktok` | `type=users&user_chart_type=likes&interval=weekly` | |
| tiktok | users_followers | `/api/charts/tiktok` | `type=users&user_chart_type=followers&interval=weekly` | |
| twitch | followers_daily | `/api/charts/twitch` | `type=followers&duration=daily&limit=200` | speculative |
| twitch | viewer_hours_daily | `/api/charts/twitch` | `type=viewer_hours&duration=daily&limit=200` | speculative |
| radio | airplay × 5 metric types | `/api/charts/airplay` | `type={mt}&duration=daily&limit=500` | mt ∈ {monthly_listeners, popularity, followers, playlist_count, playlist_reach}. **Sometimes a paid add-on tier — probe to confirm.** |

##### Axis 3 — Per-city US data (separate execution lane)

Chartmetric exposes city data through a first-class `/api/city/...` resource. The seed call is `/api/cities?country_code=US`, which returns the numeric city IDs to use elsewhere.

| Endpoint | Purpose | Notes |
|---|---|---|
| `GET /api/cities?country_code=US` | Seed call — list every US city Chartmetric tracks with its numeric `id` | Run once, persist the table |
| `GET /api/charts/applemusic/tracks?city_id={id}` | Per-city Apple Music top tracks | Only Apple supports this directly at chart level |
| `GET /api/charts/shazam?city={city_name}` | Per-city Shazam top tracks | Uses city NAME (string), not numeric ID |
| `GET /api/city/{city_id}/tracks?platform={p}` | Top tracks for a city | platforms: youtube, radio, shazam |
| `GET /api/city/{city_id}/artists?platform={p}` | Top artists for a city | platforms: spotify, youtube, shazam, radio, instagram |

**City charts are gated on probe-discovered city IDs and added to ENDPOINT_MATRIX in a follow-up task once the probe seeds them.** They're documented here as part of the MECE space but not yet executed in v1.

##### Axis 4 — Snapshot date

| Mode | Range | Cadence |
|---|---|---|
| Live refresh | yesterday | every 4 hours via the existing `chartmetric` scheduled job |
| Deep refresh | yesterday only | once per day, full ENDPOINT_MATRIX |
| Historical backfill | configurable, default last 730 days | one-shot via `scripts/backfill_chartmetric_deep_us.py` |

##### Axis 5 — Depth

Chart depth is **fixed by the upstream provider** (200 for Spotify/Apple/Shazam/iTunes/Amazon; 100 for YouTube/Deezer). Charts do NOT accept a `limit` param — pagination is via `offset`. Exception: `/charts/airplay`, `/charts/twitch`, and `/charts/tiktok/top-tracks` accept `limit` and we pass it. For exhaustive long-tail crawls, use the **list endpoints** (`/api/artist/list`, `/api/track/list`, `/api/playlist/{p}/lists`) which paginate at 100/page with no upper bound on offset.

##### Axis 6 — Artist & track enrichment (separate execution lane)

For every unique entity that appears in any chart, we additionally pull (in a follow-up enrichment task):

| Enrichment | Endpoint | Cadence |
|---|---|---|
| Artist metadata | `/api/artist/{id}` | once per artist |
| Artist platform stats | `/api/artist/{id}/stat/{platform}` for {spotify, instagram, tiktok, youtube, twitter, shazam} | weekly |
| Where people listen (Spotify cities) | `/api/artist/{id}/where-people-listen` | weekly |
| Audience demographics (Instagram/TikTok/YouTube) | `/api/artist/{id}/{platform}-audience` | weekly — **may be a paid add-on** |
| Career stage | `/api/artist/{id}/career` | weekly |
| Related artists | `/api/artist/{id}/relatedartists` | once |
| Track metadata | `/api/track/{id}` | once per track |
| Track playlist memberships | `/api/track/{id}/{platform}/{status}/playlists` | weekly |

This is a separate execution lane from the chart pulls — distinct rate budget, distinct schedule. Built in a follow-up task after the chart corpus is solid.

##### Axis 7 — Long-tail crawls (the `/list` endpoints)

For exhaustive coverage beyond what's surfaced by any chart, use:

| Endpoint | Filter for US | Notes |
|---|---|---|
| `/api/artist/list?code2=US&sortColumn=sp_monthly_listeners&limit=100` | yes | Exhaustive US artist enumeration, paginate by `offset` |
| `/api/track/list?code2=US&sortColumn=...&limit=100` | yes | Exhaustive track enumeration |
| `/api/playlist/{spotify}/lists?code2=US&tags={genre_id}&limit=100` | yes | Per-genre US playlist enumeration |

#### Budget math

Chartmetric paid tier: **2 req/sec → 172,800 req/day** at the entry-level Developer plan.

The current `ENDPOINT_MATRIX` in `scrapers/chartmetric_deep_us.py` resolves to **~250 fetches per snapshot date** when fully expanded (per-genre fan-out across Apple/iTunes/Amazon/SoundCloud/Beatport adds the bulk):

| Endpoint group | Calls per date |
|---|---|
| Spotify tracks (regional + viral, daily + weekly) | 4 |
| Spotify artists (5 type variants) | 5 |
| Spotify Fresh Find (Thursday) | 1 |
| Apple Music tracks (top + daily, 24 genres each) | 48 |
| Apple Music albums (24 genres) | 24 |
| iTunes (tracks + albums, 24 genres each) | 48 |
| Amazon (tracks popular/new + albums popular/new, 24 genres each) | 96 |
| Shazam (top + 4 per-genre) | 5 |
| TikTok (4 chart variants + top-tracks) | 5 |
| YouTube (3 weekly variants) | 3 |
| SoundCloud (top + trending, 10 genres each, Friday) | 20 |
| Deezer | 1 |
| Beatport (14 genres, Friday) | 14 |
| Twitch (2 type variants) | 2 |
| Airplay (5 metric type variants) | 5 |
| **Total per date** | **~281** |

| Workload | Calls | % of daily budget |
|---|---|---|
| Daily live cadence (existing 4h scraper, 6 endpoints × 4 ticks) | ~24 | 0.01% |
| Deep refresh (full matrix once per day, yesterday only) | ~281 | 0.16% |
| 730-day historical backfill (one-shot) | ~205,000 | runs in ~31 hours at 1.8 req/sec — split into 4–5 day chunks |
| Artist enrichment (5,000 artists weekly × 6 platforms × per-day amortized) | ~4,300/day | 2.5% |
| Track enrichment (50,000 tracks lifetime, amortized per-day) | ~7,000/day | 4% |

**Steady-state daily consumption (after backfill completes): ~12,000 calls = 7% of budget.** Plenty of headroom for cadence increases, more cities, playlist crawls.

**Backfill chunking:** because the full 730-day backfill takes ~31 hours, run it in 90-day chunks (`--start ... --end ...`) so it can be paused/resumed and so a network blip doesn't lose 12+ hours of progress.

#### MECE invariants (the contract)

1. **No tuple is fetched twice in the same scraper run** — the `ENDPOINT_MATRIX × dates` iteration is a flat loop, not nested with overlap.
2. **Every cell either resolves to "fetched" or "skipped with reason"** — speculative endpoints log `TIER` / `NOT_FOUND` / `ERROR` and continue. Nothing is silently dropped.
3. **Bulk ingest is atomic per batch** — `POST /api/v1/trending/bulk` either ingests all 500 records or fails the batch. No partial state.
4. **Genre classification and composite scoring are deferred** — the bulk path tags entities `needs_classification: true` in `metadata_json` and a background sweep handles them. This is what makes massive ingest possible.
5. **The same source is never double-counted** — `signals.source_platform` records the upstream platform; `platform="chartmetric"` is fixed because Chartmetric is the data fetcher. Cross-platform composite scoring happens later via the scoring config.

#### Execution order

1. `python scripts/chartmetric_probe.py` — runs ONE call against every endpoint in the matrix to verify tier access, plus discovers US city IDs via `/api/cities?country_code=US`, plus probes the artist demographic endpoints (which are sometimes a paid add-on). Outputs a per-endpoint pass/fail table and any speculative endpoints to promote.
2. Edit `scrapers/chartmetric_deep_us.py` based on probe output: promote any speculative endpoints that returned OK to `confirmed=True`.
3. `python scripts/backfill_chartmetric_deep_us.py --confirmed-only --days 90` — first chunk of historical pull (~5 hours). Verify it landed in the DB via the DB Stats view (P2.I) before moving on.
4. `python scripts/backfill_chartmetric_deep_us.py --days 90 --start 2026-01-12 --end 2026-04-11` — confirmed + any newly-promoted endpoints, same window.
5. Continue chunking backwards by 90 days until you have 730 days of history (~5 chunks × ~5 hours each = ~25 hours of pulling, runnable as a sequence of background jobs).
6. Wire the deep refresh into the daily scheduler (separate task — see `tasks.md` P1.E.2 P1-059).
7. Build the per-city ENDPOINT_MATRIX additions using the discovered city IDs (separate task — P1-065).
8. Build the artist + track enrichment lane (separate task — P1-063, P1-064).

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

### Cross-Platform Cascade Timing

When a song goes viral, signals cascade across platforms in a predictable sequence. Understanding this timing informs the marketing strategy.

**Typical cascade (learned from historical data):**
1. **TikTok** (Day 0): Sound starts getting used in videos
2. **Shazam** (Day 3-7): People hear it and want to identify it
3. **Spotify** (Day 7-14): Streams spike as Shazam users find the track
4. **Apple Music** (Day 10-18): Secondary streaming platform pickup
5. **Radio** (Day 20-40): Mainstream validation (lagging indicator)

**How we use this:**
- If a song gets TikTok traction (sound adoption rate >2x baseline), immediately increase Spotify playlist pitching (the spike is coming in 7-14 days)
- Shazam-to-Spotify ratio >3:1 = strong leading indicator, worth doubling marketing spend
- If a song reaches Spotify without TikTok precursor, it's organic/playlist-driven — different growth pattern

**This is not a separate model** — it's a set of rules derived from the trending snapshot time-series data, encoded in the marketing automation logic.

### Arrangement (Future — Deeper Analysis)

Vocal style, instrument palette, build patterns, hook placement, sonic similarity — via audio ML models and timbre clustering.

---

## 9. Genre Intelligence

- 959 genres, hierarchical, 12 root categories
- Bidirectional mappings to Spotify, Apple Music, MusicBrainz, Chartmetric
- Genre classifier auto-assigns tracks on ingest

### Genre Opportunity Score — Exact Formula

**Source:** `GET /api/v1/blueprint/genres` (Song Lab left panel)

**How it's computed (on the fly, no precomputation):**

1. Pull all track snapshots from the last 60 days, anchored to `MAX(snapshot_date)` in the DB (not `date.today()` — ensures historical backfill data always appears)
2. Extract genre strings from `signals_json->>'genres'` (e.g. `"pop, indie pop, chill pop"`) — this is a raw Chartmetric field, NOT the `tracks.genres` array column
3. Split by comma, normalize to lowercase, aggregate per tag:
   - `total_composite_score` and `total_velocity` across all snapshots for that tag
   - `track_count` = distinct entity IDs in this genre
4. Compute:

```
momentum  = max(0, avg_velocity) / 10          # normalized 0-1
quality   = avg_composite_score / 100           # normalized 0-1
saturation = min(1.0, track_count / 50)         # >50 tracks = fully saturated

opportunity_score = 0.4 × momentum + 0.4 × quality + 0.2 × (1 - saturation)
```

**Interpretation:**
- High score = genre has rising velocity + high-scoring tracks + not yet crowded
- A genre with 3 exceptional tracks beats a genre with 200 mediocre ones
- Minimum 2 distinct tracks required to appear in results

**Momentum label:** `rising` if avg_velocity > 0.5, `declining` if < -0.5, else `stable`

### Genre Data Caveat (Current)

Genre data lives in `signals_json` (raw Chartmetric strings like `"pop, chill pop"`) not in the `tracks.genres` column (a structured array). The genre classifier is supposed to parse these and populate `tracks.genres`, but currently only 102/2,146 tracks have the structured genres array populated. The Song Lab and opportunity scoring work correctly from `signals_json` directly.

---

## 10. Prediction Models

### Song Success Predictor

**Architecture:** LightGBM (Phase 2) → Ensemble (Phase 3: LightGBM + LSTM + XGBoost + Ridge meta-learner)

**~70 features:** per-platform momentum (35), cross-platform (10), temporal (8), genre (7), entity history (10), Song DNA (~10)

**Targets:** spotify_top_50_us (7d), shazam_top_200_us (7d), billboard_hot_100 (14d), cross_platform_breakout (14d)

**Training:** Daily 3am UTC. Temporal train/test split. Auto-retrain on accuracy drop >5%.

**Cold start:** Rule-based heuristic (<7 days), confidence-capped ensemble (7-14 days), full ensemble (14+ days).

### Artist Success Predictor (Phase 3)

Predicts 90-day follower growth for proposed artist personas.

**How it works:**
1. Chartmetric identifies which real artists are succeeding right now (charting, growing followers, viral moments)
2. The model extracts the characteristics of 1+ successful artists — not just music, but their full profile: demographic patterns, visual aesthetic, social behavior, genre positioning, release cadence
3. For a new AI artist, the model blends characteristics from multiple successful reference artists (e.g., "the genre positioning of Artist A + the visual aesthetic of Artist B + the social voice of Artist C")
4. The blended profile becomes the AI artist's DNA

**Training data:** Chartmetric artist stats (followers, growth rates, geographic audience) correlated with artist metadata (genre, platform presence, release patterns). The model learns which combinations of traits predict growth.

**Features:**
- Genre niche (how crowded, how fast-growing)
- Platform mix (TikTok-native vs Spotify-native vs cross-platform)
- Release cadence of successful artists in this niche
- Audience demographics (age, geography) from Chartmetric
- Social engagement patterns (post frequency, content type)
- Collaboration patterns (solo vs features)

**NOT in the training data:** Visual aesthetics, backstory, personality. These are creative choices informed by the genre research but not directly predictable by the model. The model says "this genre niche is growing" — the creative system decides what the artist looks and sounds like.

### Platform Weighting

Weights differ based on the success type we're predicting. An artist who goes viral on TikTok needs different signals than one who charts on Billboard.

**Current implementation weights** (based on available data — Chartmetric-heavy because it's our primary source):

| Signal | Weight | Rationale |
|---|---|---|
| Chartmetric (cross-platform) | 40% | Primary data backbone, most complete coverage |
| Spotify direct | 30% | Highest-fidelity chart data, audio features |
| Shazam | 20% | Best leading indicator (discovery intent) |
| Other (kworb, radio) | 10% | Supplementary validation |

**Target Phase 3 weights — by prediction type:**

| Signal | Chart Success | Viral/Social Success | Blend (Default) |
|---|---|---|---|
| TikTok metrics | 15% | **35%** | 25% |
| Spotify metrics | **30%** | 15% | 25% |
| Shazam metrics | **20%** | 10% | 15% |
| Apple Music | 15% | 5% | 10% |
| Social velocity | 5% | **25%** | 15% |
| Radio | **15%** | 0% | 10% |

**Why different weights per success type:**
- **Chart success** favors Spotify rank velocity, Shazam-to-Spotify ratio, and radio validation — these are the signals that precede and confirm chart entry
- **Viral/social success** favors TikTok sound adoption rate, cross-platform social velocity, and creator engagement — chart position is irrelevant for viral moments
- **Blend** is the default, balanced across both

The Artist Decision Model uses the prediction type matching the artist's niche: a TikTok-native artist uses viral weights, a radio-friendly artist uses chart weights.

Validated via Granger causality tests after 8 weeks of data. Re-evaluated quarterly.

---

## 11. Blueprint Generation

**Endpoint:** `POST /api/v1/blueprint/generate`
**UI:** Song Lab → select genre → select model → Generated Prompt

### How It Works (Implementation Detail)

**No LLM is used.** Prompts are generated entirely by deterministic Python code in `api/services/blueprint_service.py`. The process:

1. Query last 60 days of snapshots for the genre (anchored to `MAX(snapshot_date)`)
2. Filter snapshots where `signals_json` contains the genre tag
3. Aggregate Song DNA across matching tracks:
   - From `signals_json->>'audio_features'`: avg tempo, dominant key/mode, mean energy/valence/danceability
   - From `signals_json->>'primary_theme'` and `themes`: lyrical theme frequency count
   - From `signals_json->>'spotify_popularity'`: proxy for energy if no audio features
4. Format into a model-specific string template:

```
Suno:   "STYLE: {genre}, {tempo} BPM, {key} {mode}, {mood} mood, {energy_desc}"
        + lyrics skeleton with [Intro]/[Verse]/[Pre-Chorus]/[Chorus]/[Bridge]/[Outro] tags

Udio:   "PROMPT: {genre}, {tempo} BPM, {mood}, {energy}, Themes: {themes}"

SOUNDRAW: JSON params { mood, genre, tempo, energy_levels, length }

MusicGen: "PROMPT: {genre}, {tempo} BPM, {mood}, {energy}, instrumental"
```

5. Return blueprint (sonic profile + lyrical profile) + formatted prompt

### Current Limitation

Only 121/2,146 tracks have audio features populated (the `spotify_audio` scraper has never run despite being enabled). Most blueprints currently lack tempo/key/energy data and produce generic prompts. Once `spotify_audio` scraper accumulates data, blueprints will be rich and specific.

### Prompt Generation — On the Fly vs. Precomputed

**Entirely on the fly.** Nothing is precomputed on ingest. When you click a genre:
- Fresh DB query runs
- Latest 60 days of data aggregated
- Prompt formatted in ~100-200ms

**No caching** (deliberately — genre trends shift daily, stale blueprints waste song generation budget).

---

## 12. Model Validation & Backtesting

**UI:** Model Validation page — timeline charts, accuracy metrics, genre breakdown table

### What the Model Is

Currently: `sklearn.ensemble.GradientBoostingClassifier` (basic mode) or advanced LightGBM ensemble (Phase 2+).

**Binary classification:** Will this entity reach top-20 within 14 days? (yes/no)

**Training data requirements:**
- Entities with ≥14 days of snapshot history
- Minimum 30 valid training rows (otherwise training is skipped)
- Features computed as of a cutoff date; label = did it reach top-20 in the following 14 days

**Current status (April 2026):** Model has not run successfully yet. Only 4-5 distinct recent snapshot dates exist, insufficient to generate 30 labeled training examples. Once daily scraping accumulates 14+ consecutive days, the 3am Celery task will produce the first real model.

### Feature Engineering

Features extracted per entity at a cutoff date:
- `avg_score`, `max_score`, `velocity`, `acceleration` (from trending_snapshots)
- `platform_count` (distinct platforms with data)
- `days_since_first_seen`, `snapshot_count`
- `genre_*` flags (from signals_json genre strings)
- `audio_*` features (tempo, energy, valence — when populated)

### Backtesting

For each evaluation period (monthly slices of historical data):
1. Compute features as-of period start
2. Predict using stored model
3. Compare against actuals (did they reach top-20?)
4. Record: MAE, precision, recall, F1, sample count

Results stored in `backtest_results` table, visualized in Model Validation page.

**Current status:** `backtest_results` is empty. The Celery Beat task runs at 4:30am but requires: (a) a trained model to exist, and (b) the subprocess path to resolve correctly in Railway's container.

### Why the Model Validation Page is Empty

1. `predictions` table: 0 rows — model has never trained successfully
2. `backtest_results` table: 0 rows — backtest has never run
3. Root cause: insufficient consecutive daily data + container working directory issue with `subprocess.run([sys.executable, "scripts/train_model.py"])`

**ETA for first real predictions:** ~14 days after daily scraping stabilizes (mid-April 2026)

---

# Part III — Creation & Production

---

## 13. Song Generation

### Pipeline

```
Blueprint + Artist DNA → Prompt Assembly → Suno/Udio API → Audio File → Quality Check → Pass/Fail
```

### Music Generation APIs (Researched Pricing — April 2026)

| Model | Input | Best For | Per-Song Cost | Monthly Sub | API | Commercial Rights |
|---|---|---|---|---|---|---|
| **Suno Premier** (direct) | Style + lyrics + vocal gender | Full songs with vocals | $0.015 | $30/mo (2K songs) | No official API | License (not ownership) |
| **EvoLink** (Suno wrapper) | Same as Suno | API access to Suno | $0.111 | Pay-as-you-go | REST API | Via Suno license |
| **CometAPI** (Suno wrapper) | Same as Suno | API access to Suno | $0.144 | Pay-as-you-go | REST API | Via Suno license |
| **Udio Pro** (direct) | Prompt + lyrics + audio ref | Style transfer | $0.0125 | $30/mo (2.4K songs) | No official API | Yes (downloads broken as of 4/2026) |
| **SOUNDRAW** | Mood, genre, tempo, energy | Batch instrumental | $0.50 | $500/mo (1K songs) | Official REST API | Royalty-free |
| **MusicGen** (Replicate) | Text + melody reference | Self-hosted instrumental | $0.064/run | Pay-per-use | REST API | MIT (code) / CC-BY-NC (weights) |
| **Stable Audio 2.5** | Text prompt | Short clips/SFX | $0.20 | Pay-per-use | REST API | License required |

**Recommendation:** Start with Suno Premier ($30/mo, ~2K songs) for prototyping. Move to EvoLink or CometAPI wrapper ($0.11-0.14/song) for API automation. No fully stable, official, developer-friendly vocal API exists as of April 2026 — this is a market gap.

### Quality Assurance

After generation: compare audio features against blueprint (tempo ±10%, energy ±0.15). Check duration (90-300s), silence gaps. Max 3 regeneration attempts.

---

## 14. Lyrics Generation

Two approaches, both valid:

**Approach A: Suno generates lyrics from a prompt.** Give Suno a general lyric direction in the style field and let it write. This is simpler and produces lyrics that naturally fit the melody.

**Approach B: Pre-generate lyrics via Groq/Llama, then feed to Suno.** More control over theme and vocabulary, but lyrics may not perfectly match the generated melody.

**Recommended: Start with Approach A** (let Suno handle it), move to Approach B when we want more control over lyrical consistency per artist.

**Lyrics prompt template (for either approach):**
```
Theme: {blueprint.primary_theme}
Mood: {blueprint.mood}
Vocabulary: {artist_dna.vocabulary_level}
Structure: {blueprint.section_structure}
Voice: {artist_dna.lyrical_voice}
Style: {artist_dna.influences}
```

**Plagiarism risk:** Accepted. LLMs and Suno may occasionally produce lines similar to existing songs. The risk is low for full-song plagiarism but non-zero for individual phrases. Mitigation: the sheer volume of output makes any single instance insignificant.

**Profanity/language controls:** Add to the generation prompt:
- `negativeTags` in Suno: "explicit, profanity, slurs, violence"
- Or: allow explicit content per-artist (some genres expect it — hip-hop, punk)
- Per-artist `content_rating` field in Artist DNA: "clean", "mild", "explicit"

**Quality check:** Not needed as a separate step. Suno's output quality is the quality check. If the song sounds bad, the audio QA step (Section 13) catches it.

**Copyright ownership:** The label (SoundPulse Records LLC) owns the lyrics. ASCAP/BMI registration does NOT require lyrics text submission — only title, writer names, and publisher info. The "writer" is listed as the artist's legal name (a fictional person) with publishing under the label entity.

---

## 15. Artist Creation & Management

### Creation Pipeline

Genre opportunity → Artist Success Predictor → Generate profile (demographics, voice, visual, persona, narrative) → Generate visual assets (portrait, photos, banners) → Create platform accounts (semi-manual) → First 2-3 songs

**Platform account creation (the one manual step):**
Account creation on Instagram, TikTok, and YouTube cannot be automated via API (against TOS). For each new artist, a human creates the accounts using the generated profile data. This takes ~15 minutes per artist and happens infrequently (new artist creation is triggered by genre opportunities, maybe 1-3 new artists per month).

- **TikTok + Instagram:** Created manually using generated name, bio, profile photo
- **YouTube:** Created manually via Google account
- **Spotify for Artists:** Claimed AFTER first distributed release goes live (Spotify requires a release to verify)
- **Handles stored in `ai_artists` table** for automated posting going forward

Once accounts exist, ALL subsequent activity (posting content, uploading videos, engaging) is fully automated via APIs.

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

### The 6-Angle Reference Portrait

When a new artist is created, a **6-angle reference sheet** is generated as the master visual identity document. This single image contains the artist's face from 6 angles (front, 3/4 left, 3/4 right, profile left, profile right, slight up-angle) with consistent features, lighting, and style.

This reference sheet is:
- Stored permanently as the artist's `visual_dna.reference_image_id`
- Used as a **seed/reference image** for ALL subsequent image generation
- Fed into Veo for video generation (face consistency across clips)
- Fed into image models for cover art, social posts, promo photos

**Generating the 6-angle reference:** Use Stable Diffusion + IP-Adapter or Flux with a detailed prompt describing the artist's face, then use img2img to generate the 6-angle sheet from the initial portrait.

### Image Models

| Model | Use Case | API | Consistency Method |
|---|---|---|---|
| **Stable Diffusion + IP-Adapter** | 6-angle reference generation, face-locked images | ComfyUI / Replicate | IP-Adapter locks face from reference |
| **DALL-E 3** | Cover art, social posts (non-face) | OpenAI REST API | Detailed prompts + brand colors |
| **Flux** | High-quality promo photos | fal.ai / Replicate | Reference image seeding |
| **Google Veo** | TikTok videos, visualizers, music videos | Google API | 6-angle reference as face seed |

### Cover Art Strategy

Cover art does NOT need to feature the artist's face (especially for new/unknown artists). Instead:
- Abstract art matching the song's mood + artist's color palette
- Genre-appropriate visual style (dark/moody for trap, bright/colorful for pop, minimal for indie)
- Consistent color palette from `visual_dna.color_palette` across all releases
- Artist face appears on profile photos and social content, not necessarily on every cover

This avoids the hardest image consistency problem (face on cover art) while maintaining brand coherence through color and style.

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

## 17.5. The 0→3K Streams Playbook

The hardest problem in the pipeline: getting anyone to listen to a song by an unknown AI artist. This section specifies the exact automated tactics, costs, and expected yields.

### The 30-Day Launch Playbook (~$500/song)

| Week | Action | Cost | Expected Streams | Automation |
|---|---|---|---|---|
| **Pre-release (W-2 to W-1)** | Pre-save via Hypeddit. Spotify editorial pitch. Prepare 10-15 short-form videos. | $0-10 | 100-200 pre-saves | Full |
| **W1 Days 1-3** | Playlist Push campaign ($300). Meta ads ($100) driving to smart link. Daily TikTok/Reels/Shorts. | $400 | 1,000-2,000 | Full (Meta Ads API) |
| **W1-2** | SubmitHub campaign (50 credits). Target genre curators. | $40 | 500-1,500 | Semi (browser automation) |
| **W2-3** | Continue daily video posts. Groover campaign (25 curators). Discord community posts. | $55 | 500-1,000 | Full for video, semi for Groover |
| **W3-4** | Scale what's working. Reinvest in channels with best CPM. | $0-50 | 500-1,500 | Full |
| **TOTAL** | | **~$500** | **~3,000-6,000** | |

### Channel-by-Channel Breakdown

**Tier 1: Highest ROI (automate first)**

| Channel | Cost | Streams/$ | Automation | Risk |
|---|---|---|---|---|
| **Playlist Push** | $300/campaign | ~25 streams/$ | Browser automation | Low |
| **Meta Ads → Smart Link** | $0.15-0.40/stream | 2.5-6.7 streams/$ | Full (Meta Ads API) | Low |
| **Pre-save → Hypeddit** | Free | Converts to day-1 streams | Full (API) | None |
| **Short-form video** (TikTok/Reels/Shorts) | $0-50/mo tools | Unpredictable (viral potential) | Full (Veo + scheduling) | Low |

**Tier 2: Supplementary**

| Channel | Cost | Streams/$ | Automation | Risk |
|---|---|---|---|---|
| **SubmitHub** | $0.80-1.00/credit, ~$8-12/placement | ~60-200 streams/placement | Browser automation | Medium (AI detection: 98.5% accuracy) |
| **Groover** | ~$2.18/curator pitch | Higher acceptance (10-21%) | Browser automation | Medium |
| **TikTok sound seeding** (Playlist Push TikTok) | $285+/campaign | 500-2,000 Spotify streams per viral TikTok | Semi | Low |

**Tier 3: Low-yield / Supplementary**

| Channel | Notes |
|---|---|
| **Reddit** (r/listentothis etc.) | High ban risk for automated posting. Best as organic supplementary. |
| **Discord communities** | 5-50 streams per post. Useful for building early followers. |
| **Blog coverage** (SubmitHub blogs) | 50-500 streams per placement. Good for SEO/credibility. |
| **Playlist exchange networks** | AVOID. Poor engagement metrics can HURT algorithmic standing. |

### Automation Stack for Promotion

| Tool | Purpose | Cost | API? |
|---|---|---|---|
| **Hypeddit** | Pre-save links, smart links, download gates | Free-$10/mo | Dashboard |
| **Feature.fm** | Smart links, fan data, ad integration | $9.99/mo | Dashboard |
| **Meta Ads Manager** | Facebook/Instagram ad campaigns | Per-budget | Full API |
| **Playlist Push** | Curator + TikTok campaigns | Per-campaign | Browser automation |
| **SubmitHub** | Playlist + blog pitching | Per-credit | Browser automation |
| **ShortSync / Buffer** | Cross-platform video scheduling | $0-20/mo | API |
| **Runway / Pika** | AI video generation for social clips | $10-50/mo | API |

### Critical Warning: AI Detection

SubmitHub has an AI Song Checker (98.5% detection accuracy). They require disclosure of AI involvement. Songs flagged as AI may be rejected by curators.

Spotify has intensified artificial streaming detection. AI-generated music is not banned, but tracks with bot-like traffic patterns face revenue freezes (EUR 10/track/month penalty) or permanent bans.

**Mitigation:** Focus on generating genuine engagement. Playlist Push and Meta Ads drive real human listeners. Avoid any bot/fake stream services.

### Spotify Algorithm Trigger Thresholds

The first 72 hours are critical. Key thresholds for algorithmic pickup:

| Signal | Threshold | What It Triggers |
|---|---|---|
| ~2,500 streams + 375 saves in first 2 weeks | Discover Weekly consideration | Algorithmic playlist inclusion |
| High listen-through rate (>50% completion) | Autoplay/Radio inclusion | Passive discovery streams |
| 30+ Spotify followers on artist profile | Release Radar distribution | Automated notification to followers |
| 100+ pre-saves | Day-1 signal boost | Stronger first-72-hour metrics |

---

## 18. Marketing & Social

### TikTok Pipeline

**Hook extraction algorithm:**
The 15-second clip is the hook + the 5 seconds building into the hook. Specifically:
1. Identify the chorus section from Spotify Audio Analysis (sections endpoint, highest energy + loudness section)
2. Find the start of the chorus
3. Extract 5 seconds before chorus start (the build-up/anticipation) + first 10 seconds of chorus = 15-second clip
4. If no clear chorus detected: use the segment with the highest loudness peak and extract 7.5 seconds before and after
5. Apply TikTok-optimized audio processing (slight compression, normalize loudness)

**Video generation: Google Veo**
- Seed with the artist's 6-angle reference portrait
- Prompt: artist visual DNA + song mood + lyric snippet overlay
- Output: 15-second vertical video (9:16 aspect ratio)
- Fallback: static image with audio visualizer waveform + lyric overlay (FFmpeg)

**Posting:** TikTok Content Posting API (developer access — obtainable)
- Caption: generated by Groq using artist social voice
- Hashtags: genre tags + trending music hashtags + #newmusic
- Sound: linked to full track (after distribution)

**Monitoring and boosting:**
- Track likes acceleration (not absolute count — the rate of growth)
- Threshold: if likes acceleration exceeds 2x the artist's baseline within first 6 hours → boost signal
- "Boost" = post 2 more TikToks with different edits of the same sound + cross-post to Instagram Reels + YouTube Shorts
- If sound gets adopted by other creators (UGC creates > 10) → maximum boost: daily content featuring the sound

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

### PRO Registration Automation (Researched April 2026)

**Winner: TuneRegistry** — $35-95/month flat fee, 0% commission, CSV bulk import.

| Organization | TuneRegistry Handles? | Direct Alternative | Automation Path |
|---|---|---|---|
| **ASCAP** | ✅ Daily delivery | No API, no bulk import | Use TuneRegistry |
| **BMI** | ✅ Daily delivery | No API, no bulk import | Use TuneRegistry |
| **SESAC** | ✅ Daily delivery | No API | Use TuneRegistry |
| **HFA** | ✅ Bi-monthly delivery | No API | Use TuneRegistry |
| **Music Reports** | ✅ Weekly delivery | No API | Use TuneRegistry |
| **SoundExchange** | ✅ DDEX feed | Has API (request at techsupport@soundexchange.com) + CSV bulk upload | TuneRegistry OR direct API |
| **The MLC** | ✅ Supported | Spreadsheet bulk upload (300 row max) + CWR files | TuneRegistry OR direct bulk |

**Automation pipeline:**
1. Song is distributed → ISRC assigned by distributor
2. SoundPulse generates CSV matching TuneRegistry's bulk import template: title, writer names + IPI numbers, publisher (SoundPulse Records), ownership splits (100%), ISRC
3. CSV uploaded to TuneRegistry (browser automation via Playwright, or manual monthly batch)
4. TuneRegistry delivers to all 7+ organizations automatically

**Required per song:** Title, writer legal name, writer IPI number (obtained on ASCAP/BMI membership), publisher name, publisher IPI, ownership split %, ISRC

**Setup requirements:**
- Register as publisher with ASCAP or BMI (one-time, ~$50 fee)
- Obtain IPI number for the publishing entity
- TuneRegistry Business account ($95/month — handles unlimited works)

**Timeline to first royalty:** 9-18 months from performance date (industry standard, unavoidable)

**Songtrust:** NOT recommended. 15-20% commission on collected royalties, no API, no bulk import. TuneRegistry at flat fee is far more cost-effective at scale.

**Implementation order:**
1. TuneRegistry Business + CSV export pipeline from SoundPulse DB
2. SoundExchange direct (request their API for recordings)
3. MLC membership + bulk upload for mechanical royalties
4. Ensure all writer/publisher entities have IPI numbers

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

### Payment Structure

All revenue flows to the record label's bank account (human-provided). The label entity (SoundPulse Records LLC) is the payee for all distribution, PRO, and sync income. No automated payment splitting between AI artists — they're all owned by the same entity.

Revenue reconciliation across sources (Revelator, SoundExchange, ASCAP, distributor) is handled by pulling reports from each and aggregating in the `revenue_events` table.

---

# Part V — Platform & Infrastructure

---

## 21. AI Assistant

**Status: BUILT** (hideable UI: TODO — see below)

Groq/Llama 3.3 70B chat interface. Gathers DB context (trending, genres, stats, scrapers), answers questions in natural language.

Example: "If I wanted a Christian rock single, what should the artist and song look like?" → queries genre data, generates blueprint-style recommendation.

### 21.1 Hideable Panel (UI requirement)

The Assistant currently mounts as a fixed-width 288px right-side `<aside>` (`frontend/src/components/AssistantPanel.jsx`) and is always visible, eating screen real estate on every page including ones where the user is focused on data exploration.

**Requirement:** the user must be able to hide and re-show the Assistant panel.

**Behavior:**
- A toggle control collapses the panel out of the main layout flow; main content reflows to fill the freed width.
- When hidden, a small persistent affordance (icon button on the right edge — e.g. a `MessageSquare` chevron) lets the user re-open it.
- A keyboard shortcut (`Cmd/Ctrl + .`) toggles the panel.
- Preference persists across page navigation and reloads via `localStorage` key `soundpulse.assistant.visible` (default `true` — opt-in to the new UX, not opt-out).
- The toggle lives in the panel header (collapse arrow on the left of the header) AND in the floating re-open button (when hidden).
- Panel state is global, not per-page — toggling on Dashboard hides it on Explore too.
- Implementation: lift visibility into a top-level context (e.g. `AssistantVisibilityContext`) consumed by both `Layout.jsx` (which conditionally renders the aside) and any header that exposes the toggle. Avoid prop drilling.

**Why:** the assistant is useful but the dashboard, explore, and song lab pages need full horizontal real estate when the user is scanning trending tables, genre trees, or generated prompts. Forcing it always-on penalizes the most important workflows.

**Out of scope (for this iteration):** resizable panel width, multiple chat tabs, history persistence beyond the in-memory message list.

---

## 21.5. Full Data Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  DATA SOURCES                                                                            ║
╠══════════════╦══════════════════╦════════════════════╦══════════════╦════════════════════╣
║  CHARTMETRIC ║  SPOTIFY DIRECT  ║  SPOTIFY AUDIO     ║   SHAZAM     ║  GENIUS (ready)    ║
║  $350/mo     ║  Free API        ║  Analysis API      ║  RapidAPI    ║  Free API          ║
║  2 req/sec   ║  every 6h        ║  daily             ║  every 4h    ║  daily             ║
╠══════════════╬══════════════════╬════════════════════╬══════════════╬════════════════════╣
║ chart_rank   ║ search results   ║ tempo (BPM)        ║ chart_rank   ║ lyrics text        ║
║ artist_name  ║ track_id         ║ key + mode         ║ shazam_id    ║ verse/chorus       ║
║ track_title  ║ artist_name      ║ energy (0-1)       ║ track_title  ║ themes             ║
║ spotify_id   ║ popularity       ║ valence (0-1)      ║ artist_name  ║ vocabulary         ║
║ genres str   ║ genre hints      ║ danceability (0-1) ║              ║ word density       ║
║ isrc         ║                  ║ acousticness       ║              ║                    ║
║ platform_rank║                  ║ instrumentalness   ║              ║                    ║
║ raw_score    ║                  ║ loudness           ║              ║                    ║
╚══════════════╩══════════════════╩════════════════════╩══════════════╩════════════════════╝
         │                │                 │                 │                │
         ▼                ▼                 ▼                 ▼                ▼
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  ENTITY RESOLUTION (api/services/entity_resolution.py)                                  ║
║  Deduplicates across sources using: spotify_id → ISRC → fuzzy title+artist (RapidFuzz  ║
║  >85%) → creates new entity if no match                                                  ║
╚═══════════════════════════════════════╦══════════════════════════════════════════════════╝
                                        │
                    ╔═══════════════════╩═══════════════════╗
                    ▼                                       ▼
╔═══════════════════════════════╗         ╔═════════════════════════════════╗
║  TABLE: tracks                ║         ║  TABLE: artists                 ║
║  id (UUID, PK)                ║         ║  id (UUID, PK)                  ║
║  title                        ║         ║  name                           ║
║  artist_id (FK → artists)     ║         ║  spotify_id                     ║
║  spotify_id                   ║         ║  image_url                      ║
║  isrc                         ║         ║  genres[] ← classifier          ║
║  chartmetric_id               ║         ║  metadata_json                  ║
║  genres[] ← classifier        ║         ║  audio_profile                  ║
║  audio_features ←spotify_audio║         ╚═════════════════════════════════╝
║  metadata_json                ║
╚═══════════════════════════════╝
                    │
                    ▼
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  TABLE: trending_snapshots  (one row per entity × platform × date)                       ║
╠══════════════════════════════════════════════════════════════════════════════════════════╣
║  RAW FIELDS (from scrapers):                                                             ║
║    entity_id, entity_type, snapshot_date, platform                                      ║
║    platform_rank     ← chart position from source                                       ║
║    platform_score    ← raw score from source                                            ║
║    signals_json      ← full payload blob: genres str, audio_features, artist_name,      ║
║                         spotify_popularity, themes, etc.                                 ║
║                                                                                          ║
║  COMPUTED FIELDS (on ingest, api/services/normalization.py + aggregation.py):            ║
║    normalized_score  ← rank/score normalized to 0-100 across all entities/dates         ║
║    velocity          ← score change vs. same entity 7 days prior                        ║
║    composite_score   ← weighted avg of normalized_score across all platforms for entity ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝
         │                              │                              │
         ▼                              ▼                              ▼
╔═══════════════════╗    ╔══════════════════════════╗    ╔════════════════════════════════╗
║  TABLE: genres    ║    ║  BLUEPRINT SERVICE        ║    ║  ML MODEL (ml/train.py)        ║
║  (static taxonomy)║    ║  on-the-fly, no LLM       ║    ║  GradientBoostingClassifier    ║
║  959 genres       ║    ║                           ║    ║  → ml/models/*.joblib          ║
║  hierarchical     ║    ║  1. Pull 60d snapshots    ║    ║                                ║
║  12 root categories║   ║  2. Extract genre from    ║    ║  INPUTS (per entity cutoff):   ║
║  platform mappings║    ║     signals_json genres   ║    ║  avg_score, max_score          ║
╚═══════════════════╝    ║  3. Avg audio_features    ║    ║  velocity, acceleration        ║
                         ║  4. Count lyric themes    ║    ║  platform_count                ║
                         ║  5. Compute opp score:    ║    ║  days_since_first_seen         ║
                         ║     0.4×momentum          ║    ║  snapshot_count                ║
                         ║   + 0.4×quality           ║    ║  genre flags                   ║
                         ║   + 0.2×(1-saturation)    ║    ║  audio features (when avail)   ║
                         ║  6. Format prompt string  ║    ║                                ║
                         ║     per model (template)  ║    ║  OUTPUT:                       ║
                         ╚══════════════════════════╝    ║  probability 0-1               ║
                                    │                    ║  (will reach top-20 in 14d?)   ║
                                    │                    ╚══════════════╦═════════════════╝
                                    │                                   │
                                    │                    ╔══════════════╩═════════════════╗
                                    │                    ║  TABLE: predictions             ║
                                    │                    ║  entity_id, entity_type         ║
                                    │                    ║  predicted_score (probability)  ║
                                    │                    ║  confidence                     ║
                                    │                    ║  horizon (7d/30d/90d)           ║
                                    │                    ║  predicted_at                   ║
                                    │                    ║  resolved_at (after horizon)    ║
                                    │                    ║  actual_score (feedback)        ║
                                    │                    ╚══════════════╦═════════════════╝
                                    │                                   │
                                    ▼                                   ▼
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  FRONTEND — WHERE EACH DATA POINT APPEARS                                                ║
╠══════════════════╦══════════════════╦═══════════════════╦═══════════════╦═══════════════╣
║  DASHBOARD       ║  EXPLORE         ║  SONG LAB         ║  MODEL VAL    ║  ASSISTANT    ║
╠══════════════════╬══════════════════╬═══════════════════╬═══════════════╬═══════════════╣
║ Trending Table:  ║ Trending Table   ║ Genre List:       ║ Timeline      ║ Live DB query ║
║  track title     ║  (same as →)     ║  genre name       ║ charts:       ║ + PRD summary ║
║  artist name     ║                  ║  opportunity_score║  predicted vs ║ always in     ║
║  composite_score ║ Genre Tree:      ║  momentum label   ║  actual rate  ║ system prompt ║
║  velocity        ║  959 genres from ║  track_count      ║               ║               ║
║  platform badges ║  genres table    ║                   ║ Metric cards: ║ Topic keyword ║
║  7d sparkline    ║                  ║ Blueprint Card:   ║  MAE           ║ detection →   ║
║                  ║ Filters:         ║  avg tempo (BPM)  ║  precision    ║ injects       ║
║ Breakout Preds:  ║  entity type     ║  key + mode       ║  recall       ║ relevant PRD  ║
║  predicted score ║  time range      ║  energy %         ║  F1 score     ║ section       ║
║  confidence bar  ║  genre           ║  mood/valence     ║               ║               ║
║                  ║                  ║  lyrical themes   ║ Genre table:  ║               ║
║ Genre Heatmap:   ║                  ║                   ║  per-genre    ║               ║
║  genre names     ║                  ║ Prompt Output:    ║  MAE/F1       ║               ║
║  momentum score  ║                  ║  Suno style text  ║               ║               ║
║                  ║                  ║  + lyrics skeleton║               ║               ║
║                  ║                  ║  Udio prompt      ║               ║               ║
║                  ║                  ║  SOUNDRAW JSON    ║               ║               ║
║                  ║                  ║  MusicGen prompt  ║               ║               ║
╚══════════════════╩══════════════════╩═══════════════════╩═══════════════╩═══════════════╝

╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  CELERY BEAT SCHEDULE (UTC)                                                              ║
╠══════════════╦══════════════════╦═════════════════════════════════════════════════════════╣
║  Time        ║  Task            ║  What it does                                          ║
╠══════════════╬══════════════════╬═════════════════════════════════════════════════════════╣
║  */4h :15    ║  chartmetric     ║  Pull Spotify/Shazam US charts → trending_snapshots    ║
║  */6h :00    ║  spotify         ║  Search top tracks per genre → trending_snapshots      ║
║  */4h :30    ║  shazam          ║  Pull Shazam chart → trending_snapshots                ║
║  daily 2:00  ║  musicbrainz     ║  Enrich tracks with ISRC + genre tags                 ║
║  daily 3:00  ║  train_model     ║  Retrain GBM on all history → ml/models/*.joblib       ║
║  */6h :45    ║  gen_predictions ║  Score top-50 trending entities → predictions table   ║
║  daily 4:30  ║  backtest        ║  Evaluate model vs actuals → backtest_results table   ║
║  */15m       ║  health_check    ║  Ping all scraper endpoints                            ║
╚══════════════╩══════════════════╩═════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  DATA GAPS (April 2026)                                                                  ║
╠══════════════════════════════════════════════════════════════════════════════════════════╣
║  audio_features  121/2,146 tracks  spotify_audio scraper enabled but never run          ║
║  tracks.genres   102/2,146 tracks  genre classifier runs on ingest but sparse results   ║
║  predictions     0 rows            model needs 14+ consecutive days of history          ║
║  backtest_results 0 rows           depends on predictions + container path fix           ║
║  genius_lyrics   0 rows            scraper ready but disabled in scraper_configs         ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝
```

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

### 22.2. DB Stats View (TODO — new feature)

A diagnostic view in the admin/dashboard area answering "what's actually in the database, and how is it growing?"

**Backend endpoints:**

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/admin/db-stats` | Current totals across all tables |
| GET | `/api/v1/admin/db-stats/history?days=90` | Daily counts of new rows per table for the last N days, derived from `created_at` timestamps |

**`GET /api/v1/admin/db-stats` response shape:**

```json
{
  "as_of": "2026-04-11T10:16:00Z",
  "tables": {
    "tracks": {"total": 2146, "with_audio_features": 121, "with_genres": 102, "with_isrc": 1843},
    "artists": {"total": 487, "with_genres": 156, "with_spotify_id": 412},
    "trending_snapshots": {"total": 9031, "distinct_dates": 40, "distinct_platforms": 4, "earliest_date": "2026-03-02", "latest_date": "2026-04-11"},
    "genres": {"total": 906, "active": 906, "with_audio_profile": 612},
    "predictions": {"total": 0, "by_horizon": {"7d": 0, "30d": 0, "90d": 0}},
    "backtest_results": {"total": 0, "completed_runs": 0},
    "scraper_configs": {"total": 8, "enabled": 6},
    "api_keys": {"total": 4}
  }
}
```

**`GET /api/v1/admin/db-stats/history?days=90` response shape:**

```json
{
  "as_of": "2026-04-11T10:16:00Z",
  "days": 90,
  "series": [
    {
      "date": "2026-04-11",
      "tracks_added": 12, "tracks_total": 2146,
      "artists_added": 3, "artists_total": 487,
      "snapshots_added": 220, "snapshots_total": 9031,
      "predictions_added": 0, "predictions_total": 0
    },
    ...
  ]
}
```

**Frontend page** (new `frontend/src/pages/DbStats.jsx` at route `/db-stats`):
- **Top section — current state**: cards for each table showing total + key sub-counts (e.g. `tracks: 2,146 (121 with audio, 102 classified)`). Color-coded warnings when sub-counts are <50% of total (e.g. classification coverage <50% → yellow).
- **Middle section — additions over time**: stacked bar chart showing daily new rows per table (tracks/artists/snapshots/predictions) for the last 90 days.
- **Bottom section — totals over time**: line chart showing cumulative row counts for each table over the last 90 days.
- **Filter**: date range selector (7d / 30d / 90d / custom).
- **Auth**: admin key required (this is diagnostic data, not for end users).

**Why this matters:** without this view, the team has no visibility into whether scrapers are actually running, whether the genre classifier is improving, whether the ML model is producing predictions, or how the database is growing. Currently the only way to answer "how many tracks do we have?" is to query Neon directly. This is the canonical source of truth for "is the data pipeline healthy."

**Out of scope (this iteration):** per-source breakdowns (e.g. "snapshots by chartmetric vs spotify"), per-genre track counts, drilldown into specific entities. Those can come later if useful.

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
| `genres` | 959 genre taxonomy |
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

| Phase | Infra | APIs | Generation | Promo/Song | Distribution | Total (excl promo) | Promo Budget |
|---|---|---|---|---|---|---|---|
| Phase 1 (now) | $70 | $360 | — | — | — | **$430** | $0 |
| Phase 2 | $170 | $400 | — | — | — | **$570** | $0 |
| Phase 3 (10 songs/mo) | $200 | $400 | $1.50 | $500 | $120/yr | **$620** | $5,000/mo |
| Phase 3 (50 songs/mo) | $300 | $400 | $7 | $300 avg | $120/yr | **$720** | $15,000/mo |
| Phase 3 (200 songs/mo) | $500 | $400 | $28 | $200 avg | $120/yr | **$940** | $40,000/mo |

**The dominant cost is promotion, not generation.** Generation is essentially free ($0.015/song via Suno Premier). Promotion (~$200-500/song for playlist pitching + ads) is where the money goes. As the label builds audience across artists, per-song promo costs decrease (existing followers create organic streams).

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
