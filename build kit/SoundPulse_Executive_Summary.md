# SoundPulse
## A Fully Autonomous Virtual Record Label

**Product Requirements Document** — April 2026

*SoundPulse is a virtual record label with zero employees. It analyzes what makes music succeed, generates songs that will succeed, distributes them to every platform, and collects the royalties. No humans in the loop.*

---

## The Vision

SoundPulse is not a tool for record labels. It IS a record label — one that runs entirely on software.

The complete pipeline, end to end, with no human intervention:

1. **Analyze** — What sonic, cultural, and release characteristics are driving success in any given micro-genre right now?
2. **Blueprint** — Generate a specific, reproducible specification for a song that will succeed: genre, tempo, key, mood, arrangement, lyrics, vocal style, production style
3. **Generate** — Feed the blueprint to AI music generation models (Suno, Udio) to produce the actual master recording
4. **Distribute** — Upload the finished track to every streaming platform (Spotify, Apple Music, TikTok, YouTube, Amazon, Deezer, Tidal) via distribution API
5. **Register** — Register the song with PROs (ASCAP, BMI) and publishing administrators for royalty collection
6. **Optimize** — Monitor performance, A/B test release strategies, adjust future blueprints based on what's working
7. **Collect** — Royalties flow back automatically from streams, sync placements, and radio play

The output of SoundPulse is not a dashboard. It is revenue.

---

## The Pipeline

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
│ 2. BLUEPRINT — What should the next song look like?  │
│    - Target genre + sub-genre                        │
│    - Optimal sonic profile (BPM, key, energy, mood)  │
│    - Arrangement template (structure, build pattern)  │
│    - Lyrical themes + vocabulary style               │
│    - Vocal style recommendation                      │
│    - Production style (instruments, textures)        │
│    - Reference tracks ("sounds like X meets Y")      │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ 3. GENERATE — Feed the blueprint to AI music models  │
│                                                      │
│    Model input mapping:                              │
│    ┌────────────┬───────┬──────┬────────┬──────────┐│
│    │ Parameter  │ Suno  │Udio  │MusicGen│ SOUNDRAW ││
│    ├────────────┼───────┼──────┼────────┼──────────┤│
│    │ Genre      │style  │prompt│ text   │ param    ││
│    │ Tempo      │style  │prompt│ text   │ param    ││
│    │ Mood       │tags   │prompt│ text   │ param    ││
│    │ Structure  │[Verse]│lyrics│ N/A    │ N/A      ││
│    │ Vocals     │gender │gender│ N/A    │ N/A      ││
│    │ Lyrics     │full   │full  │ N/A    │ N/A      ││
│    │ Instruments│tags   │prompt│ text   │ limited  ││
│    │ Audio ref  │upload │upload│melody  │ N/A      ││
│    │ Neg control│tags   │ N/A  │ N/A    │ N/A      ││
│    └────────────┴───────┴──────┴────────┴──────────┘│
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ 4. DISTRIBUTE — Push to every platform               │
│    - Upload master + metadata via distribution API   │
│    - Spotify, Apple Music, TikTok, YouTube, Amazon,  │
│      Deezer, Tidal, 150+ platforms                   │
│    - Set release date, cover art, credits            │
│    - Platform: DistroKid/Ditto/LANDR API             │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ 5. REGISTER — Royalty collection setup               │
│    - Register with PROs (ASCAP/BMI) via Songtrust   │
│    - Publishing administration                       │
│    - ISRC + UPC code assignment                      │
│    - Sync licensing marketplace listing              │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ 6. OPTIMIZE — Monitor and iterate                    │
│    - Track performance across all platforms          │
│    - A/B test release strategies                     │
│    - Adjust future blueprints based on results       │
│    - Predicted 30/60/90 day growth trajectory        │
│    - Reinvest revenue into next generation cycle     │
└────────────────────┬────────────────────────────────┘
                     │
                     └──── LOOP BACK TO STEP 1 ────────┘
```

### Example: End-to-End

```
SoundPulse detects: "Melodic trap in C# minor at 140-150 BPM is accelerating.
  Top performers share: sparse verse → dense chorus build, autotuned vocals,
  808 sub-bass, introspective/heartbreak themes, short intros (<15 sec).
  TikTok adoption rate for this profile: 3.2x average.
  Shazam-to-Spotify conversion: 18 days median."

Blueprint generated:
  Genre: melodic trap
  BPM: 145, Key: C# minor
  Energy: 0.72, Valence: 0.28 (melancholic)
  Structure: [Intro 8s] [Verse] [Pre-Chorus] [Chorus] [Verse] [Chorus] [Bridge] [Chorus] [Outro]
  Themes: introspection, heartbreak
  Vocal: male, autotuned, emotional delivery
  Production: 808 bass, hi-hats, atmospheric pads, reverb-heavy
  Reference: "Juice WRLD meets Post Malone"

