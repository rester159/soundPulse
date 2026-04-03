# SoundPulse
## Music Intelligence API

**Product Requirements Document** — April 2026

*SoundPulse is a unified REST API that aggregates music trending data from major platforms, normalizes it into a single intelligence layer, and predicts which artists and genres are about to break out — before they do.*

---

## The Problem

Music trend data is fragmented across platforms that don't talk to each other. A track can be going viral on TikTok, climbing Shazam charts, and gaining Spotify playlist traction simultaneously — but no single source connects these signals. Labels, distributors, sync licensors, and playlist curators are forced to manually cross-reference multiple dashboards, each with different metrics, update frequencies, and data formats.

The result: by the time a trend is visible in any single platform's data, the window to act on it has often already closed.

---

## What SoundPulse Does

SoundPulse operates as a real-time intelligence layer on top of the fragmented music data ecosystem. It performs three core functions:

| Function | Description |
|---|---|
| **Aggregate** | Collects trending data from multiple platforms on a scheduled cycle. Deduplicates entities across platforms using ISRC codes, fuzzy name matching, and manual disambiguation queues. |
| **Normalize** | Converts incompatible platform metrics (Spotify streams, TikTok video counts, Shazam lookups) into a unified 0–100 composite score with a weighted formula that reflects each platform's predictive value. |
| **Predict** | A prediction engine forecasts which artists, tracks, and genres will trend at 7-day, 30-day, and 90-day horizons — with calibrated confidence scores and explainable signals. |

---

## Data Strategy — Chartmetric as the Backbone

Chartmetric is the primary data source for SoundPulse. Rather than building and maintaining individual scrapers for every platform — each with different APIs, auth methods, rate limits, and data formats — we use Chartmetric as a unified data backbone that already aggregates cross-platform signals from Spotify, Apple Music, TikTok, YouTube, Shazam, and more.

**Why this works:**
- Chartmetric already solves entity resolution across platforms (artist/track IDs are unified)
- Provides cross-platform metrics in a single API: Spotify streams, TikTok video counts, Apple Music chart positions, Shazam lookups, playlist tracking, social follower counts
- Proprietary artist scoring (CM Score) gives us a baseline to compare our own composite scores against
- $150/month gets us 1,000 req/day — enough for a 4–6 hour collection cycle across top trending entities

**What Chartmetric doesn't give us** (and where direct API access adds value):
- Real-time Spotify chart snapshots with higher granularity than Chartmetric's update frequency
- Shazam city-level data (Chartmetric covers country-level)
- MusicBrainz metadata for ISRC validation and genre enrichment
- Full control over data freshness — Chartmetric's data can lag by 12–24 hours on some metrics

**The architecture:** Chartmetric is the foundation layer. Direct platform APIs (Spotify, Shazam) are enrichment layers that fill gaps, add granularity, and provide independent signals for cross-validation.

---

## Phased Rollout

SoundPulse ships in three phases. Each phase is a usable product on its own — not a stub waiting for the next release.

### Phase 1 — MVP (Weeks 1–8)
**Goal:** Prove the aggregation and scoring model works using Chartmetric as the primary data backbone, enriched with direct Spotify and Shazam data.

- **Data sources:** Chartmetric (primary — cross-platform artist/track data, TikTok signals, playlist tracking), Spotify (direct — charts, search, audio features), Shazam (via RapidAPI — discovery signals), MusicBrainz (metadata enrichment, ISRC validation)
- **Endpoints:** `/trending`, `/search`, `/genres` (flat list, ~50 top-level genres)
- **Scoring:** Weighted composite using Chartmetric cross-platform data + direct Spotify/Shazam signals. Initial weights: Chartmetric aggregate 40%, Spotify direct 30%, Shazam 20%, cross-platform velocity 10%
- **Entity resolution:** Chartmetric handles most cross-platform matching natively. For entities not in Chartmetric: ISRC-based matching with RapidFuzz fallback. Unresolved entities flagged for manual review
- **Dashboard:** Read-only React dashboard showing top trending artists/tracks with sparklines
- **Infrastructure:** Docker Compose (PostgreSQL, Redis, FastAPI, Celery)

**Exit criteria:** API returns accurate, deduplicated trending data refreshed every 6 hours. Manual spot-checks confirm composite scores correlate with real-world breakout patterns over a 4-week observation period.

