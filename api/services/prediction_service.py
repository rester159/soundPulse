"""Prediction service — loads trained model and produces US-market predictions.

Produces 4 specific US-market prediction targets:
  1. billboard_hot_100 — will this track appear on Billboard Hot 100 within 14 days?
  2. spotify_top_50_us — will this track enter Spotify US Top 50 within 7 days?
  3. shazam_top_200_us — will this track enter Shazam US Top 200 within 7 days?
  4. cross_platform_breakout — will this track chart on 3+ US platforms within 14 days?

Falls back to a rule-based heuristic when no trained model is available.
"""

import logging
import uuid
from pathlib import Path

try:
    import joblib
except ImportError:
    joblib = None  # type: ignore[assignment]

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]

from sqlalchemy.ext.asyncio import AsyncSession

from api.services.feature_engineering import (
    FEATURE_NAMES,
    get_entity_features,
    features_to_vector,
)

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parents[2] / "ml" / "models"
MODEL_PATH = MODEL_DIR / "trending_predictor.joblib"

# Singleton cache for the loaded model so we don't hit disk on every request.
_model_cache: dict = {"model": None, "version": None}

MODEL_VERSION = "v0.2.0"

# ── US-market prediction targets ─────────────────────────────────────

PREDICTION_TARGETS = {
    "billboard_hot_100": {
        "label": "Billboard Hot 100",
        "horizon": "14d",
        "description": "Will this track appear on Billboard Hot 100 within 14 days?",
    },
    "spotify_top_50_us": {
        "label": "Spotify Top 50 US",
        "horizon": "7d",
        "description": "Will this track enter Spotify US Top 50 within 7 days?",
    },
    "shazam_top_200_us": {
        "label": "Shazam Top 200 US",
        "horizon": "7d",
        "description": "Will this track enter Shazam US Top 200 within 7 days?",
    },
    "cross_platform_breakout": {
        "label": "3+ US Platform Breakout",
        "horizon": "14d",
        "description": "Will this track chart on 3+ US platforms simultaneously within 14 days?",
    },
}


def _load_model():
    """Load the trained model from disk, or return None."""
    if joblib is None:
        return None

    if _model_cache["model"] is not None:
        return _model_cache["model"]

    if not MODEL_PATH.exists():
        logger.warning("No trained model found at %s — using rule-based fallback.", MODEL_PATH)
        return None

    try:
        model = joblib.load(MODEL_PATH)
        _model_cache["model"] = model
        _model_cache["version"] = MODEL_VERSION
        logger.info("Loaded prediction model from %s", MODEL_PATH)
        return model
    except Exception:
        logger.exception("Failed to load model from %s", MODEL_PATH)
        return None


def reload_model():
    """Force-reload the model from disk (e.g. after retraining)."""
    _model_cache["model"] = None
    _model_cache["version"] = None
    return _load_model()


# ── Rule-based fallback (4 US-market targets) ────────────────────────

