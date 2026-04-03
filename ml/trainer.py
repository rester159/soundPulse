"""Daily training loop for the SoundPulse prediction engine.

Pulls training data from the database, creates labels, trains all base
models + ensemble, evaluates, and saves to ml/saved_models/.

Can be run as: python -m ml.trainer
"""

import asyncio
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from ml.ensemble import EnsemblePredictor
from ml.features import (
    FEATURE_NAMES,
    compute_features,
    did_reach_top_n,
    features_to_vector,
    get_entities_with_history,
)

logger = logging.getLogger(__name__)

SAVED_MODELS_DIR = Path(__file__).resolve().parent / "saved_models"
MIN_SAMPLES = 30
LSTM_SEQ_LEN = 14


# ── Data collection ──────────────────────────────────────────────────


async def collect_training_data(
    min_history_days: int = 30,
    label_horizon_days: int = 14,
    top_n: int = 20,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, list[date]]:
    """Pull feature vectors, sequences, labels, and dates from the database.

    For each entity with enough history, we compute features at multiple
    cutoff dates and check whether the entity reached top-N within
    label_horizon_days after each cutoff.

    Returns:
        X: tabular features (n_samples, n_features)
        y: binary labels (n_samples,)
        sequences: LSTM sequences (n_samples, seq_len, n_features) or None
        sample_dates: list of cutoff dates used per sample
    """
    from api.database import async_session_factory

    X_rows: list[list[float]] = []
    y_rows: list[int] = []
    seq_rows: list[np.ndarray] = []
    sample_dates: list[date] = []

    async with async_session_factory() as db:
        entities = await get_entities_with_history(db, min_days=min_history_days)
        logger.info("Found %d entities with >=%d days of history.", len(entities), min_history_days)

        if not entities:
            return np.array([]), np.array([]), None, []

        today = date.today()

        for ent in entities:
            entity_id = ent["entity_id"]
            entity_type = ent["entity_type"]
            day_count = ent["day_count"]

            # Generate multiple training samples per entity by using
            # different cutoff dates (every 7 days going back).
            # This creates more training data from limited entities.
            max_lookback = min(day_count - label_horizon_days, 180)
            if max_lookback < label_horizon_days:
                max_lookback = label_horizon_days

            cutoff_offsets = list(range(label_horizon_days, max_lookback, 7))
            if not cutoff_offsets:
                cutoff_offsets = [label_horizon_days]

            for offset in cutoff_offsets:
                cutoff = today - timedelta(days=offset)

                features = await compute_features(db, entity_id, entity_type, as_of=cutoff)
                if features is None:
                    continue

                label = await did_reach_top_n(
                    db, entity_id, entity_type,
                    after_date=cutoff,
                    within_days=label_horizon_days,
                    top_n=top_n,
                )

                vector = features_to_vector(features)
                X_rows.append(vector)
                y_rows.append(int(label))
                sample_dates.append(cutoff)

                # Build LSTM sequence: feature vectors for past LSTM_SEQ_LEN days
                sequence = []
                for seq_offset in range(LSTM_SEQ_LEN - 1, -1, -1):
                    seq_date = cutoff - timedelta(days=seq_offset)
                    seq_features = await compute_features(
                        db, entity_id, entity_type, as_of=seq_date
                    )
                    if seq_features is not None:
                        sequence.append(features_to_vector(seq_features))
                    else:
                        # Pad with zeros for missing days
                        sequence.append([0.0] * len(FEATURE_NAMES))

                seq_rows.append(np.array(sequence))

    X = np.array(X_rows) if X_rows else np.array([])
    y = np.array(y_rows) if y_rows else np.array([])
    sequences = np.array(seq_rows) if seq_rows else None

    return X, y, sequences, sample_dates


# ── Training ─────────────────────────────────────────────────────────


def train_ensemble(
    X: np.ndarray,
    y: np.ndarray,
    sequences: np.ndarray | None,
    sample_dates: list[date],
) -> tuple[EnsemblePredictor, dict]:
    """Train the full ensemble with temporal train/test split.

    Uses 80/20 temporal split: train on older data, test on recent.

    Returns:
        ensemble: trained EnsemblePredictor
        metrics: evaluation metrics dict
    """
    # Temporal split: sort by date, use oldest 80% for train
    date_order = np.argsort([d.toordinal() for d in sample_dates])
    split_idx = int(len(date_order) * 0.8)

    train_idx = date_order[:split_idx]
    test_idx = date_order[split_idx:]

    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    seq_train = sequences[train_idx] if sequences is not None else None
    seq_test = sequences[test_idx] if sequences is not None else None

    logger.info(
        "Train/test split: %d train, %d test (%.1f%% positive overall)",
        len(X_train), len(X_test), 100 * y.mean(),
    )

    # Train ensemble
    ensemble = EnsemblePredictor(feature_names=FEATURE_NAMES)
    train_metrics = ensemble.train(
        X_train, y_train, X_test, y_test,
        sequences_train=seq_train,
        sequences_val=seq_test,
    )

    # ── Evaluate on test set ──
    eval_metrics = evaluate_ensemble(ensemble, X_test, y_test, seq_test)
    eval_metrics.update(train_metrics)
    eval_metrics["train_size"] = len(X_train)
    eval_metrics["test_size"] = len(X_test)
    eval_metrics["positive_rate"] = round(float(y.mean()), 4)
    eval_metrics["active_models"] = ensemble.active_models

    return ensemble, eval_metrics