Suno prompt generated:
  Style: "Melodic trap, 145 BPM, C# minor, dark melancholic mood,
         808 bass, hi-hats, atmospheric pads, autotuned male vocals"
  [Verse 1]
  {lyrics: introspective, simple vocabulary, heartbreak theme}
  [Chorus]
  {lyrics: catchy hook, repetitive, emotionally resonant}

Release strategy:
  Drop: Friday 12am EST (optimal for Spotify algorithmic playlists)
  TikTok: 15-second chorus clip posted 3 days before full release
  Target playlists: Sad Bops, Chill Vibes, Late Night Feels
  Predicted trajectory: 50K streams week 1, 200K by day 30
```

---

## Song DNA — What We Need to Capture

To replicate what makes successful music successful, we decompose every song into a full "DNA profile." This is not just tempo and mood — it includes arrangements, lyrics, themes, production choices, and cultural context. These are also the features that feed the prediction model.

### Sonic Features (from Spotify Audio Analysis)

| Feature Category | Specific Features | Source |
|---|---|---|
| **Tempo & Rhythm** | BPM, time signature, beat regularity, rhythmic complexity | Spotify Audio Analysis (beats, bars, tatums) |
| **Energy & Dynamics** | Overall energy, loudness contour, dynamic range, fade-in/fade-out | Spotify Audio Features + Analysis (segments) |
| **Mood & Tonality** | Key, mode (major/minor), valence (happy/sad), danceability | Spotify Audio Features |
| **Production Style** | Acousticness, instrumentalness, liveness, speechiness | Spotify Audio Features |
| **Timbre Profile** | 12-dimensional timbre vectors per segment — captures instrument texture, brightness, attack | Spotify Audio Analysis (segments.timbre) |
| **Song Structure** | Section types (intro/verse/chorus/bridge/outro), durations, chorus ratio, intro length | Spotify Audio Analysis (sections) + Genius (section headers) |
| **Pitch Content** | 12-dimensional pitch vectors per segment — captures harmonic content, chord progressions | Spotify Audio Analysis (segments.pitches) |

### Lyrical Features (from Genius)

| Feature | What It Captures |
|---|---|
| **Primary themes** | Love, heartbreak, party, flex, introspection, social commentary, nostalgia, empowerment |
| **Vocabulary richness** | Unique words / total words — higher = literary, lower = repetitive/catchy |
| **Chorus repetition ratio** | How much of the song is chorus — higher = more commercially formulaic |
| **Song structure** | Verse count, chorus count, bridge presence, section ordering |
| **Word count & density** | Sparse lyrics (electronic, ambient) vs dense lyrics (rap, folk) |
| **Language** | English vs non-English — critical for market targeting |

### Arrangement & Production (Future Phase — Deeper Analysis)

| Feature | Why It Matters | How to Get It |
|---|---|---|
| **Vocal style** | Male/female, pitch range, autotune, harmonies, ad-libs | Audio ML models (vocal separation + classification) |
| **Instrument palette** | 808s vs live drums, analog vs digital synths, guitar types | Timbre vector clustering from Spotify Analysis |
| **Build patterns** | Sparse verse → dense chorus, gradual builds, drops | Section-level energy/loudness analysis |
| **Hook placement** | Where the catchiest part is — critical for TikTok (first 15 seconds) | Segment analysis + stream skip patterns |
| **Featured artists** | Collaboration patterns that drive cross-audience growth | Chartmetric artist data |
| **Sonic similarity** | "Sounds like Artist X meets Artist Y" | Embedding-based similarity from timbre/pitch vectors |

### Social & Cultural Context (from Chartmetric)

| Feature | Source |
|---|---|
| **Artist social growth velocity** | Chartmetric `/stat/` endpoints (Spotify, Instagram, TikTok, YouTube, Shazam) |
| **Geographic audience distribution** | Chartmetric `/where-people-listen` |
| **Playlist ecosystem** | Which playlists drive growth in this genre |
| **Cross-platform cascade timing** | How long from TikTok viral → Shazam spike → Spotify streams |
| **Collaboration network** | Which artists collab with whom, and what the audience overlap is |

---

## Music Generation Models

### Suno (Primary — richest input surface for full songs with vocals)

| Parameter | Description |
|---|---|
| `style` | Genre/mood/instrumentation string (up to 1000 chars) |
| `prompt` | Lyrics with meta tags: `[Verse]`, `[Chorus]`, `[Bridge]`, `[Drop]`, `[Build]` |
| `vocalGender` | `"m"` or `"f"` |
| `negativeTags` | Elements to exclude |
| `styleWeight` | How strictly to follow style tags |
| `instrumental` | Boolean for instrumental-only |

Also supports vocal delivery tags (`[Whispered]`, `[Belted]`, `[Falsetto]`) and instrument tags (`[Piano]`, `[808s]`, `[Distorted Guitar]`). No official public API — third-party wrappers via sunoapi.org. Paid plans required for commercial use.

### Udio (Alternative — audio conditioning for style transfer)

Similar parameter surface to Suno plus `audio_conditioning_path` for reference audio. No official API — third-party wrappers exist. All plans allow commercial use.

### MusicGen by Meta (Open Source — instrumental only)

| Parameter | Description |
|---|---|
| `prompt` | Text descriptions for generation |
| `melody` | Reference audio tensor (chromagram for melody conditioning) |
| `guidance_scale` | CFG weighting (recommended: 3.0) |
| `duration` | Output length in seconds |

Available via `pip install audiocraft`, Replicate API, or HuggingFace. Code is MIT but **model weights are CC-BY-NC** — commercial use requires fine-tuning your own weights.

### SOUNDRAW (Most Structured API — batch generation)

| Parameter | Description |
|---|---|
| `mood` | 24+ categories (Angry, Dreamy, Elegant, Happy, Mysterious, Powerful, etc.) |
| `genre` | Explicit genre parameter |
| `tempo` / `tempo_2` | BPM range |
| `energy_levels` | Energy profile over time |
| `length` | Duration |

REST API at `soundraw.io/api/v2/musics/compose`. Up to 1000 songs/month. All output is royalty-free. Cleanest programmatic API for parameter-driven generation.

### Generation Pipeline Recommendation

1. **Suno** for full songs with vocals (richest control over lyrics, structure, vocal style)
2. **SOUNDRAW** for programmatic batch generation (explicit parameter API, royalty-free)
3. **MusicGen** for self-hosted instrumental generation (open source, melody conditioning)
4. **Stable Audio** for sound design, intros, atmospheric layers (max 47s clips)

---

## Distribution — Getting Songs on Every Platform

Once a song is generated, it needs to reach listeners on 150+ streaming platforms automatically.

### Distribution API Options

| Service | API Quality | Pricing | What It Does | Verdict |
|---|---|---|---|---|
| **Revelator** | Full REST API, public docs | Custom SaaS pricing | Distribution + rights + royalties in one API. Most comprehensive. | **TOP PICK** — covers distribution, rights management, and royalty reporting in a single API |
| **LabelGrid** | Full REST API, sandbox | $1,428/yr (Starter) to $9,120/yr (Scale) | Release creation, DSP delivery, analytics, DDEX feeds, royalty statements | **BUDGET PICK** — transparent pricing, public docs, sandbox for testing |
| **limbo/ Music** | Full REST API, JSON:API spec | Custom pricing | Album/track creation, distribution requests, territory config, Content ID | Strong API, good documentation |
| **VerseOne Pro** | REST API, Swagger docs | Premium/Enterprise tier | File upload, metadata, ISRC, release management, DSP delivery | Good for automated pipelines |
| **Audicient** | REST API | Multiple tiers | Distribution to 50+ DSPs, royalties, analytics, free white-label | Single API for delivery + analytics |
| **DPM Network** | REST API v1/v2 | Pay-per-release | Catalog delivery, royalty reports, Content ID, SoundExchange | Public docs available |

**Not suitable (no public API):** DistroKid, Amuse, UnitedMasters, LANDR, RouteNote, Stem — all dashboard-only.

### Recommended Distribution Pipeline

```
Song generated by Suno/Udio
        │
        ▼
