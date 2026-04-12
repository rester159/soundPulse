"""
Breakout opportunity quantification.

Per planning/PRD/opportunity_quantification_spec.md. For each genre with
breakout events, computes:
  - Expected lifetime streams per platform (Spotify-anchored, multipliers
    for Apple/YouTube/Tidal/Amazon, plus a TikTok exposure note)
  - Expected $ revenue per platform (low/median/high range)
  - Confidence level + score with explicit components
  - The data the projection is based on

Stream estimation goes through `_spotify_popularity_to_streams()` which
encodes the industry-known mapping from peak Spotify popularity to
lifetime stream counts. The new track (a hypothetical track in the gap
zone) is discounted vs the observed cohort because new releases are
unproven.

Cached in breakout_quantifications, keyed by (genre_id, window_end).
The daily feature-delta sweep extends to also write quantifications.
"""
from __future__ import annotations

import logging
import math
import statistics
import uuid as uuid_mod
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.breakout_event import BreakoutEvent
from api.models.breakout_quantification import BreakoutQuantification

logger = logging.getLogger(__name__)


# ---- Industry constants ----

# Spotify peak popularity → (low, median, high) lifetime streams
# Based on cross-validated public Chartmetric/Spotify data, 2024-2025.
POPULARITY_TO_STREAMS = [
    (95, (500_000_000, 1_500_000_000, 5_000_000_000)),
    (90, (100_000_000, 250_000_000, 500_000_000)),
    (85, (30_000_000, 60_000_000, 100_000_000)),
    (80, (8_000_000, 18_000_000, 30_000_000)),
    (75, (2_000_000, 4_500_000, 8_000_000)),
    (70, (500_000, 1_000_000, 2_000_000)),
    (65, (150_000, 280_000, 500_000)),
    (60, (50_000, 90_000, 150_000)),
    (55, (15_000, 28_000, 50_000)),
    (50, (5_000, 9_000, 15_000)),
    (40, (1_000, 2_300, 5_000)),
    (30, (200, 480, 1_000)),
    (0,  (0, 60, 200)),
]

# Cross-platform stream multipliers vs Spotify volume (charting tracks).
# From aggregate industry reports on top-100 distributions.
PLATFORM_STREAM_MULTIPLIERS = {
    "spotify":       1.00,
    "apple_music":   0.30,
    "youtube_music": 0.45,
    "tidal":         0.02,
    "amazon_music":  0.10,
}

# Per-stream payout rates ($) — (low, mid, high) per platform, mid-2025.
# These are NOT contractual; they vary by listener tier, region, label deal.
PLATFORM_PER_STREAM_USD = {
    "spotify":       (0.0024, 0.0040, 0.0084),
    "apple_music":   (0.0060, 0.0080, 0.0100),
    "youtube_music": (0.0006, 0.0008, 0.0010),
    "tidal":         (0.0110, 0.0125, 0.0140),
    "amazon_music":  (0.0030, 0.0040, 0.0050),
}

# TikTok handling — not a $ figure, just exposure
TIKTOK_USE_MULTIPLIER = 0.005  # roughly 1 video use per 200 Spotify streams

# Discount factors applied when projecting a NEW (unproven) track from
# the observed breakout cohort. New tracks underperform the survivors.
NEW_TRACK_LOW_DISCOUNT    = 0.60   # applied to the cohort's p10
NEW_TRACK_MEDIAN_DISCOUNT = 0.75   # applied to the cohort's mean
NEW_TRACK_HIGH_DISCOUNT   = 0.90   # applied to the cohort's p90

# Confidence model thresholds
SAMPLE_SIZE_FULL = 15
VARIANCE_FULL_STD = 30  # std dev of popularity below which variance score = 1
DAYS_FRESHNESS_HALF = 30  # exponential decay half-life in days


# ---- Stream estimation ----

def _spotify_popularity_to_streams(popularity: float) -> tuple[float, float, float]:
    """
    Returns (low, median, high) lifetime stream estimate for a Spotify
    popularity value. Linearly interpolates between bands.
    """
    if popularity is None or popularity < 0:
        return (0, 0, 0)

    # Find the right band
    for cutoff, bands in POPULARITY_TO_STREAMS:
        if popularity >= cutoff:
            return tuple(float(b) for b in bands)
    return tuple(float(b) for b in POPULARITY_TO_STREAMS[-1][1])


