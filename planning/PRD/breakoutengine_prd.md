# Breakout Analysis Engine — Technical Design

## 1. System Overview

The engine transforms SoundPulse from "what genres are trending" to "what specific sonic + lyrical formula will produce a hit in this genre right now, and why." It has 6 layers, each building on the last:

```
┌─────────────────────────────────────────────────────────────┐
│                    USER-FACING OUTPUT                        │
│  "Make a 125 BPM minor-key country song about resilience    │
│   with talk-singing verses — this formula has a 73%          │
│   predicted breakout probability based on 12 recent hits"   │
└───────────────────────────┬─────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
   ┌──────────┐     ┌──────────────┐    ┌──────────┐
   │ Layer 5  │     │   Layer 6    │    │ Layer 3  │
   │  Smart   │◄────│ ML Hit       │    │ Lyrical  │
   │  Prompt  │     │ Predictor    │    │ Analysis │
   │  (LLM)   │     │ (XGBoost)   │    │  (LLM)   │
   └────┬─────┘     └──────┬───────┘    └────┬─────┘
        │                  │                  │
   ┌────▼──────────────────▼──────────────────▼────┐
   │              Layer 4: Gap Finder               │
   │         (clustering + density analysis)        │
   └────────────────────┬──────────────────────────┘
                        │
   ┌────────────────────▼──────────────────────────┐
   │           Layer 2: Feature Delta               │
   │    (breakout features vs genre baseline)       │
   └────────────────────┬──────────────────────────┘
                        │
   ┌────────────────────▼──────────────────────────┐
   │          Layer 1: Breakout Detection           │
   │     (statistical threshold on velocity /       │
   │      composite vs genre peers)                 │
   └───────────────────────────────────────────────┘
```

---

## 2. Layer 1 — Breakout Detection

**Purpose:** Flag tracks that significantly outperform their genre peers. These are the signal — everything downstream learns from them.

**Definition of "breakout":** A track is a breakout if its peak composite_score OR velocity exceeds **2× the median** of its genre cohort within the same 14-day window. This captures both "steady climbers" (high composite) and "sudden spikes" (high velocity).

### Data model

```sql
-- New table: breakout_events
CREATE TABLE breakout_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    track_id        UUID NOT NULL REFERENCES tracks(id),
    genre_id        VARCHAR(100) NOT NULL,        -- taxonomy genre (e.g., "country.pop")

    -- Detection metrics
    detection_date  DATE NOT NULL,                -- when the breakout was detected
    window_start    DATE NOT NULL,                -- 14-day analysis window start
    window_end      DATE NOT NULL,

    -- Track's performance
    peak_composite  FLOAT NOT NULL,               -- track's max composite_score in window
    peak_velocity   FLOAT NOT NULL,               -- track's max velocity in window
    avg_rank        FLOAT,                        -- track's average rank across platforms
    platform_count  INT,                          -- how many platforms charted it

    -- Genre baseline (for this window)
    genre_median_composite  FLOAT NOT NULL,
    genre_median_velocity   FLOAT NOT NULL,
    genre_track_count       INT NOT NULL,         -- how many tracks in the genre this window

    -- Derived
    composite_ratio FLOAT NOT NULL,               -- peak_composite / genre_median_composite
    velocity_ratio  FLOAT NOT NULL,               -- peak_velocity / genre_median_velocity
    breakout_score  FLOAT NOT NULL,               -- combined signal (see formula below)

    -- Audio features at time of breakout (snapshot from tracks.audio_features)
    audio_features  JSON,

    -- Lifecycle
    resolved_at     TIMESTAMP WITH TIME ZONE,     -- when we can measure the outcome (30d later)
    outcome_score   FLOAT,                        -- actual composite_score 30d post-breakout
    outcome_label   VARCHAR(20),                  -- 'hit', 'moderate', 'fizzle' (for ML training)

    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_breakout_genre_date ON breakout_events(genre_id, detection_date DESC);
CREATE INDEX idx_breakout_track ON breakout_events(track_id);
CREATE INDEX idx_breakout_unresolved ON breakout_events(resolved_at) WHERE resolved_at IS NULL;
```

