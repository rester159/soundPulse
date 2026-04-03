# SoundPulse Prediction Engine — Testing & Iteration Plan (Claude Code Prompt)

> **Build the testing infrastructure, backtesting framework, shadow mode deployment, drift detection, and iteration roadmap for the SoundPulse prediction engine.**
> This is a companion to the main CLAUDE_CODE_PROMPT.md — run after the base prediction models exist.

---

## CONTEXT

The prediction engine is a 3-model ensemble (LightGBM + LSTM + XGBoost) combined via Ridge meta-learner, producing forecasts at 7d/30d/90d horizons. This prompt builds everything needed to know if the models are working, catch when they stop working, and systematically improve them.

---

## LAYER 1: UNIT TESTS

Test every component in isolation. These run on every commit.

### `tests/test_prediction/test_features.py`

```python
"""
Test feature engineering pipeline.
Every feature function must be tested with known inputs/outputs.
"""

class TestMomentumFeatures:
    def test_velocity_7d_uptrend(self):
        """Linear uptrend should produce positive velocity."""
        scores = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0]
        velocity = calculate_velocity(scores)
        assert velocity > 0
        assert abs(velocity - 10.0) < 0.1  # slope should be ~10/day
    
    def test_velocity_7d_flat(self):
        """Flat scores should produce ~0 velocity."""
        scores = [50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0]
        velocity = calculate_velocity(scores)
        assert abs(velocity) < 0.01
    
    def test_velocity_with_nulls(self):
        """Nulls should be interpolated, not crash."""
        scores = [10.0, None, 30.0, None, 50.0, None, 70.0]
        velocity = calculate_velocity(scores)
        assert velocity > 0
    
    def test_velocity_insufficient_data(self):
        """< 3 data points should return 0."""
        assert calculate_velocity([50.0, 60.0]) == 0.0
        assert calculate_velocity([]) == 0.0

    def test_acceleration(self):
        """Acceleration = change in velocity over time."""
        # Decelerating uptrend
        scores_week1 = [10, 20, 30, 40, 50, 60, 70]  # vel = 10
        scores_week2 = [70, 75, 80, 85, 90, 95, 100]  # vel = 5
        accel = calculate_acceleration(scores_week1, scores_week2)
        assert accel < 0  # decelerating

class TestCrossPlatformFeatures:
    def test_shazam_to_spotify_ratio(self):
        """Core leading indicator calculation."""
        platform_scores = {"shazam": 80.0, "spotify": 40.0}
        ratio = shazam_to_spotify_ratio(platform_scores)
        assert ratio == 2.0
    
    def test_shazam_to_spotify_ratio_no_spotify(self):
        """Missing Spotify data → None, not division by zero."""
        platform_scores = {"shazam": 80.0}
        ratio = shazam_to_spotify_ratio(platform_scores)
        assert ratio is None
    
    def test_platform_count(self):
        platform_scores = {"spotify": 80, "tiktok": 60, "shazam": 45}
        assert platform_count(platform_scores) == 3
    
    def test_cross_platform_velocity_alignment(self):
        """All platforms trending same direction → alignment near 1.0."""
        velocities = {"spotify": 5.0, "tiktok": 3.0, "shazam": 4.0}
        alignment = cross_platform_velocity_alignment(velocities)
        assert alignment > 0.9
    
    def test_cross_platform_velocity_misalignment(self):
        """Mixed directions → alignment near 0."""
        velocities = {"spotify": 5.0, "tiktok": -3.0, "shazam": 4.0}
        alignment = cross_platform_velocity_alignment(velocities)
        assert alignment < 0.5

class TestTikTokFeatures:
    def test_creator_tier_migration_rate(self):
        """Measure rate of macro creator adoption."""
        distribution_today = {"nano": 0.40, "micro": 0.25, "mid": 0.20, "macro": 0.10, "mega": 0.05}
        distribution_7d_ago = {"nano": 0.60, "micro": 0.25, "mid": 0.10, "macro": 0.04, "mega": 0.01}
        rate = creator_tier_migration_rate(distribution_today, distribution_7d_ago)
        assert rate > 0  # macro+mega share increased

class TestTemporalFeatures:
    def test_is_holiday_period(self):
        """Known holidays flagged correctly."""
        assert is_holiday_period(date(2026, 12, 25)) == True
        assert is_holiday_period(date(2026, 3, 15)) == False
    
    def test_season(self):
        assert get_season(date(2026, 1, 15)) == "Q1"
        assert get_season(date(2026, 7, 15)) == "Q3"

class TestGenreFeatures:
    def test_genre_overall_momentum(self, db_session):
        """Genre momentum = avg velocity of all trending entities in that genre."""
        # Seed: 3 entities in "electronic.house" with velocities [5, 10, 15]
        momentum = genre_overall_momentum("electronic.house", db_session)
        assert abs(momentum - 10.0) < 0.1

class TestFeaturePipeline:
    def test_full_feature_vector_shape(self, sample_entity):
        """Full pipeline produces expected number of features."""
        features = build_feature_vector(sample_entity)
        assert len(features) == 70  # expected feature count
        assert all(isinstance(v, (int, float, type(None))) for v in features.values())
    
    def test_no_data_leakage(self, sample_entity):
        """Features at time T should not include data from after T."""
        features_t = build_feature_vector(sample_entity, as_of=date(2026, 3, 14))
        # Verify no snapshot_date > 2026-03-14 was used
        assert features_t["_latest_data_date"] <= date(2026, 3, 14)
```

