"""Prediction service for the SoundPulse advanced prediction engine.

Loads the trained ensemble from disk, computes features for entities,
and returns predictions. Supports batch prediction with optional
Redis caching.
"""

import json
import logging
import uuid
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from ml.ensemble import EnsemblePredictor
from ml.features import (
    FEATURE_NAMES,
    compute_features,
    features_to_vector,
)

logger = logging.getLogger(__name__)

SAVED_MODELS_DIR = Path(__file__).resolve().parent / "saved_models"
CACHE_TTL_SECONDS = 3600  # 1 hour

# Singleton ensemble cache
_ensemble_cache: dict = {"ensemble": None, "loaded": False}


def _load_ensemble() -> EnsemblePredictor | None:
    """Load the trained ensemble from disk (singleton)."""
    if _ensemble_cache["loaded"]:
        return _ensemble_cache["ensemble"]

    _ensemble_cache["loaded"] = True

    if not (SAVED_MODELS_DIR / "meta_learner.pkl").exists():
        logger.warning(
            "No trained ensemble found at %s. Using rule-based fallback.",
            SAVED_MODELS_DIR,
        )
        _ensemble_cache["ensemble"] = None
        return None

    try:
        ensemble = EnsemblePredictor(feature_names=FEATURE_NAMES)
        ensemble.load(SAVED_MODELS_DIR)
        _ensemble_cache["ensemble"] = ensemble
        logger.info(
            "Loaded ensemble from %s. Active models: %s",
            SAVED_MODELS_DIR,
            ensemble.active_models,
        )
        return ensemble
    except Exception:
        logger.exception("Failed to load ensemble from %s", SAVED_MODELS_DIR)
        _ensemble_cache["ensemble"] = None
        return None


def reload_ensemble() -> EnsemblePredictor | None:
    """Force-reload the ensemble from disk (e.g. after retraining)."""
    _ensemble_cache["ensemble"] = None
    _ensemble_cache["loaded"] = False
    return _load_ensemble()


# ── Single entity prediction ─────────────────────────────────────────


async def predict_entity(
    db: AsyncSession,
    entity_id: uuid.UUID,
    entity_type: str,
    horizon: str = "7d",
) -> dict | None:
    """Generate a prediction for a single entity.

    Returns a dict with: probability, calibrated_confidence, prediction_label,
    top_features, model_version, is_ml, features, horizon, predicted_score_change.

    Returns None if there is not enough data.
    """
    features = await compute_features(db, entity_id, entity_type)
    if features is None:
        return None

    feature_vector = features_to_vector(features)
    history_days = int(features.get("entity_age_days", 0))

    # Build LSTM sequence if model supports it
    sequence = await _build_sequence(db, entity_id, entity_type)

    ensemble = _load_ensemble()
    if ensemble is None:
        # Create a temporary ensemble for rule-based fallback
        ensemble = EnsemblePredictor(feature_names=FEATURE_NAMES)

    prediction = ensemble.predict(
        features=features,
        feature_vector=feature_vector,
        sequence=sequence,
        history_days=history_days,
    )

    # Augment with extra info
    prediction["features"] = features
    prediction["horizon"] = horizon
    prediction["entity_id"] = str(entity_id)
    prediction["entity_type"] = entity_type

    # Map confidence level from calibrated_confidence
    prediction["confidence_level"] = _confidence_level(prediction["calibrated_confidence"])

    # Estimate predicted score change based on probability and current composite
    current_composite = features.get("peak_composite_score_ever", 0.0)
    latest_composite = features.get(
        "spotify_score_7d_avg",
        features.get("peak_composite_score_ever", 50.0),
    )
    horizon_days = {"7d": 7, "30d": 30, "90d": 90}.get(horizon, 7)
    prob = prediction["probability"]
    # Higher probability -> expect larger positive change
    predicted_change = (prob - 0.5) * 20.0 * (horizon_days / 7.0)
    prediction["predicted_score_change"] = round(predicted_change, 2)

    return prediction


# ── Batch prediction ─────────────────────────────────────────────────


async def batch_predict(
    db: AsyncSession,
    entity_ids: list[tuple[uuid.UUID, str]],
    horizon: str = "7d",
    redis=None,
) -> list[dict]:
    """Generate predictions for multiple entities.

    Args:
        db: database session
        entity_ids: list of (entity_id, entity_type) tuples
        horizon: prediction horizon
        redis: optional Redis client for caching

    Returns:
        list of prediction dicts (skips entities with insufficient data)
    """
    results = []

    for entity_id, entity_type in entity_ids:
        cache_key = f"ml:prediction:{entity_id}:{entity_type}:{horizon}"

        # Check cache
        if redis is not None:
            try:
                cached = await redis.get(cache_key)
                if cached:
                    results.append(json.loads(cached))
                    continue
            except Exception:
                pass  # Redis failure is non-fatal

        prediction = await predict_entity(db, entity_id, entity_type, horizon)
        if prediction is None:
            continue

        # Strip non-serializable items for caching
        cache_safe = {
            k: v for k, v in prediction.items()
            if k != "features"  # features dict can be large
        }

        # Cache result
        if redis is not None:
            try:
                await redis.set(
                    cache_key,
                    json.dumps(cache_safe, default=str),
                    ex=CACHE_TTL_SECONDS,
                )
            except Exception:
                pass  # Redis failure is non-fatal

        results.append(prediction)

    return results


# ── Helpers ──────────────────────────────────────────────────────────

LSTM_SEQUENCE_LEN = 14


async def _build_sequence(
    db: AsyncSession,
    entity_id: uuid.UUID,
    entity_type: str,
    seq_len: int = LSTM_SEQUENCE_LEN,
) -> np.ndarray | None:
    """Build an LSTM input sequence of daily feature vectors.

    Returns shape (seq_len, n_features) or None if not enough data.
    """
    today = date.today()
    sequence = []

    for offset in range(seq_len - 1, -1, -1):
        as_of = today - timedelta(days=offset)
        features = await compute_features(db, entity_id, entity_type, as_of=as_of)
        if features is not None:
            sequence.append(features_to_vector(features))
        else:
            sequence.append([0.0] * len(FEATURE_NAMES))

    return np.array(sequence)


def _confidence_level(confidence: float) -> str:
    if confidence >= 0.75:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"