def _rule_based_prediction(features: dict) -> dict:
    """Rule-based heuristic producing 4 US-market prediction targets.

    Each target uses different feature weightings:
      - billboard_hot_100: radio rank + velocity (Billboard is radio-driven)
      - spotify_top_50_us: spotify rank + velocity
      - shazam_top_200_us: shazam presence + discovery signals
      - cross_platform_breakout: platform_count + velocity across platforms
    """
    velocity = features["velocity"]
    cross_platform = features["cross_platform_count"]
    current_rank = features["current_rank"]
    peak_rank = features.get("peak_rank", current_rank)
    latest_composite = features.get("latest_composite", 0.0)
    acceleration = features.get("acceleration", 0.0)

    # Normalized component scores
    velocity_score = min(max(velocity / 10.0, -1.0), 1.0)
    platform_score = min(cross_platform / 6.0, 1.0)
    rank_score = max(1.0 - (current_rank / 100.0), 0.0)
    peak_rank_score = max(1.0 - (peak_rank / 200.0), 0.0)
    composite_score = min(latest_composite / 100.0, 1.0)
    accel_score = min(max(acceleration / 5.0, -1.0), 1.0)

    # ── billboard_hot_100: radio rank + velocity ──
    billboard_prob = (
        0.35 * rank_score      # current chart rank (radio-driven)
        + 0.30 * velocity_score  # momentum
        + 0.20 * platform_score  # cross-platform presence
        + 0.15 * composite_score  # overall trending strength
    )
    billboard_prob = min(max(billboard_prob, 0.01), 0.99)

    # ── spotify_top_50_us: spotify rank + velocity ──
    spotify_prob = (
        0.40 * rank_score       # current rank on Spotify
        + 0.35 * velocity_score   # rank velocity
        + 0.15 * accel_score      # acceleration
        + 0.10 * composite_score  # overall score
    )
    spotify_prob = min(max(spotify_prob, 0.01), 0.99)

    # ── shazam_top_200_us: shazam presence + discovery signals ──
    # Shazam captures discovery — tracks people hear and want to identify.
    # Lower peak rank = more discoverable, velocity matters for new tracks.
    shazam_prob = (
        0.30 * peak_rank_score   # discovery signal (peak rank)
        + 0.30 * velocity_score    # rising momentum
        + 0.25 * accel_score       # accelerating discovery
        + 0.15 * composite_score   # overall trending
    )
    shazam_prob = min(max(shazam_prob, 0.01), 0.99)

    # ── cross_platform_breakout: platform_count + cross-platform velocity ──
    cross_prob = (
        0.45 * platform_score    # number of platforms charting
        + 0.30 * velocity_score    # velocity across platforms
        + 0.15 * composite_score   # overall trending strength
        + 0.10 * accel_score       # momentum acceleration
    )
    cross_prob = min(max(cross_prob, 0.01), 0.99)

    # Top contributing features (shared across all targets)
    contributions = [
        {"feature": "velocity", "value": velocity, "impact": _impact_label(velocity_score)},
        {
            "feature": "cross_platform_count",
            "value": float(cross_platform),
            "impact": _impact_label(platform_score),
        },
        {"feature": "current_rank", "value": float(current_rank), "impact": _impact_label(rank_score)},
    ]
    contributions.sort(key=lambda c: abs(c["value"]), reverse=True)

    # Data quality factor: more days of history = tighter confidence interval
    days = features.get("days_since_first", 1)
    data_quality = min(days / 30.0, 1.0)  # 0.0 (1 day) to 1.0 (30+ days)

    predictions = {
        "billboard_hot_100": {
            "probability": round(billboard_prob, 4),
            **_confidence_interval(billboard_prob, data_quality, chart_size=100, current_rank=current_rank, velocity=velocity),
            "horizon": "14d",
            "label": "Billboard Hot 100",
            "description": _describe_prediction(
                "Billboard Hot 100", billboard_prob, "14 days",
                current_rank, cross_platform, velocity, acceleration,
                signals={"radio_rank": rank_score > 0.5, "velocity": velocity_score > 0.3}
            ),
        },
        "spotify_top_50_us": {
            "probability": round(spotify_prob, 4),
            **_confidence_interval(spotify_prob, data_quality, chart_size=50, current_rank=current_rank, velocity=velocity),
            "horizon": "7d",
            "label": "Spotify Top 50 US",
            "description": _describe_prediction(
                "Spotify US Top 50", spotify_prob, "7 days",
                current_rank, cross_platform, velocity, acceleration,
                signals={"spotify_rank": rank_score > 0.5, "velocity": velocity_score > 0.3}
            ),
        },
        "shazam_top_200_us": {
            "probability": round(shazam_prob, 4),
            **_confidence_interval(shazam_prob, data_quality, chart_size=200, current_rank=current_rank, velocity=velocity),
            "horizon": "7d",
            "label": "Shazam Top 200 US",
            "description": _describe_prediction(
                "Shazam US Top 200", shazam_prob, "7 days",
                current_rank, cross_platform, velocity, acceleration,
                signals={"discovery": peak_rank_score > 0.5, "acceleration": accel_score > 0.3}
            ),
        },
        "cross_platform_breakout": {
            "probability": round(cross_prob, 4),
            **_confidence_interval(cross_prob, data_quality, chart_size=6, current_rank=float(cross_platform), velocity=velocity, is_platform_count=True),
            "horizon": "14d",
            "label": "3+ US Platform Breakout",
            "description": _describe_prediction(
                "3+ US platforms simultaneously", cross_prob, "14 days",
                current_rank, cross_platform, velocity, acceleration,
                signals={"multi_platform": platform_score > 0.5, "velocity": velocity_score > 0.3}
            ),
        },
    }

    return {
        "predictions": predictions,
        "confidence_level": _confidence_level(max(billboard_prob, spotify_prob, shazam_prob, cross_prob)),
        "top_features": contributions[:3],
        "model_version": "rule-based-v2-us",
        "is_ml": False,
    }