### `tests/test_prediction/test_models.py`

```python
"""
Test each base model and the ensemble.
"""

class TestLightGBMModel:
    def test_predict_shape(self, trained_lgbm, sample_features):
        """Prediction output is a single float."""
        pred = trained_lgbm.predict(sample_features)
        assert isinstance(pred, float)
        assert 0 <= pred <= 100
    
    def test_feature_importance_available(self, trained_lgbm):
        """Feature importance should be extractable for explainability."""
        importance = trained_lgbm.feature_importance()
        assert len(importance) == 70
        assert sum(importance.values()) > 0

class TestLSTMModel:
    def test_predict_with_sequence(self, trained_lstm, sample_sequence):
        """LSTM takes sequence of 30 daily feature snapshots."""
        pred = trained_lstm.predict(sample_sequence)
        assert isinstance(pred, float)
        assert 0 <= pred <= 100
    
    def test_attention_weights(self, trained_lstm, sample_sequence):
        """Attention weights should be extractable."""
        pred, attention = trained_lstm.predict_with_attention(sample_sequence)
        assert len(attention) == 30  # one weight per timestep
        assert abs(sum(attention) - 1.0) < 0.01  # should sum to ~1

class TestXGBoostModel:
    def test_predict_with_interactions(self, trained_xgb, sample_features_with_interactions):
        """XGBoost uses hand-crafted interaction features."""
        pred = trained_xgb.predict(sample_features_with_interactions)
        assert isinstance(pred, float)
        assert 0 <= pred <= 100

class TestMetaLearner:
    def test_ensemble_combines_models(self, meta_learner):
        """Meta-learner weighted combination of 3 base model outputs."""
        base_predictions = {
            "lightgbm": 65.0,
            "lstm": 70.0,
            "xgboost": 68.0,
        }
        final = meta_learner.predict(base_predictions)
        assert isinstance(final, float)
        # Final should be within range of base predictions
        assert 60.0 <= final <= 75.0
    
    def test_weights_sum_approximately_one(self, meta_learner):
        """Ridge weights should be interpretable."""
        weights = meta_learner.get_weights()
        assert abs(sum(weights.values()) - 1.0) < 0.2  # approximate

class TestCalibration:
    def test_isotonic_calibration(self, calibrator):
        """Calibrated confidence should be monotonically increasing with raw confidence."""
        raw_confidences = [0.1, 0.3, 0.5, 0.7, 0.9]
        calibrated = [calibrator.calibrate(c) for c in raw_confidences]
        # Should be monotonically non-decreasing
        for i in range(1, len(calibrated)):
            assert calibrated[i] >= calibrated[i-1]
    
    def test_calibration_bounds(self, calibrator):
        """Calibrated confidence should stay in [0, 1]."""
        for raw in [0.0, 0.01, 0.5, 0.99, 1.0]:
            cal = calibrator.calibrate(raw)
            assert 0.0 <= cal <= 1.0

class TestColdStart:
    def test_new_entity_confidence_cap(self):
        """Entities < 7 days old → max confidence 0.50."""
        pred = generate_prediction(entity_age_days=3, raw_confidence=0.95)
        assert pred.confidence <= 0.50
    
    def test_young_entity_confidence_cap(self):
        """Entities 7-14 days old → max confidence 0.70."""
        pred = generate_prediction(entity_age_days=10, raw_confidence=0.95)
        assert pred.confidence <= 0.70
    
    def test_mature_entity_no_cap(self):
        """Entities >= 14 days old → no confidence cap."""
        pred = generate_prediction(entity_age_days=30, raw_confidence=0.95)
        assert pred.confidence == 0.95  # no cap applied
```

---

## LAYER 2: INTEGRATION TESTS

Test the full prediction pipeline end-to-end with realistic data.

### `tests/test_prediction/test_integration.py`

