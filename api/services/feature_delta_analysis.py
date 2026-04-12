"""
Feature delta analysis — Layer 2 of the Breakout Analysis Engine.

For each genre with breakout events, computes how the audio features
of breakout tracks differ from the genre baseline. Uses Welch's t-test
to identify which features are statistically significant differentiators.

Output: a per-genre dict like:
  {
    "tempo": {"delta": +12.5, "p_value": 0.003, "significant": True},
    "energy": {"delta": +0.15, "p_value": 0.02, "significant": True},
    "valence": {"delta": -0.08, "p_value": 0.45, "significant": False},
    ...
  }

Plus a list of human-readable top_differentiators ranked by significance.

See planning/PRD/breakoutengine_prd.md Layer 2 for the full design.
"""
from __future__ import annotations

import logging
import math
import uuid as uuid_mod
from datetime import date, datetime, timedelta, timezone
from statistics import mean, pstdev
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.breakout_event import BreakoutEvent
from api.models.genre_feature_delta import GenreFeatureDelta

logger = logging.getLogger(__name__)

WINDOW_DAYS = 30
MIN_BREAKOUTS = 3
MIN_BASELINE = 5
SIG_THRESHOLD = 0.10  # p-value cutoff for "significant"

AUDIO_FEATURE_KEYS = [
    "tempo", "energy", "danceability", "valence", "acousticness",
    "instrumentalness", "liveness", "speechiness", "loudness",
]


def _welch_t_test(a: list[float], b: list[float]) -> tuple[float, float]:
    """
    Welch's t-test (no scipy dependency).
    Returns (t_statistic, two_tailed_p_value).

    For p-value approximation we use a simple normal-distribution
    approximation since our sample sizes are typically small but the
    cutoff (0.1) is loose enough that exact precision isn't critical.
    """
    if len(a) < 2 or len(b) < 2:
        return 0.0, 1.0

    mean_a, mean_b = mean(a), mean(b)
    var_a = sum((x - mean_a) ** 2 for x in a) / (len(a) - 1)
    var_b = sum((x - mean_b) ** 2 for x in b) / (len(b) - 1)

    se = math.sqrt(var_a / len(a) + var_b / len(b))
    if se == 0:
        return 0.0, 1.0

    t = (mean_a - mean_b) / se

    # Approximate p-value using the survival function of the standard
    # normal distribution. For df > 30 this is very close to t-distribution;
    # for smaller df it slightly overestimates significance, which is
    # acceptable given our 0.1 threshold.
    p = 2 * (1 - _normal_cdf(abs(t)))
    return t, max(0.0, min(1.0, p))