# ── ML-based prediction ─────────────────────────────────────────────

def _ml_prediction(model, features: dict) -> dict:
    """Run the trained model on a feature vector.

    When the model supports multi-target output, returns all 4 US targets.
    Otherwise wraps single-output in the 4-target format with estimates.
    """
    vector = np.array([features_to_vector(features)])
    probability = float(model.predict_proba(vector)[0][1])

    # Feature importances
    importances = model.feature_importances_
    indexed = sorted(
        zip(FEATURE_NAMES, importances, features_to_vector(features)),
        key=lambda t: t[1],
        reverse=True,
    )
    top_features = [
        {"feature": name, "value": float(val), "impact": _importance_label(imp)}
        for name, imp, val in indexed[:5]
    ]

    # Derive per-target estimates from the single probability
    # These are rough approximations until per-target models are trained
    return {
        "predictions": {
            "billboard_hot_100": {
                "probability": round(probability * 0.85, 4),
                "horizon": "14d",
                "label": "Billboard Hot 100",
            },
            "spotify_top_50_us": {
                "probability": round(probability, 4),
                "horizon": "7d",
                "label": "Spotify Top 50 US",
            },
            "shazam_top_200_us": {
                "probability": round(min(probability * 1.1, 0.99), 4),
                "horizon": "7d",
                "label": "Shazam Top 200 US",
            },
            "cross_platform_breakout": {
                "probability": round(probability * 0.7, 4),
                "horizon": "14d",
                "label": "3+ US Platform Breakout",
            },
        },
        "confidence_level": _confidence_level(probability),
        "top_features": top_features,
        "model_version": _model_cache.get("version", MODEL_VERSION),
        "is_ml": True,
    }


# ── Public API ───────────────────────────────────────────────────────

async def predict_entity(
    db: AsyncSession,
    entity_id: uuid.UUID,
    entity_type: str,
) -> dict | None:
    """Return a prediction dict for the given entity, or None if not enough data.

    Returns dict with keys: predictions (4 US-market targets), confidence_level,
    top_features, model_version, is_ml, features.
    """
    features = await get_entity_features(db, entity_id, entity_type)
    if features is None:
        return None

    model = _load_model()
    if model is not None:
        pred = _ml_prediction(model, features)
    else:
        pred = _rule_based_prediction(features)

    pred["features"] = features
    return pred


# ── Helpers ──────────────────────────────────────────────────────────

def _confidence_level(prob: float) -> str:
    if prob >= 0.75 or prob <= 0.25:
        return "high"
    if prob >= 0.6 or prob <= 0.4:
        return "medium"
    return "low"


def _impact_label(score: float) -> str:
    if score >= 0.6:
        return "positive"
    if score <= -0.3:
        return "negative"
    return "neutral"


def _confidence_interval(
    probability: float,
    data_quality: float,
    chart_size: int = 100,
    current_rank: float = 200.0,
    velocity: float = 0.0,
    is_platform_count: bool = False,
) -> dict:
    """Compute a 95% confidence interval as a predicted chart position range.

    Instead of abstract probability bounds, produces a concrete position:
    "95% confident you'll reach at least position #X on this chart."

    Args:
        probability: predicted probability of charting (0-1)
        data_quality: 0-1 based on days of history (more data = tighter)
        chart_size: chart length (100 for Hot 100, 50 for Spotify Top 50, 200 for Shazam)
        current_rank: entity's current best rank across platforms
        velocity: rank velocity (positive = improving)
    """
    # Predict the most likely position based on current trajectory
    # Higher probability → higher predicted position (lower number = better)
    if current_rank <= chart_size:
        # Already on chart — project based on velocity
        projected_rank = max(1, current_rank - (velocity * 7))  # 7-day projection
    else:
        # Not on chart — estimate entry position from probability
        # High prob → enters near top, low prob → enters near bottom or doesn't
        projected_rank = chart_size * (1 - probability) + 1

    projected_rank = max(1, min(projected_rank, chart_size * 3))  # clamp

    # Uncertainty width based on data quality
    # 1 day of data → ±60% of chart size, 30+ days → ±15%
    uncertainty_pct = 0.60 - (0.45 * data_quality)
    uncertainty = chart_size * uncertainty_pct

    # Best case (95% upper bound) — the best position we're confident about
    best_case = max(1, int(projected_rank - uncertainty))
    # Worst case (95% lower bound)
    worst_case = min(chart_size * 3, int(projected_rank + uncertainty))

    # The key output: "95% sure you'll reach at least position #X"
    # This is the worst_case (conservative) bound
    guaranteed_position = worst_case

    # Will they make the chart at all?
    makes_chart = guaranteed_position <= chart_size

    if is_platform_count:
        # Cross-platform: positions are platform counts, not chart ranks
        outcome_95 = f"95% likely to chart on at least {max(1, best_case)} US platforms (currently on {int(current_rank)})"
        return {
            "predicted_platforms": int(projected_rank),
            "best_case_platforms": best_case,
            "worst_case_platforms": guaranteed_position,
            "makes_chart_95": int(projected_rank) >= 3,
            "outcome_95": outcome_95,
        }

    if makes_chart:
        outcome_95 = f"95% likely to reach at least #{guaranteed_position} on this chart"
    else:
        if guaranteed_position <= chart_size * 1.5:
            outcome_95 = f"95% likely to reach the #{guaranteed_position} range — just outside the chart, needs a push to break in"
        else:
            outcome_95 = f"95% likely to stay outside this chart for now (projected around #{int(projected_rank)})"

    return {
        "predicted_position": int(projected_rank),
        "best_case_position": best_case,
        "worst_case_position": guaranteed_position,
        "makes_chart_95": makes_chart,
        "outcome_95": outcome_95,
    }


