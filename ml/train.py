"""Model training pipeline for the SoundPulse trending predictor.

Binary classification: will this entity reach the top-20 within 14 days?

Usage (from project root):
    python -m ml.train            # uses DATABASE_URL from .env
    python -m scripts.train_model # convenience wrapper
"""

import asyncio
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("ml.train")

MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_PATH = MODEL_DIR / "trending_predictor.joblib"

MIN_SAMPLES = 30  # minimum rows needed to attempt training


# ── Data collection ──────────────────────────────────────────────────

async def _collect_training_data() -> tuple[np.ndarray, np.ndarray]:
    """Pull feature vectors and labels from the database.

    For each entity with enough history we:
      1. Compute features as of a *cutoff_date* (14 days before its latest snapshot).
      2. Label = 1 if the entity reached top-20 in the 14 days after the cutoff.
    """
    # Lazy imports so module-level doesn't require a running DB.
    from sqlalchemy.ext.asyncio import AsyncSession

    from api.database import async_session_factory
    from api.services.feature_engineering import (
        FEATURE_NAMES,
        did_reach_top_n,
        features_to_vector,
        get_entities_with_history,
        get_entity_features,
    )

    X_rows: list[list[float]] = []
    y_rows: list[int] = []

    async with async_session_factory() as db:
        entities = await get_entities_with_history(db, min_days=14)
        logger.info("Found %d entities with >=14 days of history.", len(entities))

        if not entities:
            return np.array([]), np.array([])

        for ent in entities:
            entity_id = ent["entity_id"]
            entity_type = ent["entity_type"]

            # Use a cutoff 14 days before today so we can check the label.
            cutoff = date.today() - timedelta(days=14)

            features = await get_entity_features(db, entity_id, entity_type, as_of=cutoff)
            if features is None:
                continue

            label = await did_reach_top_n(
                db, entity_id, entity_type, after_date=cutoff, within_days=14, top_n=20
            )

            X_rows.append(features_to_vector(features))
            y_rows.append(int(label))

    return np.array(X_rows), np.array(y_rows)


# ── Training ─────────────────────────────────────────────────────────

def _train_model(X: np.ndarray, y: np.ndarray) -> dict:
    """Train a GradientBoosting classifier and save to disk.

    Returns a metrics dict.
    """
    from api.services.feature_engineering import FEATURE_NAMES

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y if len(set(y)) > 1 else None,
    )

    model = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        min_samples_split=5,
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    metrics = {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "positive_rate": round(float(y.mean()), 4),
    }

    # Feature importance
    importances = dict(zip(FEATURE_NAMES, model.feature_importances_))
    sorted_imp = sorted(importances.items(), key=lambda kv: kv[1], reverse=True)
    logger.info("Feature importances:")
    for name, imp in sorted_imp:
        logger.info("  %-25s %.4f", name, imp)

    logger.info("Classification report:\n%s", classification_report(y_test, y_pred, zero_division=0))

    # Persist
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    logger.info("Model saved to %s", MODEL_PATH)

    metrics["feature_importances"] = importances
    return metrics


# ── Entry point ──────────────────────────────────────────────────────

async def run_training() -> dict | None:
    """Top-level async entry point.  Returns metrics dict or None on cold-start."""
    logger.info("Starting training pipeline …")

    X, y = await _collect_training_data()

    if X.size == 0 or len(X) < MIN_SAMPLES:
        logger.warning(
            "Not enough training data (%d samples, need %d). "
            "Skipping model training — the rule-based fallback will be used.",
            len(X) if X.size else 0,
            MIN_SAMPLES,
        )
        return None

    logger.info("Collected %d samples (%.1f%% positive).", len(X), 100 * y.mean())
    metrics = _train_model(X, y)
    logger.info("Training complete. Metrics: %s", {k: v for k, v in metrics.items() if k != "feature_importances"})
    return metrics


def main():
    """Synchronous CLI wrapper."""
    metrics = asyncio.run(run_training())
    if metrics is None:
        logger.info("No model was trained (cold-start). Exiting.")
        sys.exit(0)

    print("\n═══ Evaluation Metrics ═══")
    print(f"  Accuracy:  {metrics['accuracy']}")
    print(f"  Precision: {metrics['precision']}")
    print(f"  Recall:    {metrics['recall']}")
    print(f"  F1 Score:  {metrics['f1']}")
    print(f"  Samples:   {metrics['train_size']} train / {metrics['test_size']} test")
    print(f"  Pos. rate: {metrics['positive_rate']}")
    print()


if __name__ == "__main__":
    main()