```python
class TestPredictionPipeline:
    """End-to-end: raw data → features → predictions → API response."""
    
    @pytest.fixture
    def seeded_db(self, db_session):
        """Seed 90 days of realistic trending data for 50 entities."""
        seed_realistic_data(db_session, n_entities=50, n_days=90)
        return db_session
    
    def test_full_pipeline_produces_predictions(self, seeded_db):
        """Running the pipeline should produce predictions for all horizons."""
        results = run_prediction_pipeline(seeded_db)
        assert len(results["7d"]) > 0
        assert len(results["30d"]) > 0
        assert len(results["90d"]) > 0
    
    def test_predictions_have_valid_schema(self, seeded_db):
        """Every prediction matches the API response schema."""
        results = run_prediction_pipeline(seeded_db)
        for pred in results["7d"]:
            assert 0 <= pred.predicted_score <= 100
            assert 0 <= pred.confidence <= 1
            assert pred.confidence_interval["low"] <= pred.predicted_score
            assert pred.confidence_interval["high"] >= pred.predicted_score
            assert len(pred.top_signals) == 3
    
    def test_predictions_accessible_via_api(self, seeded_db, test_client):
        """After pipeline runs, GET /predictions returns results."""
        run_prediction_pipeline(seeded_db)
        resp = test_client.get("/api/v1/predictions?horizon=7d&limit=10")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 10
    
    def test_feedback_resolves_prediction(self, seeded_db, test_client):
        """POST /predictions/feedback fills actual_score and error."""
        run_prediction_pipeline(seeded_db)
        pred = test_client.get("/api/v1/predictions?limit=1").json()["data"][0]
        
        resp = test_client.post("/api/v1/predictions/feedback", json={
            "prediction_id": pred["prediction_id"],
            "actual_score": 72.1,
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["error"] is not None
```

---

## LAYER 3: BACKTESTING FRAMEWORK

Walk-forward backtesting simulates how the model would have performed historically.

### `prediction/backtesting.py`