### Breakout score formula

```python
composite_ratio = track_peak_composite / genre_median_composite
velocity_ratio  = track_peak_velocity / max(genre_median_velocity, 0.1)  # floor to avoid /0
platform_bonus  = 0.1 * (platform_count - 1)  # multi-platform = stronger signal

breakout_score = (
    0.5 * min(composite_ratio / 3.0, 1.0) +    # caps at 3x median
    0.3 * min(velocity_ratio / 5.0, 1.0) +      # caps at 5x median
    0.2 * platform_bonus
)
# Threshold: breakout_score >= 0.4 = flagged as breakout
```

### Scheduled sweep

Runs every 6 hours (alongside composite sweep). For each genre with ≥5 tracks in the last 14 days:
1. Compute genre median composite + velocity
2. Find tracks exceeding 2× median on either axis
3. Write `breakout_events` row with full context
4. After 30 days, resolve the outcome: check if the track sustained (hit), faded (moderate), or died (fizzle)

---

## 3. Layer 2 — Feature Delta Analysis

**Purpose:** For each genre, compare breakout tracks against the genre baseline to find **what's different about hits**. This is the "what's winning" intelligence.

### Computation

```python
@dataclass
class GenreFeatureDelta:
    genre_id: str
    window: tuple[date, date]
    sample_size_breakouts: int
    sample_size_baseline: int

    # For each audio feature: breakout_avg - baseline_avg
    deltas: dict[str, float]   # {"tempo": +12.5, "energy": +0.15, "valence": -0.08, ...}

    # Statistical significance (p-value from Welch's t-test)
    significance: dict[str, float]  # {"tempo": 0.003, "energy": 0.02, ...}

    # Human-readable insight
    top_differentiators: list[str]  # ["15 BPM faster than genre avg", "minor key 3x more common"]
```

### Algorithm

```python
async def compute_feature_deltas(db, genre_id, window_days=30):
    # 1. Get all tracks in this genre in the window
    baseline_features = await get_genre_audio_features(db, genre_id, window_days)

    # 2. Get breakout tracks only (from breakout_events)
    breakout_features = await get_breakout_audio_features(db, genre_id, window_days)

    # 3. For each feature, compute:
    deltas = {}
    significance = {}
    for feature in AUDIO_FEATURE_KEYS:
        baseline_vals = [t[feature] for t in baseline_features if t.get(feature) is not None]
        breakout_vals = [t[feature] for t in breakout_features if t.get(feature) is not None]

        if len(baseline_vals) >= 5 and len(breakout_vals) >= 3:
            deltas[feature] = mean(breakout_vals) - mean(baseline_vals)
            _, p_value = scipy.stats.ttest_ind(breakout_vals, baseline_vals, equal_var=False)
            significance[feature] = p_value

    # 4. Rank by significance — the features with lowest p-value
    #    are the strongest differentiators
    top = sorted(
        [(f, deltas[f], significance[f]) for f in deltas if significance[f] < 0.1],
        key=lambda x: x[2]  # sort by p-value ascending
    )

    return GenreFeatureDelta(
        genre_id=genre_id,
        deltas=deltas,
        significance=significance,
        top_differentiators=_format_differentiators(top),
        ...
    )
```

### Storage

```sql
-- Cached per genre, refreshed daily
CREATE TABLE genre_feature_deltas (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    genre_id        VARCHAR(100) NOT NULL,
    window_start    DATE NOT NULL,
    window_end      DATE NOT NULL,
    breakout_count  INT NOT NULL,
    baseline_count  INT NOT NULL,
    deltas_json     JSON NOT NULL,      -- {"tempo": 12.5, "energy": 0.15, ...}
    significance_json JSON NOT NULL,    -- {"tempo": 0.003, ...}
    top_differentiators TEXT[],         -- human-readable list
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(genre_id, window_end)
);
```

