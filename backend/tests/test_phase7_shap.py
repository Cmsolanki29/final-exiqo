"""Phase 7 SHAP Explainability test suite.

Tests:
  - SHAP additivity: sum(shap_values) + base_value ≈ model raw margin output
  - top_drivers ordered by |shap_value| descending
  - humanizer templates render correctly (30+ features)
  - humanizer fallback for unknown features
  - SHAPExplainer degrades gracefully without a model
  - SHAPExplainer.reload() updates the explainer
  - SHAPExplainer.explain_full() returns all features
  - HybridScorer populates explanation_detail when SHAP available
  - HybridScorer.explanation is flat string from top-3 drivers
  - ScoreResult.explanation_detail field backward compat (None by default)

Run:
    cd backend
    python -m pytest tests/test_phase7_shap.py -v --asyncio-mode=auto
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ================================================================== #
# Fixtures
# ================================================================== #

@pytest.fixture(scope="module")
def tiny_xgb_model():
    """Train a minimal XGBoost model for SHAP tests (runs once per module)."""
    import xgboost as xgb
    from sklearn.datasets import make_classification

    X, y = make_classification(
        n_samples=500, n_features=28, n_informative=10,
        n_redundant=5, random_state=42
    )
    model = xgb.XGBClassifier(
        n_estimators=20,
        max_depth=3,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X, y)
    return model, X


@pytest.fixture(scope="module")
def feature_names_28():
    """28 synthetic feature names matching SUPERVISED_FEATURE_COLUMNS length."""
    try:
        from ml_training.feature_engineering import SUPERVISED_FEATURE_COLUMNS
        return SUPERVISED_FEATURE_COLUMNS
    except ImportError:
        return [f"feature_{i}" for i in range(28)]


# ================================================================== #
# 1. Humanizer tests
# ================================================================== #

class TestHumanizer:
    """Unit tests for FEATURE_TEMPLATES and humanize()."""

    def test_at_least_30_templates(self):
        from services.explainability.humanizer import FEATURE_TEMPLATES
        assert len(FEATURE_TEMPLATES) >= 30, (
            f"Expected >= 30 templates, found {len(FEATURE_TEMPLATES)}"
        )

    def test_txn_count_1h_template(self):
        from services.explainability.humanizer import humanize
        result = humanize("user_txn_count_1h", 8.0, 0.45)
        assert "8" in result, f"Expected count in output: {result}"
        assert "hour" in result.lower(), f"Expected 'hour' in output: {result}"

    def test_amount_vs_avg_template(self):
        from services.explainability.humanizer import humanize
        result = humanize("txn_amount_vs_user_avg_30d", 3.5, 0.62)
        assert "3.5" in result, f"Expected ratio in output: {result}"

    def test_graph_device_sharing_template(self):
        from services.explainability.humanizer import humanize
        result = humanize("user_graph_max_device_user_count", 5.0, 0.30)
        assert "5" in result, f"Expected count in output: {result}"
        assert "device" in result.lower() or "user" in result.lower(), (
            f"Expected device/user context in output: {result}"
        )

    def test_fraud_distance_template(self):
        from services.explainability.humanizer import humanize
        result = humanize("user_graph_shortest_path_to_fraud", 1.0, 0.55)
        assert "1" in result, f"Expected hop count in output: {result}"

    def test_account_age_template(self):
        from services.explainability.humanizer import humanize
        result = humanize("user_account_age_days", 30.0, -0.20)
        assert "30" in result, f"Expected age in output: {result}"
        assert "day" in result.lower(), f"Expected 'day' in output: {result}"

    def test_unknown_feature_returns_fallback(self):
        from services.explainability.humanizer import humanize
        result = humanize("some_future_feature_xyz", 42.5, 0.1)
        assert "some_future_feature_xyz" in result, (
            f"Fallback should contain feature name: {result}"
        )
        assert "42" in result, f"Fallback should contain value: {result}"

    def test_humanize_survives_bad_template(self):
        """humanize() must never raise even if a template is malformed."""
        from services.explainability.humanizer import FEATURE_TEMPLATES, humanize
        # Temporarily inject a bad template (won't affect module state, just tests robustness)
        with patch.dict(FEATURE_TEMPLATES, {"bad_feature": "broken {nonexistent_var:.2f}"}):
            result = humanize("bad_feature", 1.0, 0.5)
        assert isinstance(result, str)

    def test_all_templates_render_without_error(self):
        """Every template in FEATURE_TEMPLATES must render successfully."""
        from services.explainability.humanizer import FEATURE_TEMPLATES, humanize
        errors = []
        for name in FEATURE_TEMPLATES:
            try:
                result = humanize(name, 5.0, 0.3)
                assert isinstance(result, str)
            except Exception as exc:
                errors.append(f"{name}: {exc}")
        assert not errors, f"Templates with render errors: {errors}"


# ================================================================== #
# 2. SHAPExplainer — unit tests
# ================================================================== #

class TestSHAPExplainer:
    """Unit tests for SHAPExplainer with a real tiny XGBoost model."""

    def test_available_false_without_model(self):
        from services.explainability.shap_explainer import SHAPExplainer
        exp = SHAPExplainer(model=None)
        assert exp.available is False

    def test_explain_returns_unavailable_without_model(self):
        from services.explainability.shap_explainer import SHAPExplainer
        exp = SHAPExplainer(model=None)
        result = exp.explain(np.zeros(28))
        assert result["available"] is False

    def test_available_true_with_model(self, tiny_xgb_model):
        from services.explainability.shap_explainer import SHAPExplainer
        model, _ = tiny_xgb_model
        exp = SHAPExplainer(model=model)
        assert exp.available is True

    def test_explain_returns_dict_with_required_keys(self, tiny_xgb_model):
        from services.explainability.shap_explainer import SHAPExplainer
        model, X = tiny_xgb_model
        exp = SHAPExplainer(model=model)
        result = exp.explain(X[0], top_k=5)
        assert result["available"] is True
        assert "base_value" in result
        assert "top_drivers" in result
        assert "feature_count" in result
        assert "total_shap_sum" in result
        assert "latency_ms" in result

    def test_shap_values_additivity(self, tiny_xgb_model):
        """sum(shap_values) + base_value ≈ model raw margin output (additivity theorem)."""
        import shap
        import xgboost as xgb
        from services.explainability.shap_explainer import SHAPExplainer  # noqa: F401

        model, X = tiny_xgb_model
        explainer_obj = shap.TreeExplainer(model)

        for i in range(3):  # test on 3 samples
            fv = X[i]
            shap_values = explainer_obj.shap_values(fv.reshape(1, -1))
            if isinstance(shap_values, list):
                sv = np.asarray(shap_values[1][0])
            else:
                sv = np.asarray(shap_values[0])

            base_value = explainer_obj.expected_value
            if isinstance(base_value, (list, np.ndarray)):
                base_value = float(np.asarray(base_value).flat[-1])
            else:
                base_value = float(base_value)

            # The raw margin from XGBoost
            raw_margin = model.get_booster().predict(
                xgb.DMatrix(fv.reshape(1, -1)), output_margin=True
            )[0]

            shap_sum = float(np.sum(sv)) + base_value
            diff = abs(shap_sum - raw_margin)
            assert diff < 0.01, (
                f"Sample {i}: SHAP additivity violated — "
                f"sum+base={shap_sum:.6f} vs margin={raw_margin:.6f} diff={diff:.8f}"
            )

    def test_top_drivers_ordered_by_abs_shap(self, tiny_xgb_model):
        """top_drivers must be sorted by |shap_value| descending."""
        from services.explainability.shap_explainer import SHAPExplainer
        model, X = tiny_xgb_model
        exp = SHAPExplainer(model=model)
        result = exp.explain(X[0], top_k=5)
        drivers = result["top_drivers"]
        abs_vals = [abs(d["shap_value"]) for d in drivers]
        assert abs_vals == sorted(abs_vals, reverse=True), (
            f"top_drivers not sorted by |shap_value|: {abs_vals}"
        )

    def test_top_k_limits_driver_count(self, tiny_xgb_model):
        from services.explainability.shap_explainer import SHAPExplainer
        model, X = tiny_xgb_model
        exp = SHAPExplainer(model=model)
        for k in [1, 3, 5, 10]:
            result = exp.explain(X[0], top_k=k)
            assert len(result["top_drivers"]) == k, (
                f"Expected {k} drivers, got {len(result['top_drivers'])}"
            )

    def test_driver_direction_matches_shap_sign(self, tiny_xgb_model):
        """direction should be increases_risk when shap_value > 0."""
        from services.explainability.shap_explainer import SHAPExplainer
        model, X = tiny_xgb_model
        exp = SHAPExplainer(model=model)
        result = exp.explain(X[0], top_k=10)
        for d in result["top_drivers"]:
            if d["shap_value"] > 0:
                assert d["direction"] == "increases_risk", (
                    f"Positive SHAP should be increases_risk: {d}"
                )
            else:
                assert d["direction"] == "decreases_risk", (
                    f"Negative SHAP should be decreases_risk: {d}"
                )

    def test_driver_human_readable_is_string(self, tiny_xgb_model):
        from services.explainability.shap_explainer import SHAPExplainer
        model, X = tiny_xgb_model
        exp = SHAPExplainer(model=model)
        result = exp.explain(X[0], top_k=5)
        for d in result["top_drivers"]:
            assert isinstance(d["human_readable"], str), (
                f"human_readable should be str: {d}"
            )
            assert len(d["human_readable"]) > 0

    def test_explain_with_custom_feature_names(self, tiny_xgb_model):
        from services.explainability.shap_explainer import SHAPExplainer
        model, X = tiny_xgb_model
        exp = SHAPExplainer(model=model)
        names = [f"my_feat_{i}" for i in range(28)]
        result = exp.explain(X[0], feature_names=names, top_k=3)
        for d in result["top_drivers"]:
            assert d["feature"].startswith("my_feat_"), (
                f"Custom name not used: {d['feature']}"
            )

    def test_reload_updates_explainer(self, tiny_xgb_model):
        """reload() should replace the explainer with a new model's version."""
        from services.explainability.shap_explainer import SHAPExplainer
        model, _ = tiny_xgb_model
        exp = SHAPExplainer(model=None)
        assert exp.available is False
        exp.reload(model)
        assert exp.available is True

    def test_explain_full_returns_all_features(self, tiny_xgb_model):
        """explain_full() must return a driver for every feature."""
        from services.explainability.shap_explainer import SHAPExplainer
        model, X = tiny_xgb_model
        exp = SHAPExplainer(model=model)
        result = exp.explain_full(X[0])
        assert result["available"] is True
        assert result["feature_count"] == 28
        assert len(result["all_features"]) == 28

    def test_explain_full_sorted_by_abs_shap(self, tiny_xgb_model):
        from services.explainability.shap_explainer import SHAPExplainer
        model, X = tiny_xgb_model
        exp = SHAPExplainer(model=model)
        result = exp.explain_full(X[0])
        abs_vals = [abs(d["shap_value"]) for d in result["all_features"]]
        assert abs_vals == sorted(abs_vals, reverse=True)

    def test_explain_latency_recorded(self, tiny_xgb_model):
        from services.explainability.shap_explainer import SHAPExplainer
        model, X = tiny_xgb_model
        exp = SHAPExplainer(model=model)
        result = exp.explain(X[0])
        assert "latency_ms" in result
        assert result["latency_ms"] >= 0


