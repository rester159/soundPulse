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

### Payment Structure

All revenue flows to the record label's bank account (human-provided). The label entity (SoundPulse Records LLC) is the payee for all distribution, PRO, and sync income. No automated payment splitting between AI artists — they're all owned by the same entity.

Revenue reconciliation across sources (Revelator, SoundExchange, ASCAP, distributor) is handled by pulling reports from each and aggregating in the `revenue_events` table.

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