### Phase 2 — Direct Platform Enrichment + Prediction (Weeks 9–20)
**Goal:** Layer in direct platform APIs for higher-resolution signals, introduce the prediction engine once we have enough historical data from Phase 1.

- **New direct sources:** Apple Music (requires Developer Program enrollment, ~2 week approval), Radio airplay (evaluate: RadioWave API or MediaBase — requires pricing/access negotiation)
- **TikTok:** Chartmetric already provides TikTok video counts and sound usage data. Evaluate TikTok Research API for deeper signals (creator tier adoption rates) — approval timeline is 2–4 months, so start the application in Phase 1
- **Prediction engine:** Single-model baseline (LightGBM on tabular features) trained on 8+ weeks of historical data from Phase 1. Binary classification: "will this track/artist appear in the top 100 trending within N days?"
- **Endpoints:** `/predictions` (7-day horizon only), expanded `/genres` with hierarchy
- **Platform weights:** Refined based on correlation analysis of Phase 1 data. Chartmetric signals decomposed into per-platform components where possible

**Exit criteria:** Prediction model achieves >60% precision at 50% recall on 7-day breakout predictions, measured against a held-out test set. This must beat the naive baseline of "tracks currently trending will keep trending."

### Phase 3 — Full Intelligence Layer (Weeks 21–32)
**Goal:** Multi-model ensemble, full genre taxonomy, maximum platform coverage.

- **Prediction engine:** Three-model ensemble (LightGBM, LSTM with attention, XGBoost) with Ridge meta-learner. Isotonic regression for confidence calibration. Predictions at 7-day, 30-day, and 90-day horizons
- **Self-learning loop:** Daily comparison of predictions vs. outcomes. Automatic retraining triggered when accuracy degrades beyond defined thresholds
- **Genre taxonomy:** 850+ genres organized hierarchically under 12 root categories, with bidirectional mappings to Spotify, Apple Music, MusicBrainz, and Chartmetric genre systems
- **API tiers:** Free (100 req/hr), Pro (1,000 req/hr), Admin (unlimited + write access)

**Exit criteria:** Ensemble model outperforms Phase 2 single model by >10% precision. Confidence calibration verified: an 80% confidence prediction contains the actual value ~80% of the time across a 30-day evaluation window.

---

## Data Source Feasibility Matrix

| Platform | Role | Access Method | Cost | Rate Limits | What You Actually Get | Risk |
|---|---|---|---|---|---|---|
| **Chartmetric** | **Primary backbone** | Enterprise REST API | $350/month (free trial available) | Free trial: 1,000 req/day. Paid entry: 2 req/sec (~170k/day). Paid premium: 25 req/sec (~2.1M/day) | Cross-platform artist scores, Spotify/Apple Music/TikTok/YouTube metrics, playlist tracking, social follower counts, proprietary CM Score. **This is our single biggest data lever** — it solves most of the aggregation problem out of the box | Low — purpose-built for this use case |
| **Spotify** | Enrichment | Web API (public) | Free | ~180 req/min with client credentials | Top 200 charts (daily/weekly), search, artist metadata, track audio features. Higher-frequency chart snapshots than Chartmetric provides. **No** save rates, playlist addition events, or stream velocity per track | Low — stable API, well-documented |
| **Shazam** | Enrichment | RapidAPI | $10/month (Basic) | 500 req/month (Basic), 10k (Pro at $50/mo) | Top charts by country/city, track recognition counts. City-level granularity that Chartmetric lacks. Key for Shazam-to-Spotify ratio (leading breakout indicator) | Low — reliable third-party wrapper |
| **Apple Music** | Enrichment (Phase 2) | MusicKit / Apple Music API | $99/year (Developer Program) | Generous but requires JWT auth | Catalog search, charts, playlist data. No listen counts or save rates. Supplements Chartmetric's Apple Music data with direct chart access | Medium — onboarding takes 1-2 weeks |
| **TikTok** | Via Chartmetric (Phase 1), Direct (Phase 2+) | Chartmetric API / TikTok Research API | Included in Chartmetric / Free if approved | Chartmetric: included in daily quota. Direct: query-based | Chartmetric provides TikTok video counts and sound usage. Direct API adds deeper signals like creator tier adoption — **but** approval takes 2-4 months and is restricted to academic/research use | **Medium** — Chartmetric covers the basics; direct access is a nice-to-have for Phase 2+ |
| **Radio** | Enrichment (Phase 2+) | TBD (RadioWave, MediaBase, or Nielsen BDS) | $200–$2,000+/month | Varies | Airplay spins, station adds, audience reach | **High** — expensive, enterprise-only, data delivery may be batch (weekly), not real-time |
| **MusicBrainz** | Metadata | Open API | Free | 1 req/sec | ISRC codes, artist/release metadata, genre tags. Essential for entity resolution and genre enrichment | Low — open source, community-maintained |