```python
"""
Walk-Forward Backtesting Framework

Methodology:
- Take historical data from date range [start, end]
- For each evaluation date D in the range:
  1. Train on all data before D (with appropriate buffer)
  2. Generate predictions at D for D+7, D+30, D+90
  3. Wait until horizon elapses
  4. Compare predicted vs actual
  5. Record metrics

This simulates real deployment — no future data leakage.
"""

from dataclasses import dataclass
from datetime import date, timedelta
import numpy as np

@dataclass
class BacktestConfig:
    start_date: date          # First evaluation date
    end_date: date            # Last evaluation date
    train_window_days: int    # Days of training data (e.g., 180)
    min_train_days: int       # Minimum training data required (e.g., 60)
    step_days: int            # Days between evaluation points (e.g., 7 = weekly)
    horizons: list[str]       # ["7d", "30d", "90d"]
    retrain_frequency: int    # Retrain every N steps (e.g., 4 = monthly)

@dataclass
class BacktestResult:
    evaluation_date: date
    horizon: str
    n_predictions: int
    mae: float               # Mean Absolute Error
    rmse: float              # Root Mean Squared Error
    median_ae: float         # Median Absolute Error
    p90_ae: float            # 90th percentile absolute error
    calibration_score: float # % of actuals within confidence interval
    directional_accuracy: float  # % of correct up/down predictions
    top_k_accuracy: float    # % of predicted top-10 that were actually top-10
    model_version: str

class WalkForwardBacktester:
    """
    Run walk-forward backtesting on the prediction model.
    
    Usage:
        config = BacktestConfig(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 1),
            train_window_days=180,
            min_train_days=60,
            step_days=7,
            horizons=["7d", "30d"],
            retrain_frequency=4,
        )
        backtester = WalkForwardBacktester(config, db_session)
        results = await backtester.run()
    """
    
    def __init__(self, config: BacktestConfig, db_session):
        self.config = config
        self.db = db_session
    
    async def run(self) -> list[BacktestResult]:
        results = []
        current_model = None
        step_count = 0
        
        eval_date = self.config.start_date
        while eval_date <= self.config.end_date:
            # Determine training window
            train_start = eval_date - timedelta(days=self.config.train_window_days)
            train_end = eval_date - timedelta(days=1)  # no data from eval_date itself
            
            # Check sufficient training data
            train_data = await self.get_data(train_start, train_end)
            if len(train_data) < self.config.min_train_days:
                eval_date += timedelta(days=self.config.step_days)
                continue
            
            # Retrain if needed
            if current_model is None or step_count % self.config.retrain_frequency == 0:
                current_model = await self.train_model(train_data)
            
            # Generate predictions for each horizon
            for horizon in self.config.horizons:
                horizon_days = {"7d": 7, "30d": 30, "90d": 90}[horizon]
                horizon_end = eval_date + timedelta(days=horizon_days)
                
                # Skip if we don't have ground truth yet
                if horizon_end > self.config.end_date:
                    continue
                
                # Generate predictions
                features = await self.build_features(eval_date)
                predictions = current_model.predict_batch(features)
                
                # Get actual outcomes
                actuals = await self.get_actuals(horizon_end)
                
                # Calculate metrics
                result = self.evaluate(eval_date, horizon, predictions, actuals, current_model.version)
                results.append(result)
            
            step_count += 1
            eval_date += timedelta(days=self.config.step_days)
        
        return results
    
    def evaluate(self, eval_date, horizon, predictions, actuals, model_version) -> BacktestResult:
        """Calculate all evaluation metrics."""
        # Match predictions to actuals by entity_id
        matched = self.match_predictions_to_actuals(predictions, actuals)
        
        errors = [pred - actual for pred, actual in matched]
        abs_errors = [abs(e) for e in errors]
        
        # Directional accuracy: did we correctly predict up vs down?
        correct_direction = sum(
            1 for pred_change, actual_change in self.get_changes(matched)
            if (pred_change > 0) == (actual_change > 0)
        )
        
        # Top-K accuracy: of our predicted top-10, how many were actually top-10?
        predicted_top10 = sorted(predictions, key=lambda p: p.predicted_score, reverse=True)[:10]
        actual_top10_ids = set(
            sorted(actuals, key=lambda a: a.actual_score, reverse=True)[:10]
        )
        top_k_hits = sum(1 for p in predicted_top10 if p.entity_id in actual_top10_ids)
        
        # Calibration: % of actuals within predicted confidence interval
        in_interval = sum(
            1 for p in predictions
            if p.confidence_interval["low"] <= actuals[p.entity_id] <= p.confidence_interval["high"]
        )
        
        return BacktestResult(
            evaluation_date=eval_date,
            horizon=horizon,
            n_predictions=len(matched),
            mae=np.mean(abs_errors),
            rmse=np.sqrt(np.mean([e**2 for e in errors])),
            median_ae=np.median(abs_errors),
            p90_ae=np.percentile(abs_errors, 90),
            calibration_score=in_interval / len(predictions) if predictions else 0,
            directional_accuracy=correct_direction / len(matched) if matched else 0,
            top_k_accuracy=top_k_hits / 10,
            model_version=model_version,
        )


# ─── ACCEPTANCE CRITERIA ───
# These are hard gates. If backtesting doesn't meet these, do NOT deploy.

ACCEPTANCE_CRITERIA = {
    "7d": {
        "mae_max": 12.0,                # Mean Absolute Error < 12 on 0-100 scale
        "rmse_max": 16.0,
        "directional_accuracy_min": 0.65, # Correctly predict up/down 65%+ of the time
        "top_k_accuracy_min": 0.40,       # 4 of predicted top-10 are actually top-10
        "calibration_min": 0.70,          # 70%+ of actuals within confidence intervals
    },
    "30d": {
        "mae_max": 18.0,
        "rmse_max": 24.0,
        "directional_accuracy_min": 0.58,
        "top_k_accuracy_min": 0.30,
        "calibration_min": 0.65,
    },
    "90d": {
        "mae_max": 25.0,
        "rmse_max": 32.0,
        "directional_accuracy_min": 0.52,
        "top_k_accuracy_min": 0.20,
        "calibration_min": 0.60,
    },
}

def check_acceptance(results: list[BacktestResult]) -> dict[str, bool]:
    """Check if backtesting results meet acceptance criteria."""
    verdict = {}
    for horizon, criteria in ACCEPTANCE_CRITERIA.items():
        horizon_results = [r for r in results if r.horizon == horizon]
        if not horizon_results:
            verdict[horizon] = False
            continue
        
        avg_mae = np.mean([r.mae for r in horizon_results])
        avg_rmse = np.mean([r.rmse for r in horizon_results])
        avg_dir_acc = np.mean([r.directional_accuracy for r in horizon_results])
        avg_top_k = np.mean([r.top_k_accuracy for r in horizon_results])
        avg_cal = np.mean([r.calibration_score for r in horizon_results])
        
        verdict[horizon] = all([
            avg_mae <= criteria["mae_max"],
            avg_rmse <= criteria["rmse_max"],
            avg_dir_acc >= criteria["directional_accuracy_min"],
            avg_top_k >= criteria["top_k_accuracy_min"],
            avg_cal >= criteria["calibration_min"],
        ])
    
    return verdict
```

---

## LAYER 4: SHADOW MODE (Champion/Challenger)

Run new models in parallel with the production model before promoting them.

### `prediction/shadow_mode.py`