def evaluate_ensemble(
    ensemble: EnsemblePredictor,
    X_test: np.ndarray,
    y_test: np.ndarray,
    sequences_test: np.ndarray | None,
) -> dict:
    """Evaluate the ensemble on a test set."""
    predictions = []
    for i in range(len(X_test)):
        seq = sequences_test[i] if sequences_test is not None else None
        pred = ensemble.predict(
            features={name: float(X_test[i, j]) for j, name in enumerate(FEATURE_NAMES)},
            feature_vector=list(X_test[i]),
            sequence=seq,
            history_days=30,  # assume enough history for test data
        )
        predictions.append(pred["probability"])

    probs = np.array(predictions)
    y_pred = (probs >= 0.5).astype(int)

    metrics: dict = {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
    }

    # AUC-ROC (only if both classes present)
    if len(set(y_test)) > 1:
        metrics["auc_roc"] = round(roc_auc_score(y_test, probs), 4)
    else:
        metrics["auc_roc"] = None

    logger.info("Evaluation metrics: %s", metrics)
    logger.info(
        "Classification report:\n%s",
        classification_report(y_test, y_pred, zero_division=0),
    )

    return metrics


# ── Save / Load ──────────────────────────────────────────────────────


def save_ensemble(ensemble: EnsemblePredictor, metrics: dict) -> Path:
    """Save ensemble and metrics to saved_models directory."""
    SAVED_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    ensemble.save(SAVED_MODELS_DIR)

    # Also save metrics
    import json

    metrics_path = SAVED_MODELS_DIR / "metrics.json"
    serializable = {}
    for k, v in metrics.items():
        if isinstance(v, (list, dict, str, int, float, bool, type(None))):
            serializable[k] = v
        else:
            serializable[k] = str(v)

    with open(metrics_path, "w") as f:
        json.dump(serializable, f, indent=2, default=str)

    logger.info("Ensemble and metrics saved to %s", SAVED_MODELS_DIR)
    return SAVED_MODELS_DIR


# ── Entry point ──────────────────────────────────────────────────────


async def run_training() -> dict | None:
    """Top-level async entry point. Returns metrics dict or None on cold-start."""
    logger.info("Starting advanced prediction engine training pipeline...")

    X, y, sequences, sample_dates = await collect_training_data()

    if X.size == 0 or len(X) < MIN_SAMPLES:
        logger.warning(
            "Not enough training data (%d samples, need %d). "
            "Skipping model training -- the rule-based fallback will be used.",
            len(X) if X.size else 0,
            MIN_SAMPLES,
        )
        return None

    logger.info(
        "Collected %d samples (%.1f%% positive) across %d unique dates.",
        len(X),
        100 * y.mean(),
        len(set(sample_dates)),
    )

    ensemble, metrics = train_ensemble(X, y, sequences, sample_dates)
    save_ensemble(ensemble, metrics)

    logger.info(
        "Training complete. Active models: %s",
        metrics.get("active_models", []),
    )
    return metrics


def main():
    """Synchronous CLI wrapper."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s -- %(message)s",
    )

    metrics = asyncio.run(run_training())
    if metrics is None:
        logger.info("No model was trained (cold-start). Exiting.")
        sys.exit(0)

    print("\n=== SoundPulse Prediction Engine - Evaluation Metrics ===")
    print(f"  Active Models: {metrics.get('active_models', [])}")
    print(f"  Accuracy:      {metrics.get('accuracy', 'N/A')}")
    print(f"  Precision:     {metrics.get('precision', 'N/A')}")
    print(f"  Recall:        {metrics.get('recall', 'N/A')}")
    print(f"  F1 Score:      {metrics.get('f1', 'N/A')}")
    print(f"  AUC-ROC:       {metrics.get('auc_roc', 'N/A')}")
    print(f"  Train Size:    {metrics.get('train_size', 'N/A')}")
    print(f"  Test Size:     {metrics.get('test_size', 'N/A')}")
    print(f"  Positive Rate: {metrics.get('positive_rate', 'N/A')}")
    print()


if __name__ == "__main__":
    main()