---

## 4. Layer 3 — Lyrical Analysis (LLM-powered)

**Purpose:** Extract thematic patterns from breakout lyrics vs baseline lyrics. Requires Genius API.

### Pipeline

```
1. Enable genius_lyrics scraper → pulls lyrics for tracks with Genius matches
2. For each genre with ≥5 breakout tracks that have lyrics:
   a. Collect breakout lyrics (top 10 by breakout_score)
   b. Collect baseline lyrics (random 20 non-breakout tracks in same genre)
   c. Send both sets to LLM with structured prompt
   d. Cache the analysis
```

### LLM prompt (via llm_client.py)

```python
LYRICAL_ANALYSIS_PROMPT = """
You are a music industry A&R analyst. Analyze these two sets of lyrics from the {genre} genre.

SET A — BREAKOUT HITS (tracks that significantly outperformed their peers):
{breakout_lyrics_truncated}

SET B — BASELINE (typical tracks in this genre that didn't break out):
{baseline_lyrics_truncated}

Analyze the differences and return ONLY this JSON structure:
{
  "breakout_themes": ["theme1", "theme2", ...],       // 3-5 themes dominant in breakouts
  "baseline_themes": ["theme1", "theme2", ...],       // 3-5 themes dominant in baseline
  "underserved_themes": ["theme1", "theme2", ...],    // themes present in breakouts but RARE in baseline
  "overserved_themes": ["theme1", "theme2", ...],     // themes saturated in baseline but ABSENT from breakouts
  "structural_patterns": {
    "avg_verse_lines": int,
    "chorus_repetition": "high|medium|low",
    "talk_singing": boolean,
    "narrative_vs_abstract": "narrative|abstract|mixed"
  },
  "vocabulary_tone": "raw|polished|conversational|poetic",
  "key_insight": "one sentence: the single most actionable lyrical difference"
}
"""
```

### Storage

```sql
CREATE TABLE genre_lyrical_analysis (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    genre_id        VARCHAR(100) NOT NULL,
    window_end      DATE NOT NULL,
    breakout_count  INT NOT NULL,
    baseline_count  INT NOT NULL,
    analysis_json   JSON NOT NULL,       -- the LLM's structured output
    llm_call_id     UUID REFERENCES llm_calls(id),  -- links to cost/token tracking
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(genre_id, window_end)
);
```

### Cost control

- Run weekly (not daily) — lyrics don't change that fast
- Truncate lyrics to ~500 words each (enough for theme detection)
- Use the cheapest model that produces structured JSON (Groq llama-3.3-70b at $0.59/M input)
- ~10 genres × ~3000 tokens/call = ~30K tokens/week ≈ $0.02/week

---

## 5. Layer 4 — Gap Finder

**Purpose:** Identify underserved sonic + thematic spaces within a genre. "Where is there demand but no supply?"

### Approach: Feature-space density analysis