```python
"""
Champion/Challenger Framework

- Champion: currently serving production predictions
- Challenger: new model running in shadow, generating predictions but not serving them

After N days of shadow running:
- Compare challenger metrics vs champion metrics
- If challenger wins on primary metric (MAE) AND doesn't regress on secondary metrics:
  → Promote challenger to champion
  → Demote champion to archive
"""

@dataclass
class ModelSlot:
    model_id: str
    model_version: str
    role: str  # "champion" | "challenger" | "archived"
    promoted_at: datetime | None
    metrics_7d: dict  # rolling 7-day metrics
    metrics_30d: dict  # rolling 30-day metrics

class ShadowModeManager:
    MIN_SHADOW_DAYS = 7     # Minimum days before challenger can be promoted
    WIN_THRESHOLD = 0.05     # Challenger must beat champion by 5% on MAE
    
    async def run_daily(self):
        """Called by the daily training loop."""
        champion = await self.get_champion()
        challenger = await self.get_challenger()
        
        if challenger is None:
            return  # No challenger running
        
        # Both models generate predictions
        champion_preds = await champion.predict_all()
        challenger_preds = await challenger.predict_all()
        
        # Store champion predictions as official (served via API)
        await self.store_predictions(champion_preds, official=True)
        # Store challenger predictions for tracking only
        await self.store_predictions(challenger_preds, official=False)
        
        # Check if challenger is ready for evaluation
        shadow_days = (datetime.now() - challenger.promoted_at).days
        if shadow_days < self.MIN_SHADOW_DAYS:
            return
        
        # Compare metrics on resolved predictions
        comparison = await self.compare_models(champion, challenger)
        
        if comparison.challenger_wins:
            await self.promote_challenger(challenger, champion)
            logger.info("model_promoted", 
                       new_champion=challenger.model_version,
                       improvement=comparison.mae_improvement_pct)
        elif shadow_days > 30:
            # Challenger has been running for 30 days without winning — retire it
            await self.retire_challenger(challenger)
            logger.info("challenger_retired", model=challenger.model_version)
    
    async def compare_models(self, champion, challenger) -> ModelComparison:
        """Compare resolved predictions between two models."""
        # Get predictions from both that have been resolved (horizon elapsed)
        champ_resolved = await self.get_resolved_predictions(champion.model_id)
        chall_resolved = await self.get_resolved_predictions(challenger.model_id)
        
        champ_mae = np.mean([abs(p.predicted_score - p.actual_score) for p in champ_resolved])
        chall_mae = np.mean([abs(p.predicted_score - p.actual_score) for p in chall_resolved])
        
        improvement = (champ_mae - chall_mae) / champ_mae
        
        return ModelComparison(
            champion_mae=champ_mae,
            challenger_mae=chall_mae,
            mae_improvement_pct=improvement * 100,
            challenger_wins=improvement >= self.WIN_THRESHOLD,
            # Also check secondary metrics don't regress
            calibration_ok=chall_calibration >= champ_calibration * 0.95,
            directional_ok=chall_directional >= champ_directional * 0.95,
        )
```

---

## LAYER 5: DRIFT DETECTION

Catch when the world changes faster than the model adapts.

### `prediction/drift_detection.py`