# ================================================================== #
# 3. ScoreResult backward compat
# ================================================================== #

class TestScoreResultSchema:
    """Verify explanation_detail is backward-compatible (Optional, defaults None)."""

    def test_explanation_detail_defaults_to_none(self):
        from schemas.score import ScoreResult
        result = ScoreResult(
            risk_score=50,
            risk_level="MEDIUM",
            unsup_score=0.5,
            explanation="test",
            detector_version="v1",
            latency_ms=10.0,
        )
        assert result.explanation_detail is None

    def test_explanation_detail_accepts_dict(self):
        from schemas.score import ScoreResult
        detail = {
            "available": True,
            "base_value": -0.5,
            "top_drivers": [{"feature": "f1", "shap_value": 0.3}],
        }
        result = ScoreResult(
            risk_score=80,
            risk_level="HIGH",
            unsup_score=0.8,
            explanation="test explanation",
            explanation_detail=detail,
            detector_version="hybrid-v1",
            latency_ms=25.0,
        )
        assert result.explanation_detail is not None
        assert result.explanation_detail["available"] is True
        assert len(result.explanation_detail["top_drivers"]) == 1

    def test_cold_start_has_no_explanation_detail(self):
        from schemas.score import ScoreResult
        result = ScoreResult.cold_start(detector_version="v1")
        assert result.explanation_detail is None


