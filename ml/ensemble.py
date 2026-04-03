"""Ridge meta-learner ensemble for SoundPulse prediction engine.

Combines predictions from LightGBM, LSTM, and XGBoost base models
using Ridge regression. Calibrates confidence via isotonic regression.

Handles missing models gracefully and provides a cold-start rule-based
fallback for entities with insufficient history.
"""

import logging
import pickle
from pathlib import Path

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import Ridge

logger = logging.getLogger(__name__)

# Base model availability flags
_LGBM_AVAILABLE = False
_LSTM_AVAILABLE = False
_XGB_AVAILABLE = False

try:
    from ml.models.lightgbm_model import LightGBMModel, LIGHTGBM_AVAILABLE

    _LGBM_AVAILABLE = LIGHTGBM_AVAILABLE
except ImportError:
    pass

try:
    from ml.models.lstm_model import LSTMModel, TORCH_AVAILABLE

    _LSTM_AVAILABLE = TORCH_AVAILABLE
except ImportError:
    pass

try:
    from ml.models.xgboost_model import XGBoostModel, XGBOOST_AVAILABLE

    _XGB_AVAILABLE = XGBOOST_AVAILABLE
except ImportError:
    pass


# Prediction labels
LABEL_BREAKOUT = "breakout"
LABEL_STEADY = "steady"
LABEL_DECLINING = "declining"

# Cold start thresholds
COLD_START_DAYS = 7
WARM_START_DAYS = 14


def _classify_prediction(probability: float) -> str:
    """Map a breakout probability to a human-readable label."""
    if probability >= 0.6:
        return LABEL_BREAKOUT
    if probability <= 0.3:
        return LABEL_DECLINING
    return LABEL_STEADY