---

## Entity Resolution

Chartmetric significantly reduces the entity resolution burden — it maintains its own unified artist and track IDs across platforms, so the cross-platform matching problem is largely pre-solved for entities in their database.

**What Chartmetric handles:** Matching artists/tracks across Spotify, Apple Music, TikTok, YouTube, Shazam, and social platforms. Their internal IDs serve as the canonical reference for any entity they track.

**What we still need to solve:**
- Matching Chartmetric entities to our internal IDs and to MusicBrainz metadata
- Handling entities that appear in Spotify/Shazam charts but aren't yet tracked by Chartmetric (brand-new artists, regional releases)
- Reconciling direct Spotify/Shazam data with Chartmetric's version of the same metrics (timestamps may differ, values may lag)

**Our approach for non-Chartmetric entities:**
1. **ISRC match** — exact join when both sides have valid ISRCs
2. **Fuzzy name match** — RapidFuzz (token_sort_ratio > 85) on normalized artist+title strings, with featuring artist extraction and reordering
3. **Disambiguation queue** — unresolved or low-confidence matches flagged for manual review via admin endpoint
4. **Learned blocklist** — known false positives (e.g., covers, remixes that share titles) stored and excluded from auto-matching

**Phase 2+:** Evaluate embedding-based matching (artist/track name embeddings via sentence transformers) for cases where fuzzy string matching fails on transliterated names (e.g., K-pop, Arabic, Japanese artists).

---

## The Core Insight — Platform Weighting

Not all platforms are equal as leading indicators. SoundPulse's scoring formula reflects this, but weights are **not hardcoded assumptions** — they are derived from correlation analysis once sufficient historical data exists.

Because Chartmetric is our data backbone, we decompose its cross-platform data into per-platform signals where possible. The weighting applies to the **signal type**, not the API source — a Spotify stream count sourced via Chartmetric is weighted the same as one from the Spotify API directly.

**Initial hypothesis (to be validated in Phase 2):**

| Signal | Hypothesized Weight | Signal Type | Source | Why It Matters |
|---|---|---|---|---|
| **TikTok metrics** | 25% | Leading | Chartmetric (Phase 1), Direct API (Phase 2+ if approved) | Viral sounds on TikTok precede streaming spikes by 1–3 weeks. Sound adoption velocity is a strong breakout signal |
| **Spotify metrics** | 25% | Concurrent | Chartmetric + Spotify API direct | Largest streaming platform globally. Chart position and velocity (rate of change in ranking) are the most reliable momentum indicators |
| **Shazam metrics** | 15% | Leading | Shazam via RapidAPI | Discovery intent signal. A high Shazam-to-Spotify ratio (people identifying a song but not yet streaming it) is a strong leading indicator of imminent breakout |
| **Apple Music metrics** | 15% | Concurrent | Chartmetric (Phase 1), Direct API (Phase 2+) | Premium audience behavior. Particularly strong signal in the US and among older demographics |
| **Social / cross-platform velocity** | 10% | Composite | Chartmetric (social follower growth, playlist adds) | Cross-platform momentum that doesn't fit neatly into one platform — e.g., simultaneous growth across Instagram, YouTube, and Spotify |
| **Radio** | 10% | Lagging | Phase 2+ (TBD source) | Validates mainstream crossover. A track hitting radio after digital traction confirms sustained momentum |

**Validation plan:** After 8 weeks of data collection, run Granger causality tests between platform-specific signals and actual breakout events (defined as: entering the Spotify Global Top 200 for the first time). Adjust weights based on observed predictive power. Re-evaluate quarterly.

---