```python
async def find_gaps(db, genre_id):
    # 1. Get ALL tracks in genre with audio features
    all_tracks = await get_genre_tracks_with_features(db, genre_id)

    # 2. Get breakout tracks only
    breakouts = await get_breakout_tracks_with_features(db, genre_id)

    # 3. Build feature vectors (normalized)
    feature_keys = ['tempo', 'energy', 'danceability', 'valence', 'acousticness', 'loudness']

    # Normalize to [0, 1] using genre min/max
    all_vectors = normalize(extract_vectors(all_tracks, feature_keys))
    breakout_vectors = normalize(extract_vectors(breakouts, feature_keys))

    # 4. Cluster all tracks into 8-12 zones using K-means
    kmeans = KMeans(n_clusters=min(10, len(all_tracks) // 5))
    kmeans.fit(all_vectors)

    # 5. For each cluster, compute:
    gaps = []
    for cluster_id in range(kmeans.n_clusters):
        cluster_mask = kmeans.labels_ == cluster_id
        cluster_size = cluster_mask.sum()

        # How many breakouts landed in this cluster?
        breakout_labels = kmeans.predict(breakout_vectors)
        breakout_in_cluster = (breakout_labels == cluster_id).sum()

        # Breakout density = breakouts / total tracks in cluster
        breakout_density = breakout_in_cluster / max(cluster_size, 1)

        # Overall density = tracks in cluster / total tracks
        supply_density = cluster_size / len(all_tracks)

        # GAP = high breakout density + low supply density
        # "Breakouts happen here, but few people are making music here"
        gap_score = breakout_density / max(supply_density, 0.01)

        # Describe the cluster center in human terms
        center = kmeans.cluster_centers_[cluster_id]
        description = describe_cluster(center, feature_keys)

        gaps.append({
            "cluster_id": cluster_id,
            "gap_score": gap_score,
            "breakout_density": breakout_density,
            "supply_density": supply_density,
            "total_tracks": int(cluster_size),
            "breakout_tracks": int(breakout_in_cluster),
            "sonic_center": dict(zip(feature_keys, center.tolist())),
            "description": description,  # e.g., "high-energy, fast, dark, acoustic"
        })

    # Sort by gap_score — highest = biggest opportunity
    gaps.sort(key=lambda x: x["gap_score"], reverse=True)
    return gaps
```

### Example output

```json
{
  "genre": "country",
  "gaps": [
    {
      "gap_score": 4.2,
      "description": "fast (125+ BPM), minor key, high energy, low acousticness",
      "breakout_tracks": 3,
      "total_tracks": 4,
      "insight": "Breakouts happen 4.2x more often in this zone than the genre average, but only 4 tracks exist here. Massive untapped opportunity."
    },
    {
      "gap_score": 0.3,
      "description": "slow (90 BPM), major key, mid energy, high acousticness",
      "breakout_tracks": 0,
      "total_tracks": 25,
      "insight": "Saturated: 25 tracks competing, zero breakouts. Avoid."
    }
  ]
}
```

---

## 6. Layer 5 — Smart Prompt Generation (LLM)

**Purpose:** Synthesize layers 1-4 into a production-ready prompt for Suno/Udio.

### Input to the LLM

```python
SMART_PROMPT_SYSTEM = """
You are a hit songwriter's AI collaborator at a virtual record label.
Generate a complete song creation prompt for {model} based on the
competitive intelligence below. The goal is NOT to copy what exists —
it's to fill the GAP that the data shows is underserved but winning.

TARGET GENRE: {genre}
BREAKOUT SONIC PROFILE (what's winning):
{feature_deltas}

TOP GAP (underserved zone with high breakout rate):
{gap_description}

LYRICAL INTELLIGENCE:
- Breakout themes: {breakout_themes}
- Underserved themes: {underserved_themes}  ← TARGET THESE
- Overserved themes: {overserved_themes}    ← AVOID THESE
- Winning tone: {vocabulary_tone}
- Structure: {structural_patterns}

PREDICTED HIT PROBABILITY: {ml_prediction}%

Generate a {model}-formatted prompt that:
1. Targets the gap zone sonically (tempo, key, energy from the gap center)
2. Uses an underserved theme (not what everyone else is writing about)
3. Follows the structural patterns of breakout hits
4. Is specific enough that {model} produces something distinctive
"""
```

### Output shape

```json
{
  "prompt": "STYLE: modern country, 128 BPM, E minor, high energy...\n\nLYRICS:\n[Verse 1]...",
  "rationale": {
    "sonic_targeting": "128 BPM in minor key — 4.2x breakout zone, only 4 competing tracks",
    "theme_targeting": "Resilience + small-town defiance — trending in breakouts, underserved in baseline",
    "structural_choice": "Talk-singing verses (3 of 5 recent breakouts used this), melodic chorus",
    "differentiation": "Combining acoustic guitar texture with trap hi-hats — no current tracks in this genre do this"
  },
  "predicted_breakout_probability": 0.73,
  "confidence": "medium",
  "based_on": {
    "breakout_tracks_analyzed": 12,
    "baseline_tracks_analyzed": 45,
    "lyrics_analyzed": 8,
    "audio_features_coverage": "89%"
  }
}
```