def _normal_cdf(x: float) -> float:
    """Standard normal CDF using erf."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _format_differentiator(feature: str, delta: float, p_value: float) -> str:
    """Convert a feature delta into a human-readable bullet."""
    direction = "higher" if delta > 0 else "lower"
    abs_delta = abs(delta)

    # Special formatting per feature type
    if feature == "tempo":
        return f"{abs_delta:.0f} BPM {direction} than genre avg (p={p_value:.3f})"
    elif feature == "loudness":
        return f"{abs_delta:.1f} dB {direction} than genre avg (p={p_value:.3f})"
    elif feature in ("energy", "danceability", "valence", "acousticness",
                     "instrumentalness", "liveness", "speechiness"):
        pct = abs_delta * 100
        return f"{feature} {pct:.0f}% {direction} than genre avg (p={p_value:.3f})"
    return f"{feature} {direction} by {abs_delta:.2f} (p={p_value:.3f})"


async def compute_all_feature_deltas(
    db: AsyncSession,
    *,
    window_days: int = WINDOW_DAYS,
) -> dict[str, int]:
    """
    Sweep all genres with recent breakout events. For each, compute
    feature deltas vs the genre baseline and cache the result.
    """
    today = date.today()
    window_start = today - timedelta(days=window_days)

    stats = {
        "genres_processed": 0,
        "deltas_computed": 0,
        "skipped_low_data": 0,
        "elapsed_ms": 0,
    }
    started = datetime.now(timezone.utc)

    # ---- Get all genres with breakout events in the window ----
    genres_result = await db.execute(
        select(BreakoutEvent.genre_id)
        .where(BreakoutEvent.detection_date >= window_start)
        .distinct()
    )
    genre_ids = [row[0] for row in genres_result.fetchall()]

    for genre_id in genre_ids:
        stats["genres_processed"] += 1

        # Pull breakout audio features for this genre
        breakout_features = await _get_breakout_features(db, genre_id, window_start)

        # Pull baseline audio features (all tracks in the genre, excluding breakouts)
        baseline_features = await _get_baseline_features(db, genre_id, window_start)

        if len(breakout_features) < MIN_BREAKOUTS or len(baseline_features) < MIN_BASELINE:
            stats["skipped_low_data"] += 1
            continue

        deltas: dict[str, float] = {}
        significance: dict[str, float] = {}
        differentiators: list[tuple[str, float, float]] = []

        for feature in AUDIO_FEATURE_KEYS:
            b_vals = [t.get(feature) for t in breakout_features if isinstance(t.get(feature), (int, float))]
            base_vals = [t.get(feature) for t in baseline_features if isinstance(t.get(feature), (int, float))]

            if len(b_vals) < 2 or len(base_vals) < 2:
                continue

            delta = mean(b_vals) - mean(base_vals)
            _, p_value = _welch_t_test(b_vals, base_vals)

            deltas[feature] = round(delta, 4)
            significance[feature] = round(p_value, 4)

            if p_value < SIG_THRESHOLD:
                differentiators.append((feature, delta, p_value))

        if not deltas:
            stats["skipped_low_data"] += 1
            continue

        # Sort differentiators by p-value (most significant first)
        differentiators.sort(key=lambda x: x[2])
        top_diffs = [_format_differentiator(f, d, p) for f, d, p in differentiators[:5]]

        # Upsert: delete any existing row for this genre+window_end, then insert
        await db.execute(
            text("""
                DELETE FROM genre_feature_deltas
                WHERE genre_id = :gid AND window_end = :wend
            """),
            {"gid": genre_id, "wend": today},
        )
        gfd = GenreFeatureDelta(
            id=uuid_mod.uuid4(),
            genre_id=genre_id,
            window_start=window_start,
            window_end=today,
            breakout_count=len(breakout_features),
            baseline_count=len(baseline_features),
            deltas_json=deltas,
            significance_json=significance,
            top_differentiators=top_diffs,
        )
        db.add(gfd)
        stats["deltas_computed"] += 1

    await db.commit()
    stats["elapsed_ms"] = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    logger.info("[feature-delta-analysis] %s", stats)

    # Layer 2.5 — chain quantification refresh after deltas land.
    # Same daily cadence so the cache stays in sync with deltas.
    try:
        from api.services.breakout_quantification import quantify_all_genres_with_breakouts
        q_stats = await quantify_all_genres_with_breakouts(db)
        stats["quantifications_cached"] = q_stats["quantifications_cached"]
        stats["quantifications_skipped"] = q_stats["skipped_no_data"]
    except Exception as exc:
        logger.exception("[feature-delta-analysis] quantification chain failed: %s", exc)

    return stats


async def _get_breakout_features(
    db: AsyncSession, genre_id: str, since: date
) -> list[dict[str, Any]]:
    """Audio features dicts for breakout tracks in this genre."""
    result = await db.execute(
        select(BreakoutEvent.audio_features)
        .where(
            BreakoutEvent.genre_id == genre_id,
            BreakoutEvent.detection_date >= since,
            BreakoutEvent.audio_features.isnot(None),
        )
    )
    return [row[0] for row in result.fetchall() if isinstance(row[0], dict)]


async def _get_baseline_features(
    db: AsyncSession, genre_id: str, since: date
) -> list[dict[str, Any]]:
    """
    Audio features for ALL tracks classified into this genre (in
    tracks.genres array) that are NOT in the breakout set for the same
    window. Pulls from tracks.audio_features directly.
    """
    result = await db.execute(text("""
        SELECT t.audio_features
        FROM tracks t
        WHERE :gid = ANY(t.genres)
          AND t.audio_features IS NOT NULL
          AND t.audio_features::text <> '{}'
          AND t.id NOT IN (
              SELECT track_id
              FROM breakout_events
              WHERE genre_id = :gid AND detection_date >= :since
          )
    """), {"gid": genre_id, "since": since})
    return [row[0] for row in result.fetchall() if isinstance(row[0], dict)]
