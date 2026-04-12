# Opportunity Quantification Spec

## 0. Purpose

Every breakout opportunity surfaced by the engine must answer two questions a label CEO actually cares about:

1. **"How big is this?"** — projected lifetime streams + $ revenue per platform
2. **"Should I trust the number?"** — explicit confidence level + the data behind it

Today the breakout engine surfaces opportunities as a sorted list with feature deltas and gap descriptions. It does NOT tell you "this opportunity is worth ~$1,500 with medium confidence." This spec adds that layer.

The quantification is not predictive of any one specific song that may or may not be created. It is a **model-based estimate** of what a NEW track in the genre's gap zone could realistically achieve, anchored to the actual measured performance of the breakout tracks already in that zone.

---

## 1. Data sources we have

| Source | Field | Available now | What it tells us |
|---|---|---|---|
| `trending_snapshots.signals_json.spotify_popularity` | 0-100 score | yes (~21k snapshots) | Spotify's internal popularity score — strong proxy for monthly streams |
| `trending_snapshots.signals_json.current_plays` | int | partial | Actual reported play count (Spotify charts) |
| `breakout_events.peak_composite` | normalized 0-100 | yes (1,093 events) | Our composite score at the breakout peak |
| `breakout_events.peak_velocity` | float | yes | Day-over-day growth rate |
| `breakout_events.platform_count` | int | yes | How many platforms the track charted on |
| `breakout_events.outcome_label` | hit/moderate/fizzle | not yet (30-day lag) | Validated outcome label, used for confidence calibration |
| `tracks.audio_features` | dict | growing (1,090+) | Used for gap matching, not directly for $ estimation |
| `artists.metadata_json.chartmetric_stats` | dict | partial | Per-artist follower/listener counts |

We do NOT have direct access to:
- Apple Music stream counts (no public API)
- Tidal/Amazon stream counts
- TikTok use counts
- YouTube view counts at the music-track level

For platforms without direct data, we use **per-platform multipliers** derived from public industry data on average platform-mix ratios for charting tracks.

---

## 2. Stream estimation model

### 2.1 From Spotify popularity to lifetime streams

Industry benchmarks (cross-validated from public Chartmetric/Spotify data, 2024-2025):

| Spotify popularity (peak) | Lifetime Spotify streams (range) | Median |
|---|---|---|
| 95-100 | 500M – 5B | 1.5B |
| 90-94 | 100M – 500M | 250M |
| 85-89 | 30M – 100M | 60M |
| 80-84 | 8M – 30M | 18M |
| 75-79 | 2M – 8M | 4.5M |
| 70-74 | 500K – 2M | 1.0M |
| 65-69 | 150K – 500K | 280K |
| 60-64 | 50K – 150K | 90K |
| 55-59 | 15K – 50K | 28K |
| 50-54 | 5K – 15K | 9K |
| 40-49 | 1K – 5K | 2.3K |
| 30-39 | 200 – 1K | 480 |
| < 30 | 0 – 200 | 60 |

Encoded as a piecewise function in `_spotify_popularity_to_streams(popularity)` returning `(low, median, high)`.

### 2.2 Cross-platform multipliers

For a track that achieves X Spotify streams, the typical platform mix for charting tracks is:

| Platform | Multiplier vs Spotify streams | Source |
|---|---|---|
| Spotify | 1.00 | baseline |
| Apple Music | 0.30 | ~30% of Spotify volume on average |
| YouTube Music | 0.45 | ~45% of Spotify (YouTube has higher volume but lower per-stream) |
| Tidal | 0.02 | small market, ~2% |
| Amazon Music | 0.10 | ~10% |
| TikTok (video uses) | 0.005 | very rough — depends entirely on virality |
| Shazam (recognitions) | 0.02 | discovery signal, doesn't directly pay |

These multipliers come from aggregate industry reports on top-100 streaming distributions. For a specific genre they vary (k-pop skews higher on YouTube, country skews higher on Apple/Amazon), so v2 of this model can apply genre adjustments.

### 2.3 Per-platform per-stream rates ($ per stream)

Mid-2025 reported payouts (these are NOT contractual; they vary by listener tier, region, label deal, and time period):

| Platform | $/stream (low) | $/stream (mid) | $/stream (high) |
|---|---|---|---|
| Spotify | $0.0024 | $0.004 | $0.0084 |
| Apple Music | $0.006 | $0.008 | $0.010 |
| YouTube Music | $0.0006 | $0.0008 | $0.001 |
| YouTube ad-supported | $0.0003 | $0.0005 | $0.0007 |
| Tidal | $0.011 | $0.0125 | $0.014 |
| Amazon Music | $0.003 | $0.004 | $0.005 |