```python
"""
Three types of drift to detect:

1. FEATURE DRIFT (PSI): Distribution of input features has shifted
   → Cause: upstream data source changed format, new platform behavior pattern
   → Action: Retrain with recent data

2. PREDICTION DRIFT (KS test): Distribution of predictions has shifted
   → Cause: Model is systematically over/under-predicting
   → Action: Recalibrate confidence, possibly retrain

3. PERFORMANCE DRIFT (MAE tracking): Accuracy is degrading
   → Cause: World changed, model assumptions no longer hold
   → Action: Retrain, possibly re-engineer features
"""

import numpy as np
from scipy import stats

class DriftDetector:
    """Run on every daily training loop iteration."""
    
    # Thresholds
    PSI_WARNING = 0.10      # Feature drift warning
    PSI_CRITICAL = 0.20     # Feature drift → trigger retrain
    KS_PVALUE_THRESHOLD = 0.01  # Prediction drift significance
    MAE_DEGRADATION_THRESHOLD = 0.15  # 15% MAE increase → retrain
    
    def calculate_psi(self, expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
        """
        Population Stability Index.
        Measures how much a feature distribution has shifted.
        
        PSI < 0.10: No significant shift
        0.10 <= PSI < 0.20: Moderate shift (warning)
        PSI >= 0.20: Significant shift (retrain)
        """
        # Bin the expected distribution
        breakpoints = np.percentile(expected, np.linspace(0, 100, bins + 1))
        breakpoints[0] = -np.inf
        breakpoints[-1] = np.inf
        
        expected_pcts = np.histogram(expected, bins=breakpoints)[0] / len(expected)
        actual_pcts = np.histogram(actual, bins=breakpoints)[0] / len(actual)
        
        # Avoid log(0)
        expected_pcts = np.clip(expected_pcts, 0.001, None)
        actual_pcts = np.clip(actual_pcts, 0.001, None)
        
        psi = np.sum((actual_pcts - expected_pcts) * np.log(actual_pcts / expected_pcts))
        return psi
    
    def check_feature_drift(self, feature_name: str, 
                            training_distribution: np.ndarray,
                            current_distribution: np.ndarray) -> DriftResult:
        """Check if a feature's distribution has shifted since training."""
        psi = self.calculate_psi(training_distribution, current_distribution)
        
        if psi >= self.PSI_CRITICAL:
            return DriftResult(feature_name, "critical", psi, "Significant feature drift detected")
        elif psi >= self.PSI_WARNING:
            return DriftResult(feature_name, "warning", psi, "Moderate feature drift")
        return DriftResult(feature_name, "ok", psi, "No significant drift")
    
    def check_prediction_drift(self, 
                               recent_predictions: np.ndarray,
                               historical_predictions: np.ndarray) -> DriftResult:
        """KS test on prediction distribution."""
        statistic, pvalue = stats.ks_2samp(recent_predictions, historical_predictions)
        
        if pvalue < self.KS_PVALUE_THRESHOLD:
            return DriftResult("predictions", "critical", statistic, 
                             f"Prediction distribution shifted (KS p={pvalue:.4f})")
        return DriftResult("predictions", "ok", statistic, "No prediction drift")
    
    def check_performance_drift(self,
                                recent_mae: float,
                                rolling_30d_mae: float) -> DriftResult:
        """Check if recent accuracy has degraded."""
        if rolling_30d_mae == 0:
            return DriftResult("performance", "ok", 0, "Insufficient data")
        
        degradation = (recent_mae - rolling_30d_mae) / rolling_30d_mae
        
        if degradation > self.MAE_DEGRADATION_THRESHOLD:
            return DriftResult("performance", "critical", degradation,
                             f"MAE degraded by {degradation*100:.1f}%")
        return DriftResult("performance", "ok", degradation, "Performance stable")
    
    async def run_full_check(self, db_session) -> list[DriftResult]:
        """Run all drift checks. Called daily."""
        results = []
        
        # Feature drift: check top 10 most important features
        top_features = await get_top_features(db_session, n=10)
        for feature_name in top_features:
            training_dist = await get_training_distribution(feature_name, db_session)
            current_dist = await get_recent_distribution(feature_name, db_session, days=7)
            results.append(self.check_feature_drift(feature_name, training_dist, current_dist))
        
        # Prediction drift
        recent_preds = await get_recent_predictions(db_session, days=7)
        historical_preds = await get_predictions(db_session, days_ago=30, window=23)
        results.append(self.check_prediction_drift(recent_preds, historical_preds))
        
        # Performance drift
        recent_mae = await get_recent_mae(db_session, days=7)
        rolling_mae = await get_rolling_mae(db_session, days=30)
        results.append(self.check_performance_drift(recent_mae, rolling_mae))
        
        return results
    
    def should_retrain(self, results: list[DriftResult]) -> bool:
        """Any critical drift → retrain."""
        return any(r.severity == "critical" for r in results)
```

---

## LAYER 6: FAILURE ANALYSIS TAXONOMY

Classify prediction errors to guide improvement.

### `prediction/failure_analysis.py`