Revelator API or LabelGrid API
        │
        ├── Upload master audio (WAV/FLAC)
        ├── Set metadata (title, artist, ISRC, UPC, genre, credits)
        ├── Set release date + territories
        ├── Set cover art (AI-generated)
        │
        ▼
Delivered to 150+ DSPs:
  Spotify, Apple Music, TikTok/TikTok Music, YouTube Music,
  Amazon Music, Deezer, Tidal, Pandora, iHeartRadio, etc.
```

---

## PRO Registration & Royalty Collection

Every song needs to be registered with Performance Rights Organizations to collect royalties from streams, radio play, and public performances.

### Critical Finding: No PRO Has a Public API

ASCAP, BMI, SESAC, PRS, GEMA, SACEM — none offer programmatic registration. Registration is done through web portals manually.

### Best Available Options

| Service | What It Does | API? | Pricing |
|---|---|---|---|
| **TuneRegistry** | Registers works with ASCAP, BMI, SESAC, SoundExchange, The MLC, HFA, Music Reports. Daily data delivery. | No API — dashboard only | Subscription (no commission) |
| **Songtrust** | Registers songs with 60+ global pay sources including PROs, YouTube, The MLC | No API — dashboard only | Commission on royalties |
| **Revelator** | Rights management + royalty calculation + reporting via API | **Yes — full API** | Custom SaaS |
| **CD Baby Pro Publishing** | PRO registration + royalty collection | No API | Commission model |

### Automation Strategy

Since no PRO offers an API, the strategy is:

1. **Revelator API** for rights management and royalty tracking (API-native)
2. **TuneRegistry** for actual PRO registration (dashboard — automate via browser automation as stopgap)
3. **Long-term:** Negotiate direct API access with TuneRegistry or build direct PRO integrations

### AI-Generated Music & PRO Eligibility

As of October 2025, ASCAP, BMI, and SOCAN accept partially AI-generated compositions as long as the work includes **meaningful human creative contribution**. Fully AI-generated works are NOT eligible. SoundPulse's model involves human creative direction (selecting genre, approving blueprints, curating output) which may satisfy this requirement — but this is a legal gray area that needs counsel.

---

## The Prediction Model

The prediction engine serves two purposes: (1) predict which existing tracks/artists will break out, and (2) predict whether a generated blueprint will succeed before we produce it.

### What the Model Learns

| Model Type | Question It Answers | Training Data |
|---|---|---|
| **Breakout predictor** | "Will this track enter the top 50 within 7/30/90 days?" | Historical snapshots: features at time T → did it chart at T+N? |
| **Genre-timing model** | "In genre X, what sonic profile is trending upward right now?" | Per-genre feature distributions over time, weighted by success |
| **Growth trajectory model** | "Given day-1 to day-7 signals, what's the 30/60/90 day path?" | Social growth curves from Chartmetric artist stats |
| **Cross-platform cascade model** | "TikTok viral → Shazam → Spotify: what's the timing?" | Platform-specific snapshot sequences for breakout entities |
| **Blueprint scorer** | "Given this Song DNA profile, what's the predicted success probability?" | Song DNA features of historical hits vs non-hits, per genre |

### Feature Engineering (~70 features)

**Per-platform momentum** (7 platforms x 5 features = 35): score 7-day average, velocity, acceleration, score vs 30-day average, rank change

**Cross-platform** (10): platform count, variance, ratios (Shazam/Spotify, TikTok/Spotify), velocity alignment, score entropy

**Temporal** (8): day-of-week, days since release, weekend flag, season

**Genre** (7): genre momentum, new entry rate, trending count, rarity, saturation

**Entity history** (10): age, peak composite, days since peak, previous breakout count, streak length, volatility

**Song DNA** (from audio analysis + lyrics): tempo, energy, valence, danceability, key, mode, chorus ratio, vocabulary richness, primary theme, section count

### Architecture

**Phase 2 — Single Model Baseline:**
- LightGBM on tabular features
- Target: binary breakout prediction (top-50 within 7 days)
- Training: 8+ weeks of historical daily snapshots

**Phase 3 — Three-Model Ensemble:**
- **LightGBM** — tabular features (platform scores, velocities, cross-platform ratios)
- **LSTM with attention** — sequential patterns in 14-day time series
- **XGBoost** — hand-crafted interaction features (e.g., TikTok velocity x Shazam ratio)
- **Ridge meta-learner** combines the three models
- **Isotonic regression** calibrates confidence scores (80% confidence = ~80% actual)
- **Self-learning loop** — daily comparison of predictions vs outcomes, automatic retraining when accuracy degrades

### Cold Start Strategy

1. **Weeks 1–4:** No predictions. Collect data, build entity resolution, validate scoring
2. **Weeks 5–8:** Accumulate historical snapshots. Label ground truth (what actually broke out?)
3. **Weeks 9–12:** Train and evaluate Phase 2 model. Ship `/predictions` with "beta" labeling
4. **Weeks 13+:** Iterate on features, begin ensemble development

**Shortcut:** Chartmetric provides historical chart data going back years. We backfill 2 years of daily snapshots (730 days x 4 chart types = ~255K labeled examples) to skip the waiting period entirely.

### Model Validation

Backtesting system evaluates the model against historical data:
- For each monthly evaluation period: use data before that date to predict, compare against what actually happened
- Metrics tracked: MAE, RMSE, precision, recall, F1, AUC-ROC
- Filterable by micro-genre and individual artist
- As the model trains on more data, prediction error should decrease over time
- Frontend page visualizes predicted vs actual rates, accuracy trends, and per-genre breakdown

---

## Data Collection

SoundPulse collects data across 4 layers, each feeding different parts of the pipeline:

### Layer 1: Chart Data — What's trending

| Scraper | Source | Frequency | Data |
|---|---|---|---|
| `chartmetric` | Chartmetric Charts API | Every 4h | Spotify regional/viral/plays charts, Shazam top charts (US market) |
| `spotify` | Spotify Web API | Every 6h | Search-based trending across 12 genre categories, chart positions |
| `kworb` | Kworb.net | Daily | Spotify daily streaming charts with stream counts |
| `radio` | Billboard.com | Daily | Radio airplay, Hot 100, Country Airplay, Artist 100 |

### Layer 2: Social Growth — How artists are growing

| Scraper | Source | Frequency | Data |
|---|---|---|---|
| `chartmetric_artists` | Chartmetric Artist Stats | Every 12h | Spotify followers/monthly listeners, Instagram followers, TikTok followers/video creates, YouTube subscribers/views, Shazam lookups, geographic audience distribution |

### Layer 3: Sonic DNA — What the music sounds like

| Scraper | Source | Frequency | Data |
|---|---|---|---|
| `spotify_audio` | Spotify Audio Features + Analysis | Daily | Tempo, energy, key, mood, danceability, timbre vectors (12-dim), pitch vectors (12-dim), song structure sections, beat/bar/tatum timing |
| `genius_lyrics` | Genius API + page scraping | Daily | Lyrics text, thematic classification (10 theme categories), vocabulary richness, song structure (verse/chorus/bridge counts), chorus repetition ratio |

### Layer 4: Metadata Enrichment

| Scraper | Source | Frequency | Data |
|---|---|---|---|
| `musicbrainz` | MusicBrainz API | Every 12h | ISRC codes, genre tags, artist/release metadata for entity resolution |

### Data Strategy — Chartmetric as the Backbone

Chartmetric ($350/month, paid entry tier: 2 req/sec = ~170K req/day) is the primary data source. Rather than building individual scrapers for TikTok, Apple Music, YouTube, and social platforms, Chartmetric aggregates them all. Direct Spotify, Shazam, and Genius APIs are enrichment layers that add granularity Chartmetric doesn't provide (audio analysis, city-level Shazam data, lyrics).

**What Chartmetric covers:** Spotify, Apple Music, TikTok, YouTube, Shazam, Instagram, Twitter metrics. Cross-platform entity resolution (unified artist/track IDs). Proprietary CM Score.

**What we add on top:** Deep audio analysis (timbre, structure, pitch), lyrics + themes, higher-frequency chart snapshots, Shazam city-level data.

---

## Entity Resolution

Chartmetric handles most cross-platform matching natively (unified artist/track IDs). For entities not in Chartmetric:

1. **ISRC match** — exact join when both sides have valid ISRCs
2. **Fuzzy name match** — RapidFuzz (token_sort_ratio > 85) on normalized artist+title strings
3. **Disambiguation queue** — unresolved matches flagged for manual review
4. **Learned blocklist** — known false positives excluded from auto-matching

**Phase 2+:** Embedding-based matching for transliterated names (K-pop, Arabic, Japanese artists).

---

## Genre Intelligence

850+ music genres organized hierarchically under 12 root categories (Pop, Rock, Electronic, Hip-Hop, R&B, Latin, Country, Jazz, Classical, African, Asian, Caribbean). Each genre maps bidirectionally to Spotify, Apple Music, MusicBrainz, and Chartmetric genre systems.

This enables:
- Genre-level trend analysis (Amapiano accelerating, Melodic Trap saturating, Brazilian Phonk emerging)
- Per-genre prediction models (what works in Electronic is different from what works in Country)
- Micro-genre targeting for music generation (not just "pop" but "bedroom pop" or "dark pop")

---

## Platform Weighting

Weights apply to signal types, not API sources. A Spotify metric from Chartmetric is weighted the same as from the Spotify API directly.

| Signal | Weight | Type | Why |
|---|---|---|---|
| **TikTok metrics** | 25% | Leading | Viral sounds precede streaming spikes by 1–3 weeks |
| **Spotify metrics** | 25% | Concurrent | Largest streaming platform. Chart velocity is the most reliable momentum indicator |
| **Shazam metrics** | 15% | Leading | Discovery intent. High Shazam-to-Spotify ratio = imminent breakout |
| **Apple Music metrics** | 15% | Concurrent | Premium audience, strong US signal |
| **Social velocity** | 10% | Composite | Cross-platform momentum (Instagram + YouTube + Spotify simultaneous growth) |
| **Radio** | 10% | Lagging | Validates mainstream crossover |

Weights are validated via Granger causality tests after 8 weeks of data collection. Re-evaluated quarterly.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/trending` | Current trending artists/tracks with composite scores, platform breakdowns, velocity, sparklines |
| `GET` | `/search` | Full-text search across all entities with trending data attached |
| `GET` | `/predictions` | Breakout predictions with confidence scores and explanatory signals |
| `GET` | `/genres` | Genre taxonomy (hierarchical tree or flat list) |
| `GET` | `/genres/{id}` | Single genre detail with platform mappings and trending stats |
| `GET` | `/backtesting/results` | Model validation: predicted vs actual accuracy over time |
| `POST` | `/backtesting/run` | Trigger a new backtesting evaluation |
| `GET` | `/health` | Service health with per-platform data freshness |

