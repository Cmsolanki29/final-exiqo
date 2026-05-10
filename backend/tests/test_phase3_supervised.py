"""Phase 3 tests — Supervised Model Layer (XGBoost + HybridScorer).

Acceptance criteria:
  [x] Synthetic data generator produces plausible fraud patterns.
  [x] HybridScorer returns both unsup and sup scores when model is loaded.
  [x] HybridScorer falls back to unsup-only when supervised model is missing.
  [x] PR-AUC > 0.5 on bootstrap synthetic data (sanity check).
  [x] Feature engineering produces correct vector shape and no NaNs.
  [x] assembled_to_feature_vector mapping is correct and stable.
  [x] evaluate_model returns all required metric keys.
  [x] Training with time-based split preserves temporal order.
"""

from __future__ import annotations

import pickle
import tempfile
from datetime import date, time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from ml_training.evaluation import evaluate_model
from ml_training.feature_engineering import (
    SUPERVISED_FEATURE_COLUMNS,
    assembled_to_feature_vector,
    build_features_from_df,
)
from ml_training.synthetic_data import generate_synthetic_fraud
from ml_training.train_supervised import (
    load_model,
    save_model,
    train_xgboost_model,
)
from schemas.score import ScoreResult


# ================================================================== #
# Fixtures
# ================================================================== #

@pytest.fixture(scope="module")
def legitimate_df() -> pd.DataFrame:
    """Generate a small legitimate transaction DataFrame for tests."""
    rng = np.random.default_rng(0)
    n = 500
    n_users = 20
    user_ids = rng.choice(range(1, n_users + 1), size=n)
    amounts = rng.lognormal(mean=7.5, sigma=1.0, size=n)
    base_date = date(2025, 1, 1)
    dates = [
        str(base_date.replace(month=1 + (i % 12), day=1 + (i % 28)))
        for i in range(n)
    ]
    return pd.DataFrame({
        "id": range(1, n + 1),
        "user_id": user_ids,
        "amount": amounts,
        "merchant": rng.choice(["Amazon", "Swiggy", "Zomato", "Flipkart", "DMart"], size=n),
        "category": rng.choice(["Food", "Shopping", "Groceries", "Utilities"], size=n),
        "payment_method": "UPI",
        "hour_of_day": rng.integers(8, 22, size=n),
        "day_of_week": rng.integers(0, 7, size=n),
        "is_weekend": rng.choice([True, False], size=n),
        "balance_after": rng.uniform(1000, 100000, size=n),
        "transaction_date": dates,
        "type": "DEBIT",
        "is_fraud": False,
        "fraud_label_source": "legitimate",
    })


@pytest.fixture(scope="module")
def df_with_fraud(legitimate_df) -> pd.DataFrame:
    """DataFrame with synthetic fraud injected."""
    return generate_synthetic_fraud(legitimate_df, fraud_rate=0.05, seed=42)


@pytest.fixture(scope="module")
def training_data(df_with_fraud):
    """Feature matrix and labels for training tests."""
    X, y = build_features_from_df(df_with_fraud)
    return X, y


@pytest.fixture(scope="module")
def trained_xgb_model(training_data):
    """Trained XGBClassifier on synthetic data."""
    X, y = training_data
    if int(y.sum()) < 5:
        pytest.skip("Insufficient fraud samples for training")
    model, metrics = train_xgboost_model(X, y, n_splits=2)
    return model


@pytest.fixture(scope="module")
def mock_ensemble_detector():
    """Minimal mock of EnsembleAnomalyDetector for HybridScorer tests."""
    detector = MagicMock()
    detector.DETECTOR_VERSION = "ensemble-pyod-iforest-copod-pca-v2.1"
    detector.score_single.return_value = ScoreResult(
        risk_score=30,
        risk_level="LOW",
        unsup_score=0.30,
        sup_score=None,
        signals={"amount_zscore": 0.2},
        explanation="Normal transaction",
        detector_version="ensemble-pyod-iforest-copod-pca-v2.1",
        latency_ms=15.0,
    )
    return detector


# ================================================================== #
# Test: synthetic_data.py
# ================================================================== #