We use the **mid** value for the median estimate, **low** for the conservative bound, **high** for the optimistic bound.

### 2.4 TikTok handling

TikTok pays into a creator fund pool, not per-stream. The fund pays out at roughly **$0.02 to $0.04 per 1,000 video views** for the music creator's share, but most of the value of TikTok exposure is **driving Spotify discovery**, not direct $ from TikTok.

We surface TikTok separately as `tiktok_exposure_estimate` with a `note` explaining it's not a $ figure but a discovery proxy.

---

## 3. Per-opportunity quantification algorithm

For each breakout-opportunity (one per genre in the top-N list):

### Step 1 — Anchor to the breakout cohort

```python
breakouts = SELECT breakout_events
            WHERE genre_id = X
            AND detection_date >= now() - INTERVAL '90 days'
            ORDER BY breakout_score DESC
            LIMIT 30
```

For each breakout, fetch the track's `signals_json.spotify_popularity` from its chart snapshots (use the maximum observed in a 14-day window around the detection date).

Compute:
- `n_breakouts` — count of breakouts in the cohort
- `n_with_popularity` — count with valid spotify_popularity
- `peak_popularities` — list of max popularity values
- `mean_peak_popularity` — average
- `p90_peak_popularity` — 90th percentile (for the high estimate)
- `p10_peak_popularity` — 10th percentile (for the low estimate)

### Step 2 — Project a NEW track in the gap zone

A new track is **unproven**, so its expected peak popularity is discounted vs the observed cohort:

```
new_track_peak_popularity_median  = mean_peak_popularity * 0.75
new_track_peak_popularity_low     = p10_peak_popularity * 0.60
new_track_peak_popularity_high    = p90_peak_popularity * 0.90
```

Rationale: most new tracks underperform the average of "tracks that already broke out", because the existing breakouts are survivor-biased. The 0.75 discount reflects "most new tracks won't break out; the ones that do will reach roughly 75% of their reference cohort's peak."

### Step 3 — Convert to lifetime stream estimates

For each of the three estimates (low/median/high), call `_spotify_popularity_to_streams(p)` which returns the mid-value of the band the popularity falls into.

Then apply the cross-platform multipliers to get per-platform stream counts.

### Step 4 — Convert to $ revenue

For each platform, multiply streams × per-stream rate. Use the same low/mid/high band per platform.

Sum all platforms for `total_lifetime_revenue_usd`.

### Step 5 — Compute confidence

Confidence = weighted sum of 5 components, each in [0, 1]:

```python
sample_size_score   = min(n_breakouts / 15, 1.0)
popularity_coverage = min(n_with_popularity / max(n_breakouts, 1), 1.0)
variance_score      = max(0, 1 - (std(peak_popularities) / 30))   # high variance = low confidence
data_freshness      = exp(-days_since_latest_breakout / 30)        # fresher = more relevant
feature_coverage    = audio_features_coverage_pct / 100
outcome_calibration = resolved_breakouts_count / max(n_breakouts, 1)  # 0 until 30+ days pass

confidence_score = (
    0.30 * sample_size_score +
    0.20 * popularity_coverage +
    0.15 * variance_score +
    0.10 * data_freshness +
    0.10 * feature_coverage +
    0.15 * outcome_calibration
)
```

Confidence label:
- `high` if score ≥ 0.70 AND n_breakouts ≥ 10 AND n_with_popularity ≥ 5
- `medium` if score ≥ 0.45 AND n_breakouts ≥ 5
- `low` if score ≥ 0.25
- `very_low` otherwise

### Step 6 — Cache and return

Cache the result in a new `breakout_quantifications` table keyed by `genre_id + window_end`. Refresh daily alongside the feature delta sweep.

---

## 4. Output schema