## Prediction Engine

### Phase 2: Single Model Baseline

Before building an ensemble, we validate that prediction is feasible at all.

- **Model:** LightGBM on tabular features
- **Features:** Platform scores, score velocity (7-day rate of change), cross-platform ratios (e.g., Shazam lookups / Spotify streams), genre, days since first appearance
- **Target:** Binary — will this entity enter the top 100 trending within 7 days?
- **Training data:** Requires 8+ weeks of historical snapshots from Phase 1. Each snapshot becomes a labeled example (did this entity actually break out within 7 days of the snapshot?)
- **Baseline to beat:** Naive persistence ("currently trending tracks stay trending") — typically ~45% precision

### Phase 3: Three-Model Ensemble

Once the single model proves the concept:

- **LightGBM** — tabular features (platform scores, velocities, cross-platform ratios)
- **LSTM with attention** — sequential patterns in time series data (7-day score histories)
- **XGBoost** — hand-crafted interaction features between platforms (e.g., TikTok velocity * Shazam ratio)
- **Meta-learner:** Ridge regression combines the three models' outputs
- **Calibration:** Isotonic regression so that confidence scores are meaningful (80% confidence = ~80% actual hit rate)
- **Self-learning:** Daily comparison of predictions vs. actual outcomes. Automatic retraining when rolling 7-day precision drops >5% below the 30-day moving average

### Cold Start Strategy

The prediction engine cannot launch on day one. Here's how we handle the gap:

1. **Weeks 1–4:** No predictions. Collect data, build entity resolution, validate scoring
2. **Weeks 5–8:** Accumulate historical snapshots. Begin labeling ground truth (which entities actually broke out?)
3. **Weeks 9–12:** Train and evaluate Phase 2 single model. Ship `/predictions` endpoint with clear "beta" labeling and wide confidence intervals
4. **Weeks 13+:** Iterate on features, evaluate additional platforms, begin ensemble development if single model shows promise

---

## API Endpoints

| Method | Endpoint | Phase | Description |
|---|---|---|---|
| `GET` | `/trending` | 1 | Current trending artists/tracks with composite scores, per-platform breakdowns, velocity, and 7-day sparkline. Filterable by genre, platform, time range |
| `GET` | `/search` | 1 | Full-text search across all artists and tracks with latest trending data attached |
| `GET` | `/genres` | 1 | Genre taxonomy (flat list in Phase 1, hierarchical tree in Phase 2+). Includes cross-platform mappings |
| `GET` | `/genres/{id}` | 2 | Deep detail on a single genre: platform mappings, audio profile, related genres, trending stats |
| `GET` | `/predictions` | 2 | Breakout predictions with confidence scores, confidence intervals, and top 3 explanatory signals. 7-day horizon in Phase 2; 30-day and 90-day in Phase 3 |
| `GET` | `/health` | 1 | Service health check with data freshness timestamps per platform |

Authentication is via API key in the `X-API-Key` header. Tiered rate limiting ships in Phase 3; Phase 1-2 use a single admin key.

---

## Upstream API Quota Management

On the free trial, Chartmetric limits to 1,000 req/day — tight but workable for initial development. Paid entry tier (2 req/sec, ~170k/day) removes this as a constraint entirely. Pricing is contact-sales, not published.

| Platform | Quota | Collection Strategy |
|---|---|---|
| **Chartmetric** (primary) | Free trial: 1,000 req/day. Paid entry: 2 req/sec (~170k/day) | **Free trial phase:** Budget ~40 req/hour. Prioritize top trending artists/tracks, cache aggressively. **Paid phase:** Quota is a non-issue — collect broadly across all tracked entities on a 4–6 hour cycle |
| **Spotify** (enrichment) | ~180 req/min (client credentials) | Batch chart pulls every 6 hours. Cache search results for 24 hours. Used to cross-validate Chartmetric data and get higher-frequency chart snapshots |
| **Shazam (RapidAPI)** | 500 req/month (Basic) | Pull top charts for 5 key markets only. Upgrade to Pro ($50/mo) if more granularity needed. Primary value is the Shazam-to-Spotify ratio signal |
| **Apple Music** (Phase 2) | Generous (no published hard limit) | Standard 6-hour cycle. Monitor for 429 responses |
| **MusicBrainz** | 1 req/sec | Metadata lookups are bursty during entity resolution. Implement token bucket rate limiter |