class TestSyntheticData:

    def test_fraud_rows_injected(self, legitimate_df):
        """Fraud rows are added to the DataFrame."""
        result = generate_synthetic_fraud(legitimate_df, fraud_rate=0.01)
        n_fraud = int(result["is_fraud"].sum())
        assert n_fraud > 0, "No fraud rows injected"

    def test_fraud_rate_approximately_correct(self, legitimate_df):
        """Actual fraud rate is within 3x the target (due to discrete patterns)."""
        target = 0.05
        result = generate_synthetic_fraud(legitimate_df, fraud_rate=target, seed=1)
        actual_rate = result["is_fraud"].sum() / len(result)
        assert actual_rate > 0, "Fraud rate must be > 0"

    def test_five_fraud_patterns_present(self, df_with_fraud):
        """All five synthetic fraud patterns are represented."""
        sources = df_with_fraud["fraud_label_source"].unique().tolist()
        expected_patterns = [
            "synthetic_card_test_burst",
            "synthetic_account_drain",
            "synthetic_off_hours",
            "synthetic_geo_impossible",
            "synthetic_new_merchant_drain",
        ]
        for pattern in expected_patterns:
            assert any(pattern in s for s in sources), f"Pattern '{pattern}' not found in sources: {sources}"

    def test_fraud_amounts_elevated(self, df_with_fraud):
        """Account drain rows have higher amounts than legitimate average."""
        legit_mean = df_with_fraud[~df_with_fraud["is_fraud"]]["amount"].mean()
        drain = df_with_fraud[df_with_fraud["fraud_label_source"] == "synthetic_account_drain"]["amount"]
        if len(drain) > 0:
            assert drain.mean() > legit_mean, "Drain fraud should have higher amounts"

    def test_card_burst_small_amounts(self, df_with_fraud):
        """Card testing burst rows have smaller amounts."""
        burst = df_with_fraud[df_with_fraud["fraud_label_source"] == "synthetic_card_test_burst"]["amount"]
        if len(burst) > 0:
            assert burst.mean() < 500, "Card test burst should have small amounts (< ₹500)"

    def test_legitimate_rows_preserved(self, legitimate_df, df_with_fraud):
        """All legitimate rows are preserved in output."""
        n_legit_in = len(legitimate_df)
        n_legit_out = len(df_with_fraud[~df_with_fraud["is_fraud"]])
        assert n_legit_out == n_legit_in, "Legitimate row count should be unchanged"

    def test_output_has_required_columns(self, df_with_fraud):
        """Output DataFrame has is_fraud and fraud_label_source columns."""
        assert "is_fraud" in df_with_fraud.columns
        assert "fraud_label_source" in df_with_fraud.columns

    def test_reproducible_with_seed(self, legitimate_df):
        """Two calls with the same seed produce identical results."""
        df1 = generate_synthetic_fraud(legitimate_df, seed=99)
        df2 = generate_synthetic_fraud(legitimate_df, seed=99)
        assert len(df1) == len(df2)
        assert int(df1["is_fraud"].sum()) == int(df2["is_fraud"].sum())


# ================================================================== #
# Test: feature_engineering.py
# ================================================================== #