Authentication via `X-API-Key` header. Three tiers: Free (100 req/hr), Pro (1,000 req/hr), Admin (unlimited + write access).

---

## Technical Architecture

| Component | Technology | Role |
|---|---|---|
| **API** | Python (FastAPI), async | REST API serving trending, predictions, genres, backtesting |
| **Database** | PostgreSQL (Neon, serverless) | Persistent storage: entities, snapshots, predictions, backtest results |
| **Cache** | Redis (Railway) | Rate limiting, response caching (15min–24h TTL by endpoint) |
| **Task Queue** | Celery + Redis broker | Scraper orchestration on scheduled cycles |
| **ML** | LightGBM, scikit-learn (Phase 2); PyTorch LSTM, XGBoost (Phase 3) | Prediction models |
| **Entity Resolution** | RapidFuzz + ISRC matching + Chartmetric IDs | Cross-platform deduplication |
| **Frontend** | React + Vite + Recharts + Tailwind | Dashboard, Explore, Model Validation, API Playground |
| **Deployment** | Railway (compute) + Neon (database) | Production hosting |
| **Local Dev** | Docker Compose | PostgreSQL, Redis, FastAPI, Celery in containers |

---

## Phased Rollout

### Phase 1 — Data Foundation (Weeks 1–8)
**Goal:** Prove aggregation works. Build the data pipeline.