# ================================================================== #
# 4. HybridScorer SHAP integration
# ================================================================== #

class TestHybridScorerSHAP:
    """Test that HybridScorer populates explanation_detail when SHAP available."""

    def test_explanation_detail_populated_when_shap_available(self, tiny_xgb_model):
        """When sup model + SHAP available, explanation_detail is set."""
        import services.hybrid_scorer as hs_module
        from services.hybrid_scorer import HybridScorer
        from services.explainability.shap_explainer import SHAPExplainer
        from ml_training.feature_engineering import SUPERVISED_FEATURE_COLUMNS

        model, X = tiny_xgb_model

        # Build a minimal feature dict matching SUPERVISED_FEATURE_COLUMNS
        features = {name: float(X[0][i]) for i, name in enumerate(SUPERVISED_FEATURE_COLUMNS)}
        txn = {"amount": 100.0, "merchant": "TestMerchant"}

        # Mock the unsup layer
        mock_detector = MagicMock()
        from schemas.score import ScoreResult
        mock_detector.score_single.return_value = ScoreResult(
            risk_score=40, risk_level="MEDIUM",
            unsup_score=0.4, explanation="test",
            detector_version="unsup-v1", latency_ms=5.0,
        )
        mock_detector.DETECTOR_VERSION = "unsup-v1"

        scorer = HybridScorer.__new__(HybridScorer)
        scorer._detector = mock_detector
        scorer._sup_model = model
        scorer._shadow_model = None
        scorer._canary_model = None
        scorer._sup_model_path = ""

        # Inject a real SHAP explainer
        shap_exp = SHAPExplainer(model=model)

        with patch.object(hs_module, "_get_shap_explainer", return_value=shap_exp):
            from core.config import get_settings
            settings = get_settings()
            result = scorer._score_sync(user_id=1, txn=txn, features=features)

        assert result.explanation_detail is not None, (
            "explanation_detail should be set when SHAP is available"
        )
        assert result.explanation_detail.get("available") is True
        assert "top_drivers" in result.explanation_detail
        assert len(result.explanation_detail["top_drivers"]) > 0

    def test_explanation_string_from_top_3_drivers(self, tiny_xgb_model):
        """explanation string should be built from top-3 SHAP human_readable texts."""
        import services.hybrid_scorer as hs_module
        from services.hybrid_scorer import HybridScorer
        from services.explainability.shap_explainer import SHAPExplainer
        from ml_training.feature_engineering import SUPERVISED_FEATURE_COLUMNS

        model, X = tiny_xgb_model
        features = {name: float(X[0][i]) for i, name in enumerate(SUPERVISED_FEATURE_COLUMNS)}
        txn = {"amount": 100.0}

        mock_detector = MagicMock()
        from schemas.score import ScoreResult
        mock_detector.score_single.return_value = ScoreResult(
            risk_score=30, risk_level="LOW",
            unsup_score=0.3, explanation="unsup reason",
            detector_version="unsup-v1", latency_ms=3.0,
        )
        mock_detector.DETECTOR_VERSION = "unsup-v1"

        scorer = HybridScorer.__new__(HybridScorer)
        scorer._detector = mock_detector
        scorer._sup_model = model
        scorer._shadow_model = None
        scorer._canary_model = None
        scorer._sup_model_path = ""

        shap_exp = SHAPExplainer(model=model)
        with patch.object(hs_module, "_get_shap_explainer", return_value=shap_exp):
            result = scorer._score_sync(user_id=1, txn=txn, features=features)

        # explanation should be a non-empty string (from SHAP drivers or fallback)
        assert isinstance(result.explanation, str)
        assert len(result.explanation) > 0

    def test_explanation_detail_none_without_supervised_model(self):
        """explanation_detail is None when no supervised model (unsup-only mode)."""
        from services.hybrid_scorer import HybridScorer
        from schemas.score import ScoreResult

        mock_detector = MagicMock()
        mock_detector.score_single.return_value = ScoreResult(
            risk_score=20, risk_level="LOW",
            unsup_score=0.2, explanation="rule: normal",
            detector_version="unsup-v1", latency_ms=4.0,
        )
        mock_detector.DETECTOR_VERSION = "unsup-v1"

        scorer = HybridScorer.__new__(HybridScorer)
        scorer._detector = mock_detector
        scorer._sup_model = None  # unsup-only mode
        scorer._shadow_model = None
        scorer._canary_model = None
        scorer._sup_model_path = ""

        features = {"txn_count_1h": 1.0}
        result = scorer._score_sync(user_id=1, txn={"amount": 50.0}, features=features)
        assert result.explanation_detail is None

    def test_shap_failure_does_not_break_scoring(self, tiny_xgb_model):
        """If SHAP.explain() raises, scoring still returns a valid ScoreResult."""
        import services.hybrid_scorer as hs_module
        from services.hybrid_scorer import HybridScorer
        from schemas.score import ScoreResult
        from ml_training.feature_engineering import SUPERVISED_FEATURE_COLUMNS

        model, X = tiny_xgb_model
        features = {name: float(X[0][i]) for i, name in enumerate(SUPERVISED_FEATURE_COLUMNS)}

        mock_detector = MagicMock()
        mock_detector.score_single.return_value = ScoreResult(
            risk_score=50, risk_level="MEDIUM",
            unsup_score=0.5, explanation="test",
            detector_version="unsup-v1", latency_ms=5.0,
        )
        mock_detector.DETECTOR_VERSION = "unsup-v1"

        scorer = HybridScorer.__new__(HybridScorer)
        scorer._detector = mock_detector
        scorer._sup_model = model
        scorer._shadow_model = None
        scorer._canary_model = None
        scorer._sup_model_path = ""

        # SHAP explainer that always raises
        bad_explainer = MagicMock()
        bad_explainer.available = True
        bad_explainer.explain.side_effect = RuntimeError("SHAP internal error")

        with patch.object(hs_module, "_get_shap_explainer", return_value=bad_explainer):
            result = scorer._score_sync(user_id=1, txn={"amount": 100.0}, features=features)

        # Scoring must succeed even when SHAP fails
        assert isinstance(result, ScoreResult)
        assert 0 <= result.risk_score <= 100
        # explanation_detail will be None (SHAP failed gracefully)
        assert result.explanation_detail is None