---

## 7. Layer 6 — ML Hit Predictor

**Purpose:** Given a set of audio features + genre + thematic signals, predict the probability that a track with those characteristics will break out.

### Training data

Each row in `breakout_events` becomes a training example once resolved:

```python
features = {
    # Audio features (13 fields)
    "tempo": 128.0,
    "energy": 0.85,
    "danceability": 0.72,
    "valence": 0.45,
    "acousticness": 0.08,
    "instrumentalness": 0.0,
    "liveness": 0.15,
    "speechiness": 0.04,
    "loudness": -5.2,
    "key": 4,               # E
    "mode": 0,               # minor
    "duration_ms": 195000,
    "time_signature": 4,

    # Genre context (relative to genre baseline)
    "tempo_delta": +15.0,          # how far from genre median
    "energy_delta": +0.12,
    "valence_delta": -0.08,
    "danceability_delta": +0.05,

    # Competitive context
    "genre_track_count": 45,       # how crowded
    "genre_breakout_rate": 0.07,   # historical hit rate
    "gap_score": 3.8,              # how underserved this zone is

    # Platform signals
    "platform_count_at_detection": 3,
    "initial_velocity": 2.5,
    "initial_composite": 65.0,

    # Temporal
    "day_of_week": 5,              # release day
    "month": 4,
    "is_summer": 0,
}

label = outcome_label  # 'hit' (1), 'moderate' (0.5), 'fizzle' (0)
```

### Model architecture

```python
# XGBoost gradient-boosted trees — best for tabular data with this
# feature count. No need for neural nets.

import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit

model = xgb.XGBRegressor(
    n_estimators=200,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.1,       # L1 regularization
    reg_lambda=1.0,      # L2 regularization
    objective='reg:squarederror',
)

# Time-series split to prevent future data leaking into training
tscv = TimeSeriesSplit(n_splits=5)
for train_idx, val_idx in tscv.split(X):
    model.fit(
        X[train_idx], y[train_idx],
        eval_set=[(X[val_idx], y[val_idx])],
        early_stopping_rounds=20,
        verbose=False,
    )
```

### Training pipeline

```
1. Breakout detection sweep runs daily → writes breakout_events
2. After 30 days, resolve each event:
   - outcome_score = current composite_score of the track
   - outcome_label = 'hit' if outcome > 2x genre median,
                     'moderate' if > 1x, 'fizzle' otherwise
3. Weekly model retraining:
   - Query all resolved breakout_events (need ≥200 for meaningful training)
   - Extract feature matrix
   - Train XGBoost with time-series cross-validation
   - Evaluate: AUC-ROC, precision@10, recall
   - If improved over previous model → save to models/hit_predictor.json
   - Log training run to model_runs table
4. Serving:
   - Blueprint v2 loads the model
   - For each gap zone, predict breakout probability
   - Include in the smart prompt output
```

### Cold start problem

We need **≥200 resolved breakout events** to train meaningfully. With ~50 breakout events per month (estimated: 6400 tracks × ~5% breakout rate ÷ 30 days ÷ ~20 genres), we'd need **~4 months** of data.

**Mitigation:**
- Start the breakout detection sweep immediately (it writes rows even before the ML model exists)
- Use simpler heuristics for hit prediction in the interim (gap_score × breakout_rate as a proxy)
- The ML model is a future upgrade, not a launch blocker

### Model storage