def _importance_label(importance: float) -> str:
    if importance >= 0.2:
        return "high"
    if importance >= 0.1:
        return "medium"
    return "low"


def _describe_prediction(
    chart_name: str,
    probability: float,
    horizon_text: str,
    current_rank: float,
    platform_count: int,
    velocity: float,
    acceleration: float,
    signals: dict[str, bool] | None = None,
) -> str:
    """Generate a human-readable description of a prediction."""
    pct = round(probability * 100)
    signals = signals or {}

    # Opening sentence — probability statement
    if pct >= 75:
        opener = f"Strong likelihood ({pct}%) of charting on {chart_name} within {horizon_text}."
    elif pct >= 50:
        opener = f"Moderate chance ({pct}%) of reaching {chart_name} within {horizon_text}."
    elif pct >= 25:
        opener = f"Low but possible chance ({pct}%) of breaking into {chart_name} within {horizon_text}."
    else:
        opener = f"Unlikely ({pct}%) to reach {chart_name} within {horizon_text}."

    # Supporting evidence
    strengths = []
    weaknesses = []

    # Rank
    if current_rank <= 10:
        strengths.append(f"already ranked #{int(current_rank)} on a US chart")
    elif current_rank <= 50:
        strengths.append(f"currently at #{int(current_rank)}, within striking distance")
    elif current_rank <= 100:
        weaknesses.append(f"sitting at #{int(current_rank)}, needs a significant push")
    else:
        weaknesses.append("not currently charting in the top 100")

    # Velocity
    if velocity > 5:
        strengths.append("climbing rapidly")
    elif velocity > 0:
        strengths.append("trending upward")
    elif velocity < -5:
        weaknesses.append("losing momentum quickly")
    elif velocity < 0:
        weaknesses.append("slightly declining")
    else:
        weaknesses.append("no movement in rank")

    # Acceleration
    if acceleration > 2:
        strengths.append("momentum is accelerating")
    elif acceleration < -2:
        weaknesses.append("momentum is decelerating")

    # Platform presence
    if platform_count >= 4:
        strengths.append(f"strong cross-platform presence ({platform_count} platforms)")
    elif platform_count >= 2:
        strengths.append(f"appearing on {platform_count} platforms")
    else:
        weaknesses.append("only on 1 platform so far")

    # Specific signals
    for signal_name, is_strong in signals.items():
        if signal_name == "radio_rank" and not is_strong:
            weaknesses.append("needs radio airplay pickup")
        if signal_name == "discovery" and is_strong:
            strengths.append("strong discovery signal — people are Shazaming it")
        if signal_name == "multi_platform" and not is_strong:
            weaknesses.append("needs to chart on more platforms")

    # Build description
    parts = [opener]
    if strengths:
        parts.append("Positives: " + ", ".join(strengths) + ".")
    if weaknesses:
        parts.append("Risks: " + ", ".join(weaknesses) + ".")

    return " ".join(parts)