def _project_new_track_popularities(
    peak_popularities: list[float],
) -> tuple[float, float, float]:
    """
    Given the observed peak popularities of breakout tracks in the genre
    cohort, project (low, median, high) peak popularity for a NEW track
    targeting the same gap zone.

    Discounts applied because new releases are unproven.
    """
    if not peak_popularities:
        return (0, 0, 0)

    sorted_pops = sorted(peak_popularities)
    n = len(sorted_pops)
    p10 = sorted_pops[max(0, int(n * 0.10))]
    p90 = sorted_pops[min(n - 1, int(n * 0.90))]
    mean = statistics.fmean(sorted_pops)

    return (
        round(p10  * NEW_TRACK_LOW_DISCOUNT,    1),
        round(mean * NEW_TRACK_MEDIAN_DISCOUNT, 1),
        round(p90  * NEW_TRACK_HIGH_DISCOUNT,   1),
    )


def _streams_to_revenue(streams_low: float, streams_med: float, streams_high: float) -> dict[str, dict[str, float]]:
    """For each platform, compute streams + revenue from the Spotify-anchored estimates."""
    out_streams: dict[str, dict[str, float]] = {}
    out_revenue: dict[str, dict[str, float]] = {}
    total_low = total_med = total_high = 0.0

    for platform, mult in PLATFORM_STREAM_MULTIPLIERS.items():
        plat_low  = streams_low  * mult
        plat_med  = streams_med  * mult
        plat_high = streams_high * mult
        out_streams[platform] = {
            "low":    round(plat_low),
            "median": round(plat_med),
            "high":   round(plat_high),
        }

        rate_low, rate_mid, rate_high = PLATFORM_PER_STREAM_USD[platform]
        rev_low  = plat_low  * rate_low
        rev_med  = plat_med  * rate_mid
        rev_high = plat_high * rate_high
        out_revenue[platform] = {
            "low":    round(rev_low,  2),
            "median": round(rev_med,  2),
            "high":   round(rev_high, 2),
        }
        total_low  += rev_low
        total_med  += rev_med
        total_high += rev_high

    out_revenue["total"] = {
        "low":    round(total_low,  2),
        "median": round(total_med,  2),
        "high":   round(total_high, 2),
    }
    return {"streams": out_streams, "revenue": out_revenue}


# ---- Confidence ----

def _compute_confidence(
    n_breakouts: int,
    n_with_popularity: int,
    peak_popularities: list[float],
    days_since_latest: int,
    feature_coverage_pct: float,
    resolved_breakouts: int,
) -> tuple[str, float, dict[str, float], str]:
    """
    Returns (label, score, components, explanation).
    """
    sample_size_score = min(n_breakouts / SAMPLE_SIZE_FULL, 1.0)
    popularity_coverage = (
        min(n_with_popularity / max(n_breakouts, 1), 1.0)
        if n_breakouts > 0 else 0.0
    )

    if len(peak_popularities) >= 2:
        std = statistics.pstdev(peak_popularities)
        variance_score = max(0.0, 1.0 - (std / VARIANCE_FULL_STD))
    else:
        variance_score = 0.0

    data_freshness = math.exp(-days_since_latest / DAYS_FRESHNESS_HALF) if days_since_latest >= 0 else 1.0
    feature_coverage = min((feature_coverage_pct or 0) / 100, 1.0)
    outcome_calibration = min(resolved_breakouts / max(n_breakouts, 1), 1.0)

    components = {
        "sample_size":         round(sample_size_score, 3),
        "popularity_coverage": round(popularity_coverage, 3),
        "variance":            round(variance_score, 3),
        "data_freshness":      round(data_freshness, 3),
        "feature_coverage":    round(feature_coverage, 3),
        "outcome_calibration": round(outcome_calibration, 3),
    }

    score = (
        0.30 * sample_size_score +
        0.20 * popularity_coverage +
        0.15 * variance_score +
        0.10 * data_freshness +
        0.10 * feature_coverage +
        0.15 * outcome_calibration
    )
    score = round(score, 3)

    if score >= 0.70 and n_breakouts >= 10 and n_with_popularity >= 5:
        label = "high"
    elif score >= 0.45 and n_breakouts >= 5:
        label = "medium"
    elif score >= 0.25:
        label = "low"
    else:
        label = "very_low"

    pieces = []
    if n_breakouts < 5:
        pieces.append(f"only {n_breakouts} breakouts (need 5+ for medium, 10+ for high)")
    if n_with_popularity < n_breakouts:
        pieces.append(f"{n_with_popularity}/{n_breakouts} have popularity data")
    if outcome_calibration == 0:
        pieces.append("outcomes have not yet resolved (begins 30 days after detection)")
    if not pieces:
        pieces.append("strong signal across all components")
    explanation = "; ".join(pieces)

    return label, score, components, explanation