- Chartmetric as primary backbone + Spotify/Shazam enrichment
- Chart data scraping every 4–6 hours
- Entity resolution via Chartmetric IDs + ISRC + fuzzy matching
- Composite scoring with initial platform weights
- React dashboard for data validation
- Historical backfill: 2 years of daily chart data from Chartmetric

**Exit criteria:** API returns accurate, deduplicated trending data. Composite scores correlate with real-world breakout patterns.

### Phase 2 — Prediction + Song DNA (Weeks 9–20)
**Goal:** Train the prediction model. Add sonic and lyrical analysis.

- LightGBM breakout predictor trained on backfilled historical data
- Spotify Audio Analysis enrichment (timbre, structure, features)
- Genius lyrics enrichment (themes, vocabulary, structure)
- Chartmetric artist social stats (growth trajectories)
- Model Validation backtesting system
- Apple Music direct API, Radio airplay data

**Exit criteria:** Prediction model >60% precision at 50% recall on 7-day breakout. Song DNA profiles available for top trending tracks.

### Phase 3 — Full Autonomous Pipeline (Weeks 21–40)
**Goal:** Close the loop. Generate music, distribute it, market it, collect royalties. No humans.

**Generation:**
- Three-model ensemble (LightGBM + LSTM + XGBoost) with Ridge meta-learner
- Blueprint generation API: input a genre, get a complete song specification
- Prompt translation layer: Song DNA → Suno/Udio/SOUNDRAW prompts
- Suno API integration for automated song generation from blueprints
- Genre-timing model: what sonic characteristics are trending per micro-genre right now
- Full 850+ genre taxonomy with real-time per-genre trend scoring

