# SoundPulse
## The AI Brain of a Virtual Record Label

**Product Requirements Document** — April 2026

*SoundPulse analyzes what makes music succeed, generates blueprints for new songs that will succeed, and feeds those blueprints directly to AI music generation models. It turns fragmented music signals into manufactured hits.*

---

## The Vision

SoundPulse is not a trend tracker. It is the intelligence engine behind a virtual record label — a system that:

1. **Analyzes** what sonic, cultural, and release characteristics are driving success in any given micro-genre at any given moment
2. **Generates blueprints** — specific, reproducible descriptions of what a new song should sound like, what it should be about, and how it should be structured
3. **Feeds those blueprints to AI music generation models** (Suno, Udio, MusicGen) to produce the actual music
4. **Predicts and optimizes** the release strategy — when to drop, which platforms first, what playlists to target

The output of SoundPulse is not a dashboard. It is the input to a music factory.

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
│ 4. OPTIMIZE — When and how to release?               │
│    - Optimal release day/time for this genre         │
│    - Platform sequencing (TikTok teaser → full drop) │
│    - Playlist targeting strategy                     │
│    - Predicted 30/60/90 day growth trajectory        │
│    - A/B test multiple generated versions            │
└─────────────────────────────────────────────────────┘
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

### Pipeline Recommendation

1. **Suno** for full songs with vocals (richest control over lyrics, structure, vocal style)
2. **SOUNDRAW** for programmatic batch generation (explicit parameter API, royalty-free)
3. **MusicGen** for self-hosted instrumental generation (open source, melody conditioning)
4. **Stable Audio** for sound design, intros, atmospheric layers (max 47s clips)

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

### Phase 3 — Blueprint Generation + Music Gen Integration (Weeks 21–32)
**Goal:** Generate actionable blueprints. Connect to music generation models.

- Three-model ensemble (LightGBM + LSTM + XGBoost) with Ridge meta-learner
- Blueprint generation API: input a genre, get a complete song specification
- Prompt translation layer: Song DNA → Suno/Udio/SOUNDRAW prompts
- Genre-timing model: what sonic characteristics are trending per micro-genre right now
- Cross-platform cascade model: predict the TikTok → Shazam → Spotify timing
- Full 850+ genre taxonomy with real-time per-genre trend scoring

**Exit criteria:** System generates prompts that produce songs with characteristics matching current genre trends. Blueprint scorer predicts success with >50% precision.

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

### Phase 3
| Item | Additional Cost |
|---|---|
| Suno API (third-party wrapper) | ~$50–$100 |
| SOUNDRAW API | ~$20–$50 |
| GPU compute for ensemble training | +$50–$200 |
| **Total** | **~$780–$2,910/month** |

These are infrastructure and API costs only. Chartmetric at $350/month is the most cost-effective decision in the stack — it replaces building and maintaining individual scrapers for 6+ platforms.

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