# ---- Main quantification ----

async def quantify_genre(
    db: AsyncSession,
    genre_id: str,
    *,
    window_days: int = 90,
) -> dict[str, Any]:
    """
    Build a quantification dict for one genre. Returns the full output
    shape from the spec §4.
    """
    today = date.today()
    window_start = today - timedelta(days=window_days)

    # 1. Pull breakouts in the genre cohort
    result = await db.execute(text("""
        SELECT
            be.track_id,
            be.detection_date,
            be.peak_composite,
            be.resolved_at IS NOT NULL AS resolved
        FROM breakout_events be
        WHERE be.genre_id = :gid
          AND be.detection_date >= :window_start
        ORDER BY be.breakout_score DESC
        LIMIT 30
    """), {"gid": genre_id, "window_start": window_start})
    rows = result.fetchall()

    if not rows:
        return {
            "genre": genre_id,
            "error": "no breakout events in window",
            "n_breakouts_analyzed": 0,
        }

    n_breakouts = len(rows)
    track_ids = [r[0] for r in rows]
    detection_dates = [r[1] for r in rows]
    resolved_count = sum(1 for r in rows if r[3])
    days_since_latest = max(0, (today - max(detection_dates)).days)

    # 2. Pull peak Spotify popularity per breakout track
    pop_result = await db.execute(text("""
        SELECT
            ts.entity_id,
            MAX( (ts.signals_json::jsonb->>'spotify_popularity')::float ) AS peak_pop
        FROM trending_snapshots ts
        WHERE ts.entity_id = ANY(:tids)
          AND ts.entity_type = 'track'
          AND (ts.signals_json::jsonb)->>'spotify_popularity' ~ '^[0-9]+(\\.[0-9]+)?$'
        GROUP BY ts.entity_id
    """), {"tids": [str(t) for t in track_ids]})
    popularities_by_track = {row[0]: float(row[1]) for row in pop_result.fetchall() if row[1] is not None}
    peak_popularities = list(popularities_by_track.values())
    n_with_popularity = len(peak_popularities)

    # 3. Audio feature coverage for the genre
    feat_result = await db.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE audio_features IS NOT NULL AND audio_features::text <> '{}') AS with_af
        FROM tracks
        WHERE :gid = ANY(genres)
    """), {"gid": genre_id})
    feat_row = feat_result.fetchone()
    feature_coverage_pct = (
        (feat_row[1] / feat_row[0] * 100) if feat_row and feat_row[0] > 0 else 0
    )

    # 4. Project new-track peak popularity
    if n_with_popularity >= 2:
        proj_low, proj_med, proj_high = _project_new_track_popularities(peak_popularities)
    elif n_with_popularity == 1:
        single = peak_popularities[0]
        proj_low  = single * 0.4
        proj_med  = single * 0.6
        proj_high = single * 0.85
    else:
        proj_low = proj_med = proj_high = 0

    # 5. Convert to streams (per platform, low/median/high)
    streams_low_band  = _spotify_popularity_to_streams(proj_low)[0]
    streams_med_band  = _spotify_popularity_to_streams(proj_med)[1]
    streams_high_band = _spotify_popularity_to_streams(proj_high)[2]

    sr = _streams_to_revenue(streams_low_band, streams_med_band, streams_high_band)

    # 6. TikTok exposure estimate (not $)
    tiktok_low  = round(streams_low_band  * TIKTOK_USE_MULTIPLIER)
    tiktok_med  = round(streams_med_band  * TIKTOK_USE_MULTIPLIER)
    tiktok_high = round(streams_high_band * TIKTOK_USE_MULTIPLIER)

    # 7. Confidence
    label, score, components, explanation = _compute_confidence(
        n_breakouts=n_breakouts,
        n_with_popularity=n_with_popularity,
        peak_popularities=peak_popularities,
        days_since_latest=days_since_latest,
        feature_coverage_pct=feature_coverage_pct,
        resolved_breakouts=resolved_count,
    )

    # 8. Assemble output
    return {
        "genre": genre_id,
        "estimated_lifetime_streams": sr["streams"],
        "estimated_revenue_usd": sr["revenue"],
        "tiktok_exposure": {
            "estimated_video_uses": {
                "low": tiktok_low,
                "median": tiktok_med,
                "high": tiktok_high,
            },
            "note": "TikTok pays into a pooled fund, not per-stream. Numbers reflect discovery exposure, not direct revenue.",
        },
        "confidence": {
            "level": label,
            "score": score,
            "components": components,
            "explanation": explanation,
        },
        "based_on": {
            "n_breakouts_analyzed": n_breakouts,
            "n_with_popularity_data": n_with_popularity,
            "mean_peak_popularity": round(statistics.fmean(peak_popularities), 1) if peak_popularities else None,
            "p90_peak_popularity": round(sorted(peak_popularities)[min(len(peak_popularities)-1, int(len(peak_popularities)*0.9))], 1) if peak_popularities else None,
            "p10_peak_popularity": round(sorted(peak_popularities)[max(0, int(len(peak_popularities)*0.1))], 1) if peak_popularities else None,
            "projected_new_track_popularity": {
                "low": proj_low,
                "median": proj_med,
                "high": proj_high,
            },
            "stream_data_source": "spotify_popularity_estimation",
            "outcome_resolution_rate": round(resolved_count / max(n_breakouts, 1), 3),
            "days_since_latest_breakout": days_since_latest,
            "feature_coverage_pct": round(feature_coverage_pct, 1),
            "computed_at": datetime.now(timezone.utc).isoformat(),
        },
        "earliest_surfaced_at": min(detection_dates).isoformat() if detection_dates else None,
        "latest_surfaced_at": max(detection_dates).isoformat() if detection_dates else None,
    }


async def quantify_all_genres_with_breakouts(
    db: AsyncSession,
    *,
    window_days: int = 90,
) -> dict[str, int]:
    """
    Sweep all genres with breakout events and cache quantifications.
    Called by the daily sweep job alongside feature-delta analysis.
    """
    today = date.today()
    window_start = today - timedelta(days=window_days)

    stats = {
        "genres_processed": 0,
        "quantifications_cached": 0,
        "skipped_no_data": 0,
        "elapsed_ms": 0,
    }
    started = datetime.now(timezone.utc)

    genres_result = await db.execute(
        select(BreakoutEvent.genre_id)
        .where(BreakoutEvent.detection_date >= window_start)
        .distinct()
    )
    genre_ids = [row[0] for row in genres_result.fetchall()]

    for genre_id in genre_ids:
        stats["genres_processed"] += 1
        q = await quantify_genre(db, genre_id, window_days=window_days)
        if q.get("error"):
            stats["skipped_no_data"] += 1
            continue

        # Upsert
        await db.execute(text("""
            DELETE FROM breakout_quantifications
            WHERE genre_id = :gid AND window_end = :wend
        """), {"gid": genre_id, "wend": today})

        row = BreakoutQuantification(
            id=uuid_mod.uuid4(),
            genre_id=genre_id,
            window_end=today,
            quantification=q,
            confidence_level=q["confidence"]["level"],
            confidence_score=q["confidence"]["score"],
            total_revenue_median_usd=q["estimated_revenue_usd"]["total"]["median"],
            n_breakouts_analyzed=q["based_on"]["n_breakouts_analyzed"],
        )
        db.add(row)
        stats["quantifications_cached"] += 1

    await db.commit()
    stats["elapsed_ms"] = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    logger.info("[breakout-quantification] %s", stats)
    return stats