**Distribution:**
- Revelator or LabelGrid API integration for automated DSP delivery
- Auto-generate metadata (ISRC, UPC, credits, genre tags) from Song DNA
- AI-generated cover art (DALL-E / Midjourney API)
- Scheduled release with optimal timing per genre

**Viral Marketing (TikTok + Social):**
- Auto-create TikTok teaser clips (15-sec hook extraction from generated song)
- Post to TikTok via TikTok Content Posting API (available for registered developers)
- Create AI artist profiles on Instagram, TikTok, YouTube
- Generate social content (behind-the-scenes AI narratives, lyric videos, visualizers)
- Schedule posts to maximize engagement windows per platform
- Monitor viral signals (sound adoption rate, UGC creation) and boost performing content
- Cross-platform cascade strategy: TikTok teaser (day -3) → full release (day 0) → YouTube visualizer (day +1)

**PRO Registration & Royalties:**
- Revelator API for rights management and royalty tracking
- TuneRegistry for PRO registration (automated via browser automation initially)
- SoundExchange registration for digital performance royalties

**Artist Identity:**
- Generate AI artist personas (name, visual identity, backstory, social presence)
- Each persona targets a specific genre niche
- Multiple personas across genres = diversified portfolio
- Personas build followings independently, creating compounding audience value

**Exit criteria:** System generates a song, distributes it to 150+ platforms, posts TikTok teasers, registers royalties, and monitors performance — all from a single "launch" command. First revenue collected from an AI-generated, AI-distributed, AI-marketed song.

---

## Success Metrics

### Phase 1
| Metric | Target |
|---|---|
| Data freshness | <6 hours stale |
| Entity match rate | >85% cross-platform |
| API uptime | >99% |
| Composite score correlation with chart movement | Positive Spearman rank correlation |

### Phase 2
| Metric | Target |
|---|---|
| 7-day breakout precision | >60% at 50% recall |
| Song DNA coverage | Audio features for >90% of top 200 tracks |
| Lyrics coverage | Themes extracted for >70% of top 200 tracks |
| Baseline improvement | >15% precision over naive persistence |

