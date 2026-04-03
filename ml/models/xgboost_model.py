"""XGBoost model with interaction features for SoundPulse prediction engine.

Generates pairwise interaction features from the top-10 most important
features and runs binary classification.

Gracefully handles the case where xgboost is not installed.
"""

import logging
import pickle
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

try:
    import xgboost as xgb

    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("xgboost not installed. XGBoost model will be unavailable.")


class XGBoostModel:
    """XGBoost binary classifier with pairwise interaction features."""

    name = "xgboost"

    def __init__(self, feature_names: list[str] | None = None):
        if not XGBOOST_AVAILABLE:
            raise ImportError("xgboost is required but not installed.")

        self.model: Any = None
        self.feature_names = feature_names
        self.feature_importances_: dict[str, float] = {}
        self.top_interaction_indices: list[tuple[int, int]] = []
        self.interaction_feature_names: list[str] = []
        self.all_feature_names: list[str] = []

        self.params = {
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "learning_rate": 0.05,
            "max_depth": 6,
            "min_child_weight": 5,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_alpha": 0.1,
            "reg_lambda": 1.0,
            "seed": 42,
            "n_jobs": -1,
            "verbosity": 0,
        }
        self.num_boost_round = 300
        self.early_stopping_rounds = 30

    def _generate_interaction_features(
        self, X: np.ndarray, top_indices: list[int] | None = None
    ) -> np.ndarray:
        """Generate pairwise interaction features from top-N feature columns.

        If top_indices is None, uses the first 10 columns.
        Returns X augmented with interaction columns.
        """
        if top_indices is None:
            n_features = min(10, X.shape[1])
            top_indices = list(range(n_features))

        interactions = []
        interaction_names = []

        for i in range(len(top_indices)):
            for j in range(i + 1, len(top_indices)):
                idx_i, idx_j = top_indices[i], top_indices[j]
                # Multiplication interaction
                interactions.append(X[:, idx_i] * X[:, idx_j])
                name_i = self.feature_names[idx_i] if self.feature_names else f"f{idx_i}"
                name_j = self.feature_names[idx_j] if self.feature_names else f"f{idx_j}"
                interaction_names.append(f"{name_i}_x_{name_j}")

        self.top_interaction_indices = [
            (top_indices[i], top_indices[j])
            for i in range(len(top_indices))
            for j in range(i + 1, len(top_indices))
        ]
        self.interaction_feature_names = interaction_names

        if interactions:
            interaction_matrix = np.column_stack(interactions)
            return np.hstack([X, interaction_matrix])
        return X

    def _apply_interactions(self, X: np.ndarray) -> np.ndarray:
        """Apply pre-computed interaction pairs to new data."""
        if not self.top_interaction_indices:
            return X

        interactions = []
        for idx_i, idx_j in self.top_interaction_indices:
            if idx_i < X.shape[1] and idx_j < X.shape[1]:
                interactions.append(X[:, idx_i] * X[:, idx_j])

        if interactions:
            interaction_matrix = np.column_stack(interactions)
            return np.hstack([X, interaction_matrix])
        return X

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray | None = None,
        y_val: np.ndarray | None = None,
        precomputed_importances: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """Train XGBoost with interaction features.

        If precomputed_importances is provided (e.g. from a LightGBM model),
        use those to select the top-10 features for interaction generation.
        """
        # Determine top features for interaction generation
        if precomputed_importances and self.feature_names:
            sorted_feats = sorted(
                precomputed_importances.items(), key=lambda x: x[1], reverse=True
            )
            top_names = [name for name, _ in sorted_feats[:10]]
            top_indices = [
                self.feature_names.index(name)
                for name in top_names
                if name in self.feature_names
            ]
        else:
            top_indices = list(range(min(10, X_train.shape[1])))

        # Generate interaction features
        X_train_aug = self._generate_interaction_features(X_train, top_indices)

        # Build full feature name list
        base_names = self.feature_names or [f"f{i}" for i in range(X_train.shape[1])]
        self.all_feature_names = list(base_names) + self.interaction_feature_names

        dtrain = xgb.DMatrix(X_train_aug, label=y_train, feature_names=self.all_feature_names)

        evals = [(dtrain, "train")]
        if X_val is not None and y_val is not None:
            X_val_aug = self._apply_interactions(X_val)
            dval = xgb.DMatrix(X_val_aug, label=y_val, feature_names=self.all_feature_names)
            evals.append((dval, "valid"))

        self.model = xgb.train(
            self.params,
            dtrain,
            num_boost_round=self.num_boost_round,
            evals=evals,
            early_stopping_rounds=self.early_stopping_rounds,
            verbose_eval=50,
        )

        # Store feature importances
        importance = self.model.get_score(importance_type="gain")
        self.feature_importances_ = {
            k: float(v) for k, v in importance.items()
        }

        metrics: dict[str, float] = {
            "best_iteration": float(self.model.best_iteration),
            "best_score": float(self.model.best_score),
        }

        logger.info(
            "XGBoost training complete. Best iteration: %d, interactions: %d",
            self.model.best_iteration,
            len(self.interaction_feature_names),
        )
        return metrics

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Return probability of positive class."""
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")

        X_aug = self._apply_interactions(X)
        dmatrix = xgb.DMatrix(X_aug, feature_names=self.all_feature_names)
        return self.model.predict(dmatrix, iteration_range=(0, self.model.best_iteration + 1))

    def get_feature_importance(self, top_n: int = 10) -> list[tuple[str, float]]:
        """Return top-N features by importance (gain)."""
        sorted_feats = sorted(
            self.feature_importances_.items(), key=lambda x: x[1], reverse=True
        )
        return sorted_feats[:top_n]

    def save(self, path: str | Path) -> None:
        """Save model + interaction config to disk."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(
                {
                    "model": self.model,
                    "feature_names": self.feature_names,
                    "feature_importances": self.feature_importances_,
                    "top_interaction_indices": self.top_interaction_indices,
                    "interaction_feature_names": self.interaction_feature_names,
                    "all_feature_names": self.all_feature_names,
                    "params": self.params,
                },
                f,
            )
        logger.info("XGBoost model saved to %s", path)

    def load(self, path: str | Path) -> None:
        """Load model from disk."""
        path = Path(path)
        with open(path, "rb") as f:
            data = pickle.load(f)

        self.model = data["model"]
        self.feature_names = data.get("feature_names")
        self.feature_importances_ = data.get("feature_importances", {})
        self.top_interaction_indices = data.get("top_interaction_indices", [])
        self.interaction_feature_names = data.get("interaction_feature_names", [])
        self.all_feature_names = data.get("all_feature_names", [])
        self.params = data.get("params", self.params)
        logger.info("XGBoost model loaded from %s", path)

    @property
    def is_trained(self) -> bool:
        return self.model is not None