```json
{
  "estimated_lifetime_streams": {
    "spotify":      {"low": 50000, "median": 200000, "high": 800000},
    "apple_music":  {"low": 15000, "median": 60000,  "high": 240000},
    "youtube_music":{"low": 22500, "median": 90000,  "high": 360000},
    "tidal":        {"low": 1000,  "median": 4000,   "high": 16000},
    "amazon_music": {"low": 5000,  "median": 20000,  "high": 80000}
  },
  "estimated_revenue_usd": {
    "spotify":      {"low": 120,  "median": 800,    "high": 6720},
    "apple_music":  {"low": 90,   "median": 480,    "high": 2400},
    "youtube_music":{"low": 14,   "median": 72,     "high": 360},
    "tidal":        {"low": 11,   "median": 50,     "high": 224},
    "amazon_music": {"low": 15,   "median": 80,     "high": 400},
    "total":        {"low": 250,  "median": 1482,   "high": 10104}
  },
  "tiktok_exposure": {
    "estimated_video_uses": {"low": 250, "median": 1000, "high": 4000},
    "note": "TikTok pays into a pooled fund, not per-stream. Numbers reflect discovery exposure, not direct revenue."
  },
  "confidence": {
    "level": "medium",
    "score": 0.62,
    "components": {
      "sample_size": 0.80,
      "popularity_coverage": 0.71,
      "variance": 0.55,
      "data_freshness": 0.92,
      "feature_coverage": 0.45,
      "outcome_calibration": 0.00
    },
    "explanation": "12 of 17 breakouts have popularity data; outcomes have not yet resolved (resolution begins 30 days after detection)."
  },
  "based_on": {
    "n_breakouts_analyzed": 17,
    "n_with_popularity_data": 12,
    "mean_peak_popularity": 68.5,
    "p90_peak_popularity": 84.0,
    "p10_peak_popularity": 51.0,
    "stream_data_source": "spotify_popularity_estimation",
    "outcome_resolution_rate": 0.0,
    "computed_at": "2026-04-12T22:30:00Z"
  }
}
```

---

## 5. Database changes

### New table: `breakout_quantifications`

```sql
CREATE TABLE breakout_quantifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    genre_id        VARCHAR(100) NOT NULL,
    window_end      DATE NOT NULL,
    quantification  JSON NOT NULL,
    confidence_level VARCHAR(20) NOT NULL,
    confidence_score FLOAT NOT NULL,
    total_revenue_median_usd  FLOAT NOT NULL,  -- denormalized for ORDER BY
    n_breakouts_analyzed INT NOT NULL,
    computed_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (genre_id, window_end)
);

CREATE INDEX idx_quant_revenue ON breakout_quantifications(total_revenue_median_usd DESC);
```

The `quantification` JSON column holds the full output from §4 verbatim. The denormalized columns allow fast sorting/filtering without JSON ops.

---

## 6. Date surfacing (separate small ask)

Each breakout has `detection_date` (the day the engine first flagged it). We add this to:
- The `top-opportunities` API response: each blueprint gets `surfaced_at` (the earliest detection_date for any breakout in the genre's cohort)
- The UI: each card shows `Surfaced 3 days ago` or the absolute date

---

## 7. UI changes

`SongLab.jsx` updates:

1. **Card count**: change from hardcoded 5 to a `?n=` query param controlled by a UI selector. Default 10, options 5/10/20.
2. **Quantification block** on each card:
   - Big-number revenue: `~$1,500` (median) with `($250 – $10K)` range below
   - Per-platform breakdown collapsible: Spotify $800 / Apple $480 / YouTube $72 / Tidal $50 / Amazon $80
   - Stream counts: total median streams across platforms
   - TikTok exposure note (not $)
3. **Confidence indicator**: confidence level pill (high/medium/low/very_low) with the numeric score and a tooltip listing the 6 components
4. **Surfaced date**: small `Surfaced 5 days ago · 3 detections this window` line at the top of each card
5. **Sort options**: by opportunity score (default), by revenue median, by confidence

---

## 8. Honest limitations

This model is intentionally conservative and explicit about its bounds:

- **It is NOT a promise.** The numbers describe what a NEW track in the gap zone could realistically achieve based on the cohort that already exists. A specific generated track may massively over- or under-perform depending on production quality, marketing, and luck.
- **The 0.75 discount factor is arbitrary.** It will be tuned via outcome calibration once we have ≥ 30 resolved breakouts (~30 days from now).
- **Apple/Tidal/Amazon estimates are derivative.** We have no direct stream data; we use Spotify-anchored multipliers. Genre-specific tuning is a v2 feature.
- **TikTok is not in $ figures.** The pooled-fund model + zero data access make any $ figure meaningless.
- **Revenue is gross, not net.** No deduction for distributor cut (~10-30%), publishing splits, mechanical splits, or PRO collection lag. The label CEO sees gross because that's the comparable industry benchmark.
- **Confidence depends heavily on `outcome_calibration`** which is 0 today. As resolved breakouts accumulate, confidence numbers will become much more meaningful.

This is the v1 of the model. The math is transparent so it can be tuned. Every component is in the cache table so changes can be A/B tested.

---

## 9. Implementation order

1. Migration 009: `breakout_quantifications` table
2. Service: `api/services/breakout_quantification.py` with the model
3. Sweep: hook into the existing `compute_all_feature_deltas` daily job (extend it to also compute quantifications)
4. API: extend `/blueprint/top-opportunities` to include quantification + surfaced_at
5. UI: extend `SongLab.jsx` cards
6. Test E2E: verify numbers are sane on r-and-b.soul, electronic.ambient, pop.k-pop

Total estimated time: ~90 minutes.