### Phase 3
| Metric | Target |
|---|---|
| Ensemble lift over single model | >10% precision improvement |
| Confidence calibration error | <0.05 mean absolute |
| Blueprint quality | Generated prompts produce songs matching target genre profile >80% of the time |
| Genre trend detection | Correctly identifies 3 of top 5 emerging genres per quarter |
| Songs generated per month | >50 across all genre niches |
| Distribution success rate | >95% of songs delivered to all target DSPs |
| TikTok teaser engagement | >1% avg engagement rate on posted clips |
| First revenue milestone | At least 1 song generating >$1/month in streaming revenue |
| Autonomous pipeline uptime | Full generate → distribute → market pipeline runs without human intervention for 30+ days |

---

## Operating Costs

### Phase 1
| Item | Monthly Cost |
|---|---|
| Chartmetric API (paid entry) | $350 |
| Shazam via RapidAPI | $10 |
| Spotify / MusicBrainz APIs | Free |
| Railway compute (API + Redis) | $20–$50 |
| Neon database | Free tier |
| **Total** | **~$380–$410/month** |

### Phase 2
| Item | Additional Cost |
|---|---|
| Apple Developer Program | $8/month amortized |
| Shazam upgrade to Pro | +$40 |
| Genius API | Free |
| Radio data (TBD) | $200–$2,000 |
| Increased compute for ML | +$30–$100 |
| **Total** | **~$660–$2,560/month** |

### Phase 3 (Full Autonomous Pipeline)
| Item | Additional Cost |
|---|---|
| Suno API (third-party wrapper) | ~$50–$100 |
| SOUNDRAW API | ~$20–$50 |
| Revelator or LabelGrid (distribution) | $120–$760/mo |
| TuneRegistry (PRO registration) | ~$20–$50 |
| TikTok Content Posting API | Free (developer access) |
| AI cover art (DALL-E API) | ~$10–$30 |
| GPU compute for ensemble training | +$50–$200 |
| **Total** | **~$1,030–$4,100/month** |

At scale, revenue from streaming royalties should exceed these costs. A single song averaging 10K streams/month generates ~$30-40/month. A portfolio of 500 songs = $15K-20K/month in passive revenue against ~$4K/month in infrastructure costs.

---

## Artist Portfolio Management

SoundPulse doesn't just create songs — it creates and manages a roster of AI artists. Each artist is a persistent persona with a genre niche, visual identity, social presence, and growing discography.

### The Artist Decision Model

When a new song blueprint is generated, the system must decide:

```
New blueprint: melodic trap, C# minor, 145 BPM, introspective/heartbreak

Option A: Assign to existing artist "VOIDBOY" (melodic trap, 12 songs,
          8K Spotify monthly listeners, growing TikTok)
          → Adds to discography, compounds existing audience

Option B: Create new artist "DREAMSCAR" (new persona)
          → Fresh brand, no audience yet, but no genre-clash risk
```

**Decision factors:**
- **Genre match**: Does the existing artist's established genre match the blueprint? (>80% feature overlap = assign)
- **Discography coherence**: Would this song feel natural alongside their existing tracks?
- **Audience momentum**: Is the existing artist's audience growing? (If stagnating, new persona may be better)
- **Market saturation**: How many of our artists are already in this niche? (Avoid cannibalizing our own catalog)
- **Release cadence**: Has the artist released recently? (Optimal spacing: 2-4 weeks between singles)

### Artist Lifecycle

```
1. BIRTH — New genre opportunity detected, no suitable existing artist
   → Generate persona: name, visual identity (AI art), bio, social profiles
   → Create accounts: Spotify for Artists, TikTok, Instagram, YouTube

2. GROWTH — First 5 songs, building initial audience
   → Aggressive TikTok marketing, playlist pitching
   → Monitor which songs get traction, feed back to blueprint model

3. MATURITY — 10+ songs, established audience
   → Consistent release cadence, audience expects new music
   → Cross-promote with other label artists
   → Explore sync licensing opportunities

4. EVOLUTION — Genre trends shift
   → Gradually evolve the artist's sound to match trends
   → Or: create a "side project" persona in the new genre

5. RETIREMENT — Genre saturated, audience declining
   → Reduce release frequency, let catalog generate passive revenue
   → Redirect resources to growing artists
```

### Separating Artist DNA from Song DNA

This is critical. The **Artist DNA** defines who the artist IS — it stays constant across all their songs. The **Song DNA** defines what each individual track sounds like — it varies per release. When generating a new song for an existing artist, we combine both:

**Artist DNA (persistent, defines the persona):**