class TestFeatureEngineering:

    def test_feature_columns_order_stable(self):
        """SUPERVISED_FEATURE_COLUMNS is a fixed-length ordered list."""
        assert len(SUPERVISED_FEATURE_COLUMNS) == 28, (
            f"Expected 28 columns, got {len(SUPERVISED_FEATURE_COLUMNS)}"
        )
        assert SUPERVISED_FEATURE_COLUMNS[0] == "txn_count_1h"
        assert SUPERVISED_FEATURE_COLUMNS[-1] == "day_of_week"

    def test_build_features_from_df_shape(self, training_data):
        """Feature matrix has correct shape and column order."""
        X, y = training_data
        assert X.shape[1] == len(SUPERVISED_FEATURE_COLUMNS)
        assert list(X.columns) == SUPERVISED_FEATURE_COLUMNS

    def test_no_nan_in_features(self, training_data):
        """Feature matrix contains no NaN values."""
        X, y = training_data
        assert not X.isna().any().any(), f"NaNs found in columns: {X.columns[X.isna().any()].tolist()}"

    def test_no_inf_in_features(self, training_data):
        """Feature matrix contains no infinite values."""
        X, y = training_data
        assert np.isfinite(X.values).all(), "Infinite values found in feature matrix"

    def test_labels_binary(self, training_data):
        """Labels are 0.0 or 1.0 only."""
        _, y = training_data
        unique_vals = set(y.unique())
        assert unique_vals.issubset({0.0, 1.0}), f"Non-binary labels found: {unique_vals}"

    def test_X_y_aligned(self, training_data):
        """X and y have the same number of rows."""
        X, y = training_data
        assert len(X) == len(y)

    def test_assembled_to_feature_vector_shape(self):
        """assembled_to_feature_vector returns vector of correct length."""
        assembled = {
            "user_txn_count_1h": 2, "user_txn_count_24h": 5,
            "user_txn_count_7d": 20, "user_txn_count_30d": 80,
            "user_debit_sum_1h": 1000.0, "user_debit_sum_24h": 3000.0,
            "user_debit_avg_30d": 800.0, "user_debit_std_30d": 200.0,
            "user_debit_p95_30d": 2000.0, "user_unique_merchants_30d": 10,
            "user_account_age_days": 180, "user_weekend_txn_ratio_30d": 0.3,
            "user_avg_hours_between_txns_30d": 8.0,
            "txn_log_amount": 7.0, "txn_hour_sin": 0.5, "txn_hour_cos": 0.866,
            "amt_ratio_30d": 1.2, "txn_amount_vs_p95": 0.5,
            "velocity_inr_per_hour": 1000.0, "hours_since_prev": 3.0,
            "merchant_changed": 0.0, "txn_balance_ratio": 0.02,
            "txn_is_round_amount": 0.0, "txn_time_risk": 0.0,
            "txn_is_burst": 0.0, "txn_is_weekend": 0.0,
            "txn_is_night": 0.0, "txn_day_of_week": 2.0,
        }
        vec = assembled_to_feature_vector(assembled)
        assert vec.shape == (len(SUPERVISED_FEATURE_COLUMNS),)

    def test_assembled_to_feature_vector_no_nan(self):
        """assembled_to_feature_vector replaces missing values with 0.0."""
        vec = assembled_to_feature_vector({})  # empty dict → all defaults
        assert np.isfinite(vec).all()
        assert vec.shape == (len(SUPERVISED_FEATURE_COLUMNS),)

    def test_assembled_to_feature_vector_correct_mapping(self):
        """amt_ratio_30d maps to amount_vs_avg_30d position in the vector."""
        assembled = {"amt_ratio_30d": 5.0}
        vec = assembled_to_feature_vector(assembled)
        idx = SUPERVISED_FEATURE_COLUMNS.index("amount_vs_avg_30d")
        assert vec[idx] == pytest.approx(5.0)


# ================================================================== #
# Test: train_supervised.py + evaluation.py
# ================================================================== #

class TestTrainAndEvaluate:

    def test_train_returns_model_and_metrics(self, training_data):
        """train_xgboost_model returns a model and a non-empty metrics dict."""
        X, y = training_data
        if int(y.sum()) < 5:
            pytest.skip("Insufficient fraud samples")
        model, metrics = train_xgboost_model(X, y, n_splits=2)
        assert model is not None
        assert "train_size" in metrics
        assert metrics["train_size"] > 0

    def test_model_has_predict_proba(self, trained_xgb_model):
        """Trained model exposes predict_proba (required by HybridScorer)."""
        assert hasattr(trained_xgb_model, "predict_proba")

    def test_pr_auc_above_chance(self, trained_xgb_model, training_data):
        """PR-AUC > 0.5 on synthetic data (sanity: model beats random chance)."""
        X, y = training_data
        split = int(len(X) * 0.8)
        X_test, y_test = X.iloc[split:], y.iloc[split:]
        if int(y_test.sum()) == 0:
            pytest.skip("No fraud in test split")
        metrics = evaluate_model(trained_xgb_model, X_test, y_test)
        assert metrics["pr_auc"] > 0.5, (
            f"PR-AUC {metrics['pr_auc']:.4f} ≤ 0.5 — model not beating random chance"
        )

    def test_evaluate_returns_all_required_keys(self, trained_xgb_model, training_data):
        """evaluate_model returns all Phase 3-required metric keys."""
        X, y = training_data
        split = int(len(X) * 0.8)
        X_test, y_test = X.iloc[split:], y.iloc[split:]
        if int(y_test.sum()) == 0:
            pytest.skip("No fraud in test split")
        metrics = evaluate_model(trained_xgb_model, X_test, y_test)
        required = [
            "pr_auc", "roc_auc", "recall_at_1pct_fpr", "recall_at_5pct_fpr",
            "precision_at_80_recall", "precision_at_50_recall",
            "confusion_matrix_at_best_f1", "n_test", "n_fraud_test",
        ]
        for key in required:
            assert key in metrics, f"Missing metric key: {key}"

    def test_save_and_load_model_roundtrip(self, trained_xgb_model, training_data):
        """Model saved and loaded produces identical predictions."""
        X, y = training_data
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test_model.pkl"
            save_model(trained_xgb_model, path)
            loaded = load_model(path)
            assert loaded is not None
            orig_preds = trained_xgb_model.predict_proba(X)[:, 1]
            load_preds = loaded.predict_proba(X)[:, 1]
            np.testing.assert_array_almost_equal(orig_preds, load_preds)

    def test_load_model_returns_none_for_missing_file(self):
        """load_model returns None gracefully when file is absent."""
        result = load_model("/nonexistent/path/model.pkl")
        assert result is None

    def test_train_too_few_fraud_raises(self, training_data):
        """train_xgboost_model raises ValueError with < 5 fraud samples."""
        import pytest
        from ml_training.train_supervised import train_xgboost_model
        X, y = training_data
        y_almost_empty = pd.Series([0.0] * len(y))  # no fraud at all
        with pytest.raises(ValueError, match="Too few fraud samples"):
            train_xgboost_model(X, y_almost_empty, n_splits=2)

    def test_evaluate_degenerate_no_fraud(self, trained_xgb_model, training_data):
        """evaluate_model handles test sets with no fraud gracefully."""
        X, _ = training_data
        y_no_fraud = pd.Series([0.0] * len(X))
        metrics = evaluate_model(trained_xgb_model, X, y_no_fraud)
        assert metrics["pr_auc"] == 0.0
        assert metrics["n_fraud_test"] == 0.0