```python
"""
When a prediction is significantly wrong, classify WHY it was wrong.
This informs which part of the system to improve.

Error Categories:
1. VIRAL_SHOCK    — Unexpected viral event (TikTok challenge, meme, celebrity endorsement)
2. DATA_GAP       — Missing data from a platform during prediction window
3. GENRE_MISMATCH — Entity was misclassified, genre features were wrong
4. COLD_START     — Entity too new, insufficient history for accurate prediction
5. SEASONAL       — Seasonal pattern not captured (holiday music, summer anthems)
6. PLATFORM_SHIFT — Platform algorithm change (Spotify changed playlist curation)
7. EXTERNAL_EVENT — Real-world event affecting music (artist controversy, award show)
8. MODEL_BIAS     — Systematic over/under-prediction for a category of entities
9. STALE_DATA     — Prediction used stale data due to scraper failure
10. UNKNOWN       — Can't determine cause
"""

from enum import Enum

class FailureType(Enum):
    VIRAL_SHOCK = "viral_shock"
    DATA_GAP = "data_gap"
    GENRE_MISMATCH = "genre_mismatch"
    COLD_START = "cold_start"
    SEASONAL = "seasonal"
    PLATFORM_SHIFT = "platform_shift"
    EXTERNAL_EVENT = "external_event"
    MODEL_BIAS = "model_bias"
    STALE_DATA = "stale_data"
    UNKNOWN = "unknown"

class FailureClassifier:
    """
    Automated heuristic classifier for prediction failures.
    Runs on every resolved prediction where |error| > threshold.
    """
    
    ERROR_THRESHOLD = 20.0  # Only analyze predictions off by > 20 points
    
    async def classify(self, prediction, actual_score, db_session) -> FailureType:
        entity = await get_entity(prediction.entity_id, db_session)
        
        # Check cold start
        if entity.age_days < 14:
            return FailureType.COLD_START
        
        # Check data gaps
        platforms_at_prediction = await get_platform_coverage(
            entity.id, prediction.predicted_at, db_session
        )
        platforms_at_resolution = await get_platform_coverage(
            entity.id, prediction.resolved_at, db_session
        )
        if len(platforms_at_prediction) < len(platforms_at_resolution) - 1:
            return FailureType.DATA_GAP
        
        # Check viral shock (sudden spike not preceded by gradual buildup)
        if actual_score > prediction.predicted_score + 30:
            velocity_before = await get_velocity(entity.id, prediction.predicted_at, db_session)
            if velocity_before < 5.0:  # was flat, then exploded
                return FailureType.VIRAL_SHOCK
        
        # Check stale data
        data_age_at_prediction = await get_data_freshness(entity.id, prediction.predicted_at, db_session)
        if data_age_at_prediction > timedelta(hours=24):
            return FailureType.STALE_DATA
        
        # Check seasonal patterns
        if is_holiday_period(prediction.predicted_at) or is_holiday_period(prediction.resolved_at):
            return FailureType.SEASONAL
        
        # Check genre mismatch
        predicted_genre_momentum = prediction.features_json.get("genre_overall_momentum", 0)
        actual_genre_momentum = await get_genre_momentum(entity.genres[0], prediction.resolved_at, db_session)
        if abs(predicted_genre_momentum - actual_genre_momentum) > 20:
            return FailureType.GENRE_MISMATCH
        
        # Check model bias (systematic error for this entity type/genre)
        historical_errors = await get_historical_errors(
            entity_type=entity.type, genre=entity.genres[0], db_session=db_session
        )
        if len(historical_errors) > 10:
            bias = np.mean(historical_errors)
            if abs(bias) > 10:
                return FailureType.MODEL_BIAS
        
        return FailureType.UNKNOWN
    
    async def generate_failure_report(self, db_session, days: int = 30) -> dict:
        """Generate summary of failure types over the last N days."""
        failures = await get_recent_failures(db_session, days)
        
        distribution = {}
        for failure_type in FailureType:
            count = sum(1 for f in failures if f.failure_type == failure_type)
            distribution[failure_type.value] = {
                "count": count,
                "pct": count / len(failures) * 100 if failures else 0,
                "avg_error": np.mean([f.error for f in failures if f.failure_type == failure_type]) if count > 0 else 0,
            }
        
        return {
            "period_days": days,
            "total_failures": len(failures),
            "distribution": distribution,
            "top_failure_type": max(distribution, key=lambda k: distribution[k]["count"]),
            "recommendation": self._get_recommendation(distribution),
        }
    
    def _get_recommendation(self, distribution: dict) -> str:
        """Actionable recommendation based on failure distribution."""
        top = max(distribution, key=lambda k: distribution[k]["count"])
        
        recommendations = {
            "viral_shock": "Add social media spike detection as a feature. Consider a separate 'viral alert' model.",
            "data_gap": "Improve scraper reliability. Add fallback chains. Consider imputation for missing data.",
            "genre_mismatch": "Audit genre classification. Consider multi-label genre assignment.",
            "cold_start": "Extend cold start ramp period. Use genre-level transfer learning for new entities.",
            "seasonal": "Add seasonal decomposition features. Train separate seasonal adjustment model.",
            "platform_shift": "Monitor upstream API responses for schema changes. Add platform algorithm change detection.",
            "external_event": "Integrate news/social sentiment features. Hard to predict but can react faster.",
            "model_bias": "Audit training data balance. Consider per-genre or per-entity-type model calibration.",
            "stale_data": "Fix scraper scheduling. Add data freshness as an input feature with confidence discount.",
            "unknown": "Manual investigation needed. Review individual failure cases.",
        }
        return recommendations.get(top, "No recommendation available.")
```

---

## 26-WEEK ITERATION ROADMAP

Build this as a Markdown reference file the system reads to know what phase it's in.

### `prediction/ITERATION_ROADMAP.md`