| Feature | Description | Example |
|---|---|---|
| **Voice timbre** | The specific vocal texture, tone, breathiness | "Warm, slightly raspy male tenor with subtle reverb" |
| **Vocal style** | Delivery patterns, ad-libs, phrasing | "Melodic flow, occasional falsetto, whispered bridges" |
| **Accent / pronunciation** | Language character | "Slight Southern US drawl" or "London inflection" |
| **Autotune preference** | Processing style | "Heavy pitch correction, T-Pain style" or "Natural, no autotune" |
| **Genre home** | Primary genre(s) | "Melodic trap, emo rap" |
| **Lyrical voice** | Recurring themes, vocabulary level, perspective | "First person introspective, simple vocab, emotional vulnerability" |
| **Production signature** | Recurring sonic elements | "Always uses 808s, spacey reverb, minimal hi-hats" |
| **Visual identity** | Art style, color palette, aesthetic | "Dark, purple/black, abstract, moody" |
| **Persona narrative** | Backstory, personality, social voice | "Anonymous artist from nowhere, music speaks for itself" |

**Song DNA (varies per track, defined by the blueprint):**

| Feature | Description | Example |
|---|---|---|
| **Tempo** | BPM for this specific track | 145 BPM |
| **Key / mode** | Musical key | C# minor |
| **Energy / valence** | How intense and how happy/sad | 0.72 energy, 0.28 valence |
| **Song structure** | Arrangement for this track | Intro → Verse → Chorus → Verse → Bridge → Chorus → Outro |
| **Specific theme** | What THIS song is about | "Missing someone who left" |
| **Lyric content** | Actual lyrics for this track | Generated per song |
| **Featured elements** | Any one-off production choices | "Piano intro", "guitar solo bridge" |

**Generation prompt = Artist DNA + Song DNA:**

```
Suno prompt for artist "VOIDBOY", song "Neon Scars":

STYLE: Melodic trap, 145 BPM, C# minor, dark melancholic mood,
       808 bass, spacey reverb, minimal hi-hats,
       warm raspy male tenor vocals, heavy pitch correction,
       melodic flow with occasional falsetto

[Verse 1]
(Theme: missing someone who left. First person, emotionally vulnerable.
 Simple vocabulary, short lines.)

[Chorus]
(Catchy melodic hook. Same vocal signature as all VOIDBOY tracks.
 Whispered doubled vocals on the hook.)
```

This separation means:
- **Same artist, different songs** → swap the Song DNA, keep the Artist DNA
- **Suno "persona" feature** → maps directly to our Artist DNA (vocal model persistence)
- **Brand coherence** → every song from one artist sounds like THEM, even though the songs differ
- **A/B testing** → try the same Song DNA with different Artist DNAs to see which persona fits best

### Data Model for AI Artists

Each AI artist in the database tracks:

**Identity:**
- Name, visual identity (AI-generated profile images, cover art style, color palette)
- Bio / persona narrative
- Social accounts (TikTok, Instagram, YouTube handles)

**Artist DNA (frozen at creation, evolves slowly):**
- Voice profile (timbre descriptor, autotune level, delivery style, accent)
- Genre home (primary + adjacent genres)
- Production signature (recurring sonic elements)
- Lyrical voice (themes, vocabulary level, perspective, language)
- Suno/Udio persona ID (if the model supports persistent voice)

**Catalog:**
- Release history (songs, dates, Song DNA for each)
- Performance metrics per song (streams, saves, playlist adds, TikTok usage)
- Audience metrics (followers, growth rate, geographic distribution)
- Revenue attribution (royalties per song, per platform)

**Management:**
- Brand coherence score (feature variance across catalog — lower = more consistent)
- Release cadence (average days between releases)
- Growth trajectory (is audience expanding, stagnating, declining?)
- Portfolio role (growth artist, cash cow, experimental, retired)

---

## Data Source Feasibility Matrix

| Platform | Role | Cost | Rate Limits | What You Get | Risk |
|---|---|---|---|---|---|
| **Chartmetric** | Primary backbone | $350/mo | 2 req/sec (~170k/day) | Cross-platform metrics, social stats, entity resolution, CM Score | Low |
| **Spotify** | Enrichment | Free | ~180 req/min | Charts, search, audio features, audio analysis | Low |
| **Shazam** | Enrichment | $10–$50/mo | 500–10k req/mo | Discovery signals, city-level data | Low |
| **Genius** | Lyrics | Free | ~100 req/mo + scraping | Song lyrics, section structure | Low |
| **Apple Music** | Phase 2 | $99/yr | Generous | Charts, catalog data | Medium |
| **TikTok** | Via Chartmetric | Included | Included | Video counts, sound usage | Medium |
| **Radio** | Phase 2+ | $200–$2k/mo | Varies | Airplay spins, station adds | High |
| **MusicBrainz** | Metadata | Free | 1 req/sec | ISRCs, genre tags, release data | Low |

---

*SoundPulse turns fragmented music signals into actionable intelligence — and actionable intelligence into music.*