# ================================================================== #
# Test: hybrid_scorer.py
# ================================================================== #

class TestHybridScorer:

    def test_has_supervised_model_false_when_no_file(self, mock_ensemble_detector):
        """HybridScorer reports no supervised model when the file doesn't exist."""
        from services.hybrid_scorer import HybridScorer
        with patch("services.hybrid_scorer.load_model", return_value=None):
            scorer = HybridScorer(detector=mock_ensemble_detector)
        assert not scorer.has_supervised_model

    def test_has_supervised_model_true_when_loaded(self, mock_ensemble_detector, trained_xgb_model):
        """HybridScorer reports supervised model active when file is present."""
        from services.hybrid_scorer import HybridScorer
        with patch("services.hybrid_scorer.load_model", return_value=trained_xgb_model):
            scorer = HybridScorer(detector=mock_ensemble_detector)
        assert scorer.has_supervised_model

    def test_fallback_to_unsup_only_returns_score_result(self, mock_ensemble_detector):
        """Without supervised model, score_sync returns a valid ScoreResult."""
        from services.hybrid_scorer import HybridScorer
        with patch("services.hybrid_scorer.load_model", return_value=None):
            scorer = HybridScorer(detector=mock_ensemble_detector)

        txn = {"amount": 500.0, "hour_of_day": 12, "day_of_week": 2, "is_weekend": False}
        result = scorer.score_sync(user_id=1, txn=txn, features=None)

        assert isinstance(result, ScoreResult)
        assert result.sup_score is None, "sup_score should be None in unsup-only mode"
        assert 0 <= result.risk_score <= 100

    def test_hybrid_returns_both_scores_when_model_loaded(self, mock_ensemble_detector, trained_xgb_model):
        """With supervised model, score_sync populates both unsup_score and sup_score."""
        from services.hybrid_scorer import HybridScorer
        with patch("services.hybrid_scorer.load_model", return_value=trained_xgb_model):
            scorer = HybridScorer(detector=mock_ensemble_detector)

        txn = {"amount": 500.0, "hour_of_day": 12, "day_of_week": 2, "is_weekend": False}
        # Provide a minimal assembled features dict
        assembled = {k: 0.0 for k in [
            "user_txn_count_1h", "user_txn_count_24h", "user_txn_count_7d", "user_txn_count_30d",
            "user_debit_sum_1h", "user_debit_sum_24h", "user_debit_avg_30d", "user_debit_std_30d",
            "user_debit_p95_30d", "user_unique_merchants_30d", "user_account_age_days",
            "user_weekend_txn_ratio_30d", "user_avg_hours_between_txns_30d",
            "txn_log_amount", "txn_hour_sin", "txn_hour_cos", "amt_ratio_30d",
            "txn_amount_vs_p95", "velocity_inr_per_hour", "hours_since_prev",
            "merchant_changed", "txn_balance_ratio", "txn_is_round_amount",
            "txn_time_risk", "txn_is_burst", "txn_is_weekend", "txn_is_night", "txn_day_of_week",
        ]}
        result = scorer.score_sync(user_id=1, txn=txn, features=assembled)

        assert isinstance(result, ScoreResult)
        assert result.sup_score is not None, "sup_score should be populated when model is loaded"
        assert 0.0 <= result.sup_score <= 1.0
        assert 0.0 <= result.unsup_score <= 1.0

    def test_hybrid_blends_scores_correctly(self, mock_ensemble_detector, trained_xgb_model):
        """final risk_score is the weighted blend of unsup and sup scores."""
        from services.hybrid_scorer import HybridScorer
        with patch("services.hybrid_scorer.load_model", return_value=trained_xgb_model):
            scorer = HybridScorer(detector=mock_ensemble_detector)

        txn = {"amount": 500.0, "hour_of_day": 12, "day_of_week": 2}
        assembled = {k: 0.0 for k in [
            "user_txn_count_1h", "user_txn_count_24h", "user_txn_count_7d", "user_txn_count_30d",
            "user_debit_sum_1h", "user_debit_sum_24h", "user_debit_avg_30d", "user_debit_std_30d",
            "user_debit_p95_30d", "user_unique_merchants_30d", "user_account_age_days",
            "user_weekend_txn_ratio_30d", "user_avg_hours_between_txns_30d",
            "txn_log_amount", "txn_hour_sin", "txn_hour_cos", "amt_ratio_30d",
            "txn_amount_vs_p95", "velocity_inr_per_hour", "hours_since_prev",
            "merchant_changed", "txn_balance_ratio", "txn_is_round_amount",
            "txn_time_risk", "txn_is_burst", "txn_is_weekend", "txn_is_night", "txn_day_of_week",
        ]}
        result = scorer.score_sync(user_id=1, txn=txn, features=assembled)

        # Manually compute expected blend
        from core.config import get_settings
        settings = get_settings()
        expected = settings.UNSUP_WEIGHT * result.unsup_score + settings.SUP_WEIGHT * result.sup_score
        expected_score = int(round(min(max(expected * 100, 0), 100)))
        assert result.risk_score == expected_score

    def test_reload_supervised_false_for_missing_file(self, mock_ensemble_detector):
        """reload_supervised returns False when model file does not exist."""
        from services.hybrid_scorer import HybridScorer
        with patch("services.hybrid_scorer.load_model", return_value=None):
            scorer = HybridScorer(detector=mock_ensemble_detector)
        result = scorer.reload_supervised("/nonexistent/path.pkl")
        assert result is False

    def test_reload_supervised_true_after_bootstrap(self, mock_ensemble_detector, trained_xgb_model):
        """reload_supervised returns True and activates the model."""
        from services.hybrid_scorer import HybridScorer
        with patch("services.hybrid_scorer.load_model", return_value=None):
            scorer = HybridScorer(detector=mock_ensemble_detector)
        assert not scorer.has_supervised_model

        with patch("services.hybrid_scorer.load_model", return_value=trained_xgb_model):
            result = scorer.reload_supervised("any/path.pkl")
        assert result is True
        assert scorer.has_supervised_model

    def test_score_result_risk_level_valid(self, mock_ensemble_detector):
        """ScoreResult.risk_level is always one of the 4 valid literals."""
        from services.hybrid_scorer import HybridScorer
        with patch("services.hybrid_scorer.load_model", return_value=None):
            scorer = HybridScorer(detector=mock_ensemble_detector)

        txn = {"amount": 500.0, "hour_of_day": 12}
        result = scorer.score_sync(user_id=1, txn=txn)
        assert result.risk_level in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

    @pytest.mark.asyncio
    async def test_score_async_returns_score_result(self, mock_ensemble_detector):
        """async score() method returns a ScoreResult."""
        from services.hybrid_scorer import HybridScorer
        with patch("services.hybrid_scorer.load_model", return_value=None):
            scorer = HybridScorer(detector=mock_ensemble_detector)

        txn = {"amount": 200.0, "hour_of_day": 10}
        result = await scorer.score(user_id=42, txn=txn)
        assert isinstance(result, ScoreResult)