```sql
CREATE TABLE model_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_type      VARCHAR(50) NOT NULL,          -- 'hit_predictor'
    version         INT NOT NULL,
    trained_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    training_rows   INT NOT NULL,
    feature_count   INT NOT NULL,
    metrics_json    JSON NOT NULL,                  -- {"auc_roc": 0.78, "precision_10": 0.65, ...}
    model_path      VARCHAR(500) NOT NULL,          -- "models/hit_predictor_v3.json"
    is_active       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## 8. Opportunity Score v2

Replaces the current naive formula with breakout-informed scoring:

```python
def opportunity_score_v2(genre_stats):
    # Breakout rate: what % of tracks in this genre became breakouts?
    breakout_rate = genre_stats.breakout_count / max(genre_stats.track_count, 1)

    # Momentum trend: is the genre accelerating or decelerating?
    momentum = genre_stats.velocity_this_week / max(genre_stats.velocity_last_month, 0.1)
    momentum_score = sigmoid_normalize(momentum, center=1.0, steepness=2.0)

    # Demand signal: are audiences growing? (from artist follower growth)
    demand_growth = genre_stats.avg_artist_follower_growth_rate
    demand_score = sigmoid_normalize(demand_growth, center=0.0, steepness=5.0)

    # Competitive gap: how many unique artists vs tracks?
    artist_concentration = genre_stats.unique_artists / max(genre_stats.track_count, 1)
    # Low concentration = dominated by few artists = hard to break in
    # High concentration = many artists = open field
    competition_score = artist_concentration

    # Max gap score across clusters (from Layer 4)
    best_gap = genre_stats.max_gap_score
    gap_score = min(best_gap / 5.0, 1.0)

    # Combined
    opportunity = (
        0.25 * breakout_rate * 10 +     # scale to [0, 1ish]
        0.25 * momentum_score +
        0.15 * demand_score +
        0.15 * competition_score +
        0.20 * gap_score
    )

    confidence = min(1.0, genre_stats.track_count / 20)  # need ≥20 tracks to be confident

    return opportunity, confidence
```

---

## 9. Implementation Phases

| Phase | Scope | Depends on | Time est. | Data needed |
|---|---|---|---|---|
| **P1: Breakout detection** | breakout_events table + 6h sweep | Existing data | ~4 hrs | Current snapshots (23k+) |
| **P2: Feature delta** | genre_feature_deltas table + daily computation | P1 | ~3 hrs | P1 + audio features (growing) |
| **P3: Opportunity Score v2** | Replace current formula | P1 + P2 | ~2 hrs | P1 output |
| **P4: Gap finder** | K-means clustering + gap scoring | P2 | ~4 hrs | Audio features on ≥50% of tracks |
| **P5: Genius lyrics pipeline** | Enable scraper + store lyrics | GENIUS_API_KEY env var | ~3 hrs | Genius API access |
| **P6: Lyrical analysis** | LLM-powered theme extraction | P1 + P5 | ~4 hrs | Lyrics for ≥5 breakouts/genre |
| **P7: Smart prompt v2** | LLM prompt using all layers | P2 + P4 + P6 | ~3 hrs | All prior layers |
| **P8: ML hit predictor** | XGBoost training + serving | P1 (≥200 resolved events) | ~6 hrs | ~4 months of breakout data |
| **P9: Blueprint v2 API** | Wire everything into /blueprint/generate | All of above | ~4 hrs | All prior layers |

**Total: ~33 hours of engineering, shipped incrementally.**

P1-P3 can ship in the first week and immediately improve the product. P4-P7 ship in week 2-3. P8 starts collecting data from day 1 but doesn't produce predictions for ~4 months.

---

## 10. What this changes for the user

**Before (current):**
```
"STYLE: country, 109 BPM, A major, upbeat positive"
```

**After (with breakout engine):**
```
"STYLE: modern country, 128 BPM, E minor, high energy, raw/confessional tone

The data shows: fast minor-key country with talk-singing verses
is breaking out 4.2x more than the genre average, but only 4 tracks
occupy this space. 3 of the last 5 country breakouts used themes of
resilience + defiance (NOT the typical love/trucks narrative).

LYRICS:
[Verse 1 — talk-singing, raw, confessional]
(Theme: small-town resilience. 4 lines, short punchy phrases.)
...

HIT PROBABILITY: 73% (based on 12 breakout tracks analyzed)
CONFIDENCE: medium (45 baseline tracks, 89% audio feature coverage)
```
