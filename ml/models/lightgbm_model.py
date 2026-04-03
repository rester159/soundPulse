"""LightGBM base model for SoundPulse prediction engine.

Binary classification: will this entity reach top 20 within N days?
Hyperparameters tuned for music trending data.
"""

import logging
import pickle
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

try:
    import lightgbm as lgb

    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    logger.warning("lightgbm not installed. LightGBM model will be unavailable.")


class LightGBMModel:
    """LightGBM binary classifier for trending prediction."""

    name = "lightgbm"

    def __init__(self, feature_names: list[str] | None = None):
        if not LIGHTGBM_AVAILABLE:
            raise ImportError("lightgbm is required but not installed.")

        self.model: Any = None
        self.feature_names = feature_names
        self.feature_importances_: dict[str, float] = {}

        # Hyperparameters tuned for music data
        self.params = {
            "objective": "binary",
            "metric": "binary_logloss",
            "boosting_type": "gbdt",
            "learning_rate": 0.05,
            "num_leaves": 63,
            "min_data_in_leaf": 20,
            "max_depth": -1,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "lambda_l1": 0.1,
            "lambda_l2": 0.1,
            "verbose": -1,
            "n_jobs": -1,
            "seed": 42,
        }
        self.num_boost_round = 300
        self.early_stopping_rounds = 30

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray | None = None,
        y_val: np.ndarray | None = None,
    ) -> dict[str, float]:
        """Train the LightGBM model.

        Returns a dict of training metrics.
        """
        train_data = lgb.Dataset(
            X_train, label=y_train, feature_name=self.feature_names, free_raw_data=False
        )

        callbacks = [lgb.log_evaluation(period=50)]
        valid_sets = [train_data]
        valid_names = ["train"]

        if X_val is not None and y_val is not None:
            val_data = lgb.Dataset(
                X_val, label=y_val, feature_name=self.feature_names, free_raw_data=False
            )
            valid_sets.append(val_data)
            valid_names.append("valid")
            callbacks.append(lgb.early_stopping(self.early_stopping_rounds, verbose=True))

        self.model = lgb.train(
            self.params,
            train_data,
            num_boost_round=self.num_boost_round,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=callbacks,
        )

        # Store feature importances
        if self.feature_names:
            importances = self.model.feature_importance(importance_type="gain")
            self.feature_importances_ = dict(zip(self.feature_names, importances))
        else:
            importances = self.model.feature_importance(importance_type="gain")
            self.feature_importances_ = {
                f"feature_{i}": float(v) for i, v in enumerate(importances)
            }

        metrics: dict[str, float] = {
            "best_iteration": float(self.model.best_iteration or self.num_boost_round),
        }
        if self.model.best_score:
            for ds_name, ds_metrics in self.model.best_score.items():
                for metric_name, value in ds_metrics.items():
                    metrics[f"{ds_name}_{metric_name}"] = value

        logger.info("LightGBM training complete. Best iteration: %s", metrics.get("best_iteration"))
        return metrics

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Return probability of positive class (breakout)."""
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")
        return self.model.predict(X, num_iteration=self.model.best_iteration)

    def get_feature_importance(self, top_n: int = 10) -> list[tuple[str, float]]:
        """Return top-N features by importance (gain)."""
        sorted_feats = sorted(
            self.feature_importances_.items(), key=lambda x: x[1], reverse=True
        )
        return sorted_feats[:top_n]

    def save(self, path: str | Path) -> None:
        """Save model to disk."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(
                {
                    "model": self.model,
                    "feature_names": self.feature_names,
                    "feature_importances": self.feature_importances_,
                    "params": self.params,
                },
                f,
            )
        logger.info("LightGBM model saved to %s", path)

    def load(self, path: str | Path) -> None:
        """Load model from disk."""
        path = Path(path)
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.model = data["model"]
        self.feature_names = data.get("feature_names")
        self.feature_importances_ = data.get("feature_importances", {})
        self.params = data.get("params", self.params)
        logger.info("LightGBM model loaded from %s", path)

    @property
    def is_trained(self) -> bool:
        return self.model is not None