```markdown
# Prediction Engine Iteration Roadmap

## Weeks 1-4: Foundation
- [ ] Feature engineering pipeline (all ~70 features)
- [ ] LightGBM model (first base model)
- [ ] Unit tests for all features
- [ ] Basic backtesting framework (7d horizon only)
- [ ] Daily training loop (no drift detection yet)
- **EXIT CRITERIA**: LightGBM alone meets 7d MAE < 15

## Weeks 5-8: Ensemble
- [ ] LSTM model with attention
- [ ] XGBoost with interaction features
- [ ] Ridge meta-learner combining all 3
- [ ] Confidence calibration (isotonic regression)
- [ ] Extend backtesting to 30d horizon
- **EXIT CRITERIA**: Ensemble meets 7d MAE < 12, 30d MAE < 20

## Weeks 9-12: Reliability
- [ ] Cold start strategy implementation
- [ ] Shadow mode (champion/challenger)
- [ ] Drift detection (PSI + KS + MAE tracking)
- [ ] Failure classification taxonomy
- [ ] Automated retraining triggers
- **EXIT CRITERIA**: Shadow mode running, drift detected within 24h

## Weeks 13-16: Accuracy Push
- [ ] Add 90d horizon
- [ ] Feature importance analysis → prune weak features
- [ ] Hyperparameter tuning (Optuna for each base model)
- [ ] Cross-validation instead of single split
- [ ] Genre-specific model calibration
- **EXIT CRITERIA**: All 3 horizons meet acceptance criteria

## Weeks 17-20: Robustness
- [ ] Failure analysis automation
- [ ] Weekly failure report generation
- [ ] A/B test framework for feature experiments
- [ ] Data quality scoring (discount predictions when data is stale)
- [ ] Platform weight auto-tuning based on predictive value
- **EXIT CRITERIA**: <5% unknown failure classifications

## Weeks 21-26: Scale & Polish
- [ ] Model serving optimization (batch predictions, caching)
- [ ] Prediction explanation improvements (SHAP values)
- [ ] Historical accuracy dashboard (trend of MAE over time)
- [ ] Anomaly detection layer (pre-filter viral shocks)
- [ ] Documentation and runbooks for model operations
- **EXIT CRITERIA**: Production-ready, documented, self-maintaining
```

---

## DAILY TRAINING LOOP (UPDATED WITH ALL LAYERS)

```python
# prediction/training_loop.py

async def daily_training_loop():
    """
    Runs at 06:30 UTC daily.
    Orchestrates: drift detection → retraining decision → prediction generation → failure analysis.
    """
    
    # 1. DRIFT DETECTION
    drift_results = await DriftDetector().run_full_check(db)
    for result in drift_results:
        if result.severity != "ok":
            logger.warning("drift_detected", **result.__dict__)
    
    # 2. RESOLVE EXPIRED PREDICTIONS
    resolved = await resolve_expired_predictions(db)
    logger.info("predictions_resolved", count=len(resolved))
    
    # 3. CLASSIFY FAILURES
    for pred in resolved:
        if abs(pred.error) > FailureClassifier.ERROR_THRESHOLD:
            failure_type = await FailureClassifier().classify(pred, pred.actual_score, db)
            await store_failure_classification(pred.id, failure_type, db)
    
    # 4. DECIDE: RETRAIN OR NOT
    should_retrain = DriftDetector().should_retrain(drift_results)
    if not should_retrain:
        # Also check MAE degradation
        recent_mae = await get_recent_mae(db, days=7)
        rolling_mae = await get_rolling_mae(db, days=30)
        if rolling_mae > 0 and (recent_mae - rolling_mae) / rolling_mae > 0.15:
            should_retrain = True
    
    # 5. RETRAIN IF NEEDED
    if should_retrain:
        logger.info("retraining_triggered")
        new_model = await train_full_ensemble(db)
        
        # Run backtesting on new model
        backtest_results = await WalkForwardBacktester(BACKTEST_CONFIG, db).run()
        acceptance = check_acceptance(backtest_results)
        
        if all(acceptance.values()):
            # Deploy as challenger (shadow mode)
            await ShadowModeManager().deploy_challenger(new_model)
            logger.info("challenger_deployed", model=new_model.version)
        else:
            logger.warning("new_model_failed_acceptance", results=acceptance)
    
    # 6. GENERATE TODAY'S PREDICTIONS (using champion model)
    champion = await ShadowModeManager().get_champion()
    predictions = await champion.predict_all_entities(db)
    await store_predictions(predictions, official=True)
    logger.info("predictions_generated", count=len(predictions))
    
    # 7. SHADOW MODE: Also generate challenger predictions if one exists
    challenger = await ShadowModeManager().get_challenger()
    if challenger:
        challenger_preds = await challenger.predict_all_entities(db)
        await store_predictions(challenger_preds, official=False)
        
        # Check if challenger should be promoted
        await ShadowModeManager().evaluate_promotion()
    
    # 8. GENERATE WEEKLY FAILURE REPORT (on Mondays)
    if datetime.now().weekday() == 0:
        report = await FailureClassifier().generate_failure_report(db, days=7)
        logger.info("weekly_failure_report", **report)
```