class EnsemblePredictor:
    """Ridge meta-learner ensemble combining base model predictions.

    The ensemble:
    1. Collects predictions from all available base models.
    2. Passes them through a Ridge regression meta-learner.
    3. Calibrates the output via isotonic regression.
    4. Falls back to rule-based heuristics for cold-start entities.
    """

    def __init__(self, feature_names: list[str] | None = None):
        self.feature_names = feature_names
        self.meta_learner: Ridge | None = None
        self.calibrator: IsotonicRegression | None = None

        # Base models
        self.lgbm: "LightGBMModel | None" = None
        self.lstm: "LSTMModel | None" = None
        self.xgb: "XGBoostModel | None" = None

        # Track which models are active in this ensemble
        self.active_models: list[str] = []
        self.model_version = "ensemble-v1.0"

    def _init_base_models(self) -> None:
        """Initialize available base models."""
        if _LGBM_AVAILABLE and self.lgbm is None:
            try:
                self.lgbm = LightGBMModel(feature_names=self.feature_names)
            except ImportError:
                pass

        if _LSTM_AVAILABLE and self.lstm is None:
            try:
                self.lstm = LSTMModel()
            except ImportError:
                pass

        if _XGB_AVAILABLE and self.xgb is None:
            try:
                self.xgb = XGBoostModel(feature_names=self.feature_names)
            except ImportError:
                pass

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        sequences_train: np.ndarray | None = None,
        sequences_val: np.ndarray | None = None,
    ) -> dict[str, float]:
        """Train all base models and the meta-learner.

        Args:
            X_train: tabular features for train set (n_samples, n_features)
            y_train: binary labels (n_samples,)
            X_val: tabular features for validation set
            y_val: validation labels
            sequences_train: LSTM sequences for train (n_samples, seq_len, n_features)
            sequences_val: LSTM sequences for validation

        Returns:
            dict of training metrics from all models.
        """
        self._init_base_models()
        metrics: dict[str, float] = {}
        self.active_models = []

        # ── Train LightGBM ──
        if self.lgbm is not None:
            try:
                lgbm_metrics = self.lgbm.train(X_train, y_train, X_val, y_val)
                metrics.update({f"lgbm_{k}": v for k, v in lgbm_metrics.items()})
                self.active_models.append("lightgbm")
                logger.info("LightGBM trained successfully.")
            except Exception:
                logger.exception("LightGBM training failed.")
                self.lgbm = None

        # ── Train LSTM ──
        if self.lstm is not None and sequences_train is not None:
            try:
                lstm_metrics = self.lstm.train(
                    sequences_train, y_train, sequences_val, y_val
                )
                metrics.update({f"lstm_{k}": v for k, v in lstm_metrics.items()})
                self.active_models.append("lstm")
                logger.info("LSTM trained successfully.")
            except Exception:
                logger.exception("LSTM training failed.")
                self.lstm = None

        # ── Train XGBoost (with interaction features) ──
        if self.xgb is not None:
            try:
                # Pass LightGBM importances for interaction feature selection
                lgbm_importances = (
                    self.lgbm.feature_importances_ if self.lgbm and self.lgbm.is_trained else None
                )
                xgb_metrics = self.xgb.train(
                    X_train, y_train, X_val, y_val,
                    precomputed_importances=lgbm_importances,
                )
                metrics.update({f"xgb_{k}": v for k, v in xgb_metrics.items()})
                self.active_models.append("xgboost")
                logger.info("XGBoost trained successfully.")
            except Exception:
                logger.exception("XGBoost training failed.")
                self.xgb = None

        if not self.active_models:
            logger.warning("No base models trained successfully.")
            return metrics

        # ── Collect base model predictions on validation set ──
        base_preds = self._collect_base_predictions(X_val, sequences_val)
        if base_preds.shape[1] == 0:
            logger.warning("No base model predictions available for meta-learner.")
            return metrics

        # ── Train Ridge meta-learner ──
        self.meta_learner = Ridge(alpha=1.0)
        self.meta_learner.fit(base_preds, y_val)
        meta_preds = self.meta_learner.predict(base_preds)
        meta_preds = np.clip(meta_preds, 0, 1)
        logger.info(
            "Ridge meta-learner trained on %d models: %s",
            len(self.active_models),
            self.active_models,
        )

        # ── Train isotonic calibrator ──
        self.calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
        self.calibrator.fit(meta_preds, y_val)
        logger.info("Isotonic calibrator trained.")

        # Log weights
        weights = dict(zip(self.active_models, self.meta_learner.coef_))
        logger.info("Meta-learner weights: %s", weights)
        metrics["meta_learner_intercept"] = float(self.meta_learner.intercept_)
        for name, w in weights.items():
            metrics[f"meta_weight_{name}"] = float(w)

        return metrics

    def _collect_base_predictions(
        self,
        X: np.ndarray,
        sequences: np.ndarray | None = None,
    ) -> np.ndarray:
        """Collect predictions from all trained base models into a matrix."""
        preds_list: list[np.ndarray] = []

        if self.lgbm is not None and self.lgbm.is_trained:
            preds_list.append(self.lgbm.predict(X))

        if self.lstm is not None and self.lstm.is_trained and sequences is not None:
            preds_list.append(self.lstm.predict(sequences))

        if self.xgb is not None and self.xgb.is_trained:
            preds_list.append(self.xgb.predict(X))

        if not preds_list:
            return np.empty((len(X), 0))

        return np.column_stack(preds_list)

    def predict(
        self,
        features: dict[str, float],
        feature_vector: list[float] | None = None,
        sequence: np.ndarray | None = None,
        history_days: int = 30,
    ) -> dict:
        """Generate a prediction for a single entity.

        Args:
            features: raw feature dict from feature engineering
            feature_vector: ordered numeric vector (if None, built from features)
            sequence: LSTM sequence array of shape (seq_len, n_features)
            history_days: how many days of history this entity has

        Returns:
            dict with keys: probability, calibrated_confidence, prediction_label,
            top_features, model_version, is_ml
        """
        # ── Cold start: use rule-based heuristics ──
        if history_days < COLD_START_DAYS:
            return self._cold_start_prediction(features, history_days)

        # ── Warm prediction: use ensemble if available ──
        if not self.active_models or self.meta_learner is None:
            return self._cold_start_prediction(features, history_days)

        if feature_vector is None:
            from ml.features import FEATURE_NAMES as fn, features_to_vector

            feature_vector = features_to_vector(features)

        X = np.array([feature_vector])
        seq = sequence[np.newaxis, :, :] if sequence is not None else None

        base_preds = self._collect_base_predictions(X, seq)
        if base_preds.shape[1] == 0:
            return self._cold_start_prediction(features, history_days)

        # Meta-learner prediction
        raw_prob = float(np.clip(self.meta_learner.predict(base_preds)[0], 0, 1))

        # Calibrate confidence
        if self.calibrator is not None:
            calibrated = float(self.calibrator.predict([raw_prob])[0])
        else:
            calibrated = raw_prob

        # Apply confidence discount for warm-start entities (7-14 days)
        if history_days < WARM_START_DAYS:
            max_conf = 0.7
            calibrated = min(calibrated, max_conf)

        # Collect top contributing features
        top_features = self._get_top_features(features)

        # Derive per-target estimates from the single ensemble probability
        # These are rough approximations until per-target models are trained
        return {
            "predictions": {
                "billboard_hot_100": {
                    "probability": round(raw_prob * 0.85, 4),
                    "horizon": "14d",
                    "label": "Billboard Hot 100",
                },
                "spotify_top_50_us": {
                    "probability": round(raw_prob, 4),
                    "horizon": "7d",
                    "label": "Spotify Top 50 US",
                },
                "shazam_top_200_us": {
                    "probability": round(min(raw_prob * 1.1, 0.99), 4),
                    "horizon": "7d",
                    "label": "Shazam Top 200 US",
                },
                "cross_platform_breakout": {
                    "probability": round(raw_prob * 0.7, 4),
                    "horizon": "14d",
                    "label": "3+ US Platform Breakout",
                },
            },
            "probability": round(raw_prob, 4),
            "calibrated_confidence": round(calibrated, 4),
            "prediction_label": _classify_prediction(raw_prob),
            "top_features": top_features,
            "model_version": self.model_version,
            "is_ml": True,
            "active_models": list(self.active_models),
        }

    def _cold_start_prediction(self, features: dict[str, float], history_days: int) -> dict:
        """Rule-based fallback for entities with insufficient history.

        Produces 4 US-market prediction targets:
          - billboard_hot_100: radio rank + velocity
          - spotify_top_50_us: spotify rank + velocity
          - shazam_top_200_us: shazam presence + discovery signals
          - cross_platform_breakout: platform_count + velocity across platforms
        """
        velocity = features.get("spotify_velocity_7d", 0.0)
        # Also check aggregate velocity across platforms
        platform_velocities = []
        for p in ["spotify", "tiktok", "apple_music", "shazam"]:
            v = features.get(f"{p}_velocity_7d", 0.0)
            if v != 0.0:
                platform_velocities.append(v)
        if platform_velocities:
            velocity = max(velocity, max(platform_velocities))

        cross_platform = features.get("platform_count", 0.0)
        genre_momentum = features.get("genre_overall_momentum", 0.0)
        current_streak = features.get("current_streak_days", 0.0)

        # Score components
        velocity_score = min(max(velocity / 5.0, -1.0), 1.0)
        platform_score = min(cross_platform / 6.0, 1.0)
        genre_score = min(max(genre_momentum / 3.0, -0.5), 0.5)
        streak_score = min(current_streak / 7.0, 1.0)

        raw_prob = (
            0.35 * velocity_score
            + 0.30 * platform_score
            + 0.20 * genre_score
            + 0.15 * streak_score
        )
        raw_prob = min(max(raw_prob, 0.01), 0.99)

        # Per-target probabilities using different weightings
        billboard_prob = min(max(
            0.35 * velocity_score + 0.30 * platform_score + 0.20 * genre_score + 0.15 * streak_score,
            0.01), 0.99)
        spotify_prob = min(max(
            0.40 * velocity_score + 0.25 * platform_score + 0.20 * streak_score + 0.15 * genre_score,
            0.01), 0.99)
        shazam_prob = min(max(
            0.30 * velocity_score + 0.30 * genre_score + 0.25 * streak_score + 0.15 * platform_score,
            0.01), 0.99)
        cross_prob = min(max(
            0.45 * platform_score + 0.30 * velocity_score + 0.15 * genre_score + 0.10 * streak_score,
            0.01), 0.99)

        # Cap confidence for cold start
        max_conf = 0.5 if history_days < COLD_START_DAYS else 0.7
        confidence = min(abs(raw_prob - 0.5) * 2, max_conf)

        top_features = [
            {"feature": "velocity", "value": round(velocity, 4), "impact": _impact_label(velocity_score)},
            {"feature": "platform_count", "value": cross_platform, "impact": _impact_label(platform_score)},
            {"feature": "genre_momentum", "value": round(genre_momentum, 4), "impact": _impact_label(genre_score)},
        ]
        top_features.sort(key=lambda x: abs(x["value"]), reverse=True)

        return {
            "predictions": {
                "billboard_hot_100": {
                    "probability": round(billboard_prob, 4),
                    "horizon": "14d",
                    "label": "Billboard Hot 100",
                },
                "spotify_top_50_us": {
                    "probability": round(spotify_prob, 4),
                    "horizon": "7d",
                    "label": "Spotify Top 50 US",
                },
                "shazam_top_200_us": {
                    "probability": round(shazam_prob, 4),
                    "horizon": "7d",
                    "label": "Shazam Top 200 US",
                },
                "cross_platform_breakout": {
                    "probability": round(cross_prob, 4),
                    "horizon": "14d",
                    "label": "3+ US Platform Breakout",
                },
            },
            "probability": round(raw_prob, 4),
            "calibrated_confidence": round(confidence, 4),
            "prediction_label": _classify_prediction(raw_prob),
            "top_features": top_features[:3],
            "model_version": "rule-based-v2-us",
            "is_ml": False,
            "active_models": [],
        }

    def _get_top_features(self, features: dict[str, float], top_n: int = 5) -> list[dict]:
        """Extract top contributing features from the ensemble.

        Combines feature importances from all base models.
        """
        combined_importance: dict[str, float] = {}

        if self.lgbm is not None and self.lgbm.is_trained:
            for name, imp in self.lgbm.feature_importances_.items():
                combined_importance[name] = combined_importance.get(name, 0.0) + imp

        if self.xgb is not None and self.xgb.is_trained:
            for name, imp in self.xgb.feature_importances_.items():
                # Skip interaction features for readability
                if "_x_" not in name:
                    combined_importance[name] = combined_importance.get(name, 0.0) + imp

        sorted_features = sorted(combined_importance.items(), key=lambda x: x[1], reverse=True)

        result = []
        for name, importance in sorted_features[:top_n]:
            value = features.get(name, 0.0)
            result.append({
                "feature": name,
                "value": round(value, 4),
                "impact": _importance_label(importance, combined_importance),
            })
        return result

    def save(self, directory: str | Path) -> None:
        """Save the full ensemble to a directory."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        # Save meta-learner and calibrator
        with open(directory / "meta_learner.pkl", "wb") as f:
            pickle.dump(
                {
                    "meta_learner": self.meta_learner,
                    "calibrator": self.calibrator,
                    "active_models": self.active_models,
                    "model_version": self.model_version,
                    "feature_names": self.feature_names,
                },
                f,
            )

        # Save base models
        if self.lgbm is not None and self.lgbm.is_trained:
            self.lgbm.save(directory / "lightgbm.pkl")
        if self.lstm is not None and self.lstm.is_trained:
            self.lstm.save(directory / "lstm.pkl")
        if self.xgb is not None and self.xgb.is_trained:
            self.xgb.save(directory / "xgboost.pkl")

        logger.info("Ensemble saved to %s", directory)

    def load(self, directory: str | Path) -> None:
        """Load the full ensemble from a directory."""
        directory = Path(directory)

        if not (directory / "meta_learner.pkl").exists():
            logger.warning("No meta_learner.pkl found in %s", directory)
            return

        with open(directory / "meta_learner.pkl", "rb") as f:
            data = pickle.load(f)

        self.meta_learner = data.get("meta_learner")
        self.calibrator = data.get("calibrator")
        self.active_models = data.get("active_models", [])
        self.model_version = data.get("model_version", "ensemble-v1.0")
        self.feature_names = data.get("feature_names")

        # Load base models
        if "lightgbm" in self.active_models and _LGBM_AVAILABLE:
            lgbm_path = directory / "lightgbm.pkl"
            if lgbm_path.exists():
                try:
                    self.lgbm = LightGBMModel(feature_names=self.feature_names)
                    self.lgbm.load(lgbm_path)
                except Exception:
                    logger.exception("Failed to load LightGBM model.")
                    self.lgbm = None

        if "lstm" in self.active_models and _LSTM_AVAILABLE:
            lstm_path = directory / "lstm.pkl"
            if lstm_path.exists():
                try:
                    self.lstm = LSTMModel()
                    self.lstm.load(lstm_path)
                except Exception:
                    logger.exception("Failed to load LSTM model.")
                    self.lstm = None

        if "xgboost" in self.active_models and _XGB_AVAILABLE:
            xgb_path = directory / "xgboost.pkl"
            if xgb_path.exists():
                try:
                    self.xgb = XGBoostModel(feature_names=self.feature_names)
                    self.xgb.load(xgb_path)
                except Exception:
                    logger.exception("Failed to load XGBoost model.")
                    self.xgb = None

        logger.info(
            "Ensemble loaded from %s. Active models: %s",
            directory,
            self.active_models,
        )

    @property
    def is_trained(self) -> bool:
        return self.meta_learner is not None and len(self.active_models) > 0


# ── Helpers ──────────────────────────────────────────────────────────


def _impact_label(score: float) -> str:
    if score >= 0.5:
        return "positive"
    if score <= -0.3:
        return "negative"
    return "neutral"


def _importance_label(
    importance: float, all_importances: dict[str, float]
) -> str:
    """Relative importance label based on distribution."""
    if not all_importances:
        return "medium"
    max_imp = max(all_importances.values())
    if max_imp == 0:
        return "medium"
    relative = importance / max_imp
    if relative >= 0.5:
        return "high"
    if relative >= 0.2:
        return "medium"
    return "low"