**Fallback cascade:** If an API returns errors or hits rate limits:
1. Retry with exponential backoff (max 3 retries)
2. If an enrichment source fails, Chartmetric data covers the gap (it tracks the same platforms)
3. If Chartmetric itself fails, use cached data (mark staleness in API response metadata)
4. Never serve stale data without flagging it — consumers must know the freshness of what they're getting

---

## Success Metrics

SoundPulse must be measured against concrete benchmarks, not vibes.

### Phase 1 Metrics
| Metric | Target | How Measured |
|---|---|---|
| Data freshness | <6 hours stale | Timestamp diff between last scrape and current time |
| Entity match rate | >85% of tracks matched across Chartmetric + Spotify + Shazam | % of entities with confirmed cross-platform match (Chartmetric IDs provide the baseline) |
| False match rate | <5% | Manual audit of 100 random matches weekly |
| API uptime | >99% | Health check monitoring |
| Composite score correlation | Positive correlation with actual chart movement | Spearman rank correlation between SoundPulse score and Spotify chart position changes over 7-day windows |

### Phase 2 Metrics
| Metric | Target | How Measured |
|---|---|---|
| 7-day breakout precision | >60% at 50% recall | Precision-recall on held-out test set, evaluated weekly |
| Baseline improvement | >15% precision over naive persistence | Side-by-side comparison |
| Prediction coverage | >80% of actual breakouts were in our candidate set | Recall on breakout events |

### Phase 3 Metrics
| Metric | Target | How Measured |
|---|---|---|
| Ensemble lift over single model | >10% precision improvement | A/B evaluation on same time period |
| Confidence calibration | Mean absolute calibration error <0.05 | Reliability diagram across confidence buckets |
| 30-day prediction precision | >50% at 40% recall | Weekly evaluation |
| Genre trend detection | Correctly identifies 3 of top 5 emerging genres per quarter | Quarterly manual evaluation against industry reports |

---

## Who This Is For

- Record labels and A&R teams identifying emerging artists before competitors
- Playlist curators sourcing tracks with validated cross-platform momentum
- Sync licensing companies matching trending sounds to advertising briefs
- Music distributors advising independent artists on release timing
- Investment analysts tracking genre-level shifts in the music market
- Media companies building data-driven editorial around music trends

---

## Technical Architecture

- **API:** Python (FastAPI), async throughout
- **Database:** PostgreSQL (via SQLAlchemy async + Alembic migrations)
- **Cache / Rate Limiting:** Redis
- **Task Queue:** Celery with Redis broker (scraper orchestration on 4–6 hour cycles)
- **ML:** LightGBM, scikit-learn (Phase 2). PyTorch LSTM, XGBoost added in Phase 3
- **Entity Resolution:** RapidFuzz + ISRC matching, with manual disambiguation queue
- **Frontend:** React + Vite testing dashboard (not a production UI — internal tool for validating data quality)
- **Deployment:** Docker Compose (local development), with path to container orchestration for production

---

## Operating Costs

### Phase 1 (MVP)
| Item | Monthly Cost |
|---|---|
| Chartmetric API (paid entry tier) | $350 |
| Shazam via RapidAPI (Basic) | $10 |
| Spotify API | Free |
| MusicBrainz API | Free |
| **Compute (Docker on a VPS)** | **$20–$50** |
| **Total** | **~$380–$410/month** |

### Phase 2 (Expanded)
| Item | Monthly Cost |
|---|---|
| Phase 1 costs | $380–$410 |
| Apple Developer Program | $8 (amortized) |
| Shazam upgrade to Pro | +$40 |
| Radio data (TBD) | $200–$2,000 |
| Increased compute (ML training) | +$30–$100 |
| **Total** | **~$660–$2,560/month** |

Note: Chartmetric at $350/month is the most cost-effective decision in the stack — it replaces the need to build and maintain individual scrapers for TikTok, Apple Music, YouTube, and social platforms. The free trial (1,000 req/day) is sufficient for development and validation. These are infrastructure and API costs only. Engineering time is the dominant cost and is not included here.

---

*SoundPulse turns fragmented music signals into actionable intelligence — one validated phase at a time.*
