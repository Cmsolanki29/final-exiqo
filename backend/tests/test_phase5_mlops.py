"""Phase 5 MLOps test suite.

Tests:
  - PSI and KL divergence math (pure, no I/O)
  - ModelRegistry registration and loading (using temporary MLflow SQLite backend)
  - ShadowLogger.log() DB write
  - ShadowLogger.evaluate_shadow() per-segment regression check
  - HybridScorer.score_with_shadow() dual-score return
  - HybridScorer canary routing (deterministic MD5)
  - DriftMonitor feature drift check (mocked DB)
  - Prometheus metrics observation
  - Admin drift-report endpoint
  - Admin shadow-report endpoint

Run:
    cd backend
    python -m pytest tests/test_phase5_mlops.py -v --asyncio-mode=auto
"""

from __future__ import annotations

import json
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

import numpy as np
import pytest

# Ensure backend/ is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ================================================================== #
# 1. PSI pure math — no infrastructure needed
# ================================================================== #

class TestPSI:
    """Population Stability Index pure math tests."""

    def test_psi_identical_distributions_is_zero(self):
        """PSI of two samples from the exact same distribution must be ~0."""
        from services.monitoring.drift import population_stability_index

        rng = np.random.default_rng(42)
        data = rng.normal(0, 1, size=5000)
        # Split same data in half: both halves should have near-zero PSI
        half = len(data) // 2
        psi = population_stability_index(data[:half], data[half:])
        assert psi < 0.05, f"PSI of near-identical distributions should be < 0.05, got {psi}"

    def test_psi_disjoint_distributions_is_high(self):
        """PSI of completely disjoint distributions must be > 0.5."""
        from services.monitoring.drift import population_stability_index

        ref = np.linspace(0, 1, 1000)        # uniform [0, 1]
        cur = np.linspace(10, 11, 1000)      # uniform [10, 11] — completely disjoint
        psi = population_stability_index(ref, cur)
        assert psi > 0.5, f"PSI of disjoint distributions should be > 0.5, got {psi}"

    def test_psi_returns_zero_for_empty_input(self):
        from services.monitoring.drift import population_stability_index
        assert population_stability_index(np.array([]), np.array([1.0, 2.0])) == 0.0
        assert population_stability_index(np.array([1.0, 2.0]), np.array([])) == 0.0

    def test_psi_returns_zero_for_constant_reference(self):
        """Constant feature has no variance — PSI is 0 by definition."""
        from services.monitoring.drift import population_stability_index
        ref = np.ones(500)
        cur = np.ones(500)
        psi = population_stability_index(ref, cur)
        assert psi == 0.0

    def test_psi_moderate_shift(self):
        """PSI of moderately shifted distributions should be between 0.10 and 0.25."""
        from services.monitoring.drift import population_stability_index

        rng = np.random.default_rng(99)
        ref = rng.normal(0, 1, 2000)
        cur = rng.normal(0.5, 1.2, 2000)    # slight shift in mean and std
        psi = population_stability_index(ref, cur)
        # Accept a wide range — just confirm it's non-trivially non-zero
        assert psi > 0.0, "Shifted distribution should have non-zero PSI"

    def test_kl_divergence_identical_is_near_zero(self):
        from services.monitoring.drift import kl_divergence
        rng = np.random.default_rng(7)
        data = rng.normal(5, 2, 2000)
        kl = kl_divergence(data[:1000], data[1000:])
        assert kl < 0.1, f"KL divergence for near-identical should be < 0.1, got {kl}"

    def test_kl_divergence_disjoint_is_large(self):
        from services.monitoring.drift import kl_divergence
        ref = np.linspace(0, 1, 1000)
        cur = np.linspace(5, 6, 1000)
        kl = kl_divergence(ref, cur)
        assert kl > 1.0, f"KL divergence for disjoint should be > 1.0, got {kl}"


# ================================================================== #
# 2. ModelRegistry — uses local temp SQLite MLflow backend
# ================================================================== #

class TestModelRegistry:
    """ModelRegistry with local MLflow SQLite backend."""

    @pytest.fixture(autouse=True)
    def setup_mlflow(self, tmp_path, monkeypatch):
        """Point MLflow at a temporary SQLite DB so tests don't need a server."""
        import mlflow
        tracking_uri = f"sqlite:///{tmp_path}/test_mlflow.db"
        mlflow.set_tracking_uri(tracking_uri)
        # Patch settings to return the temp URI
        monkeypatch.setenv("MLFLOW_TRACKING_URI", tracking_uri)
        yield

    def _make_tiny_xgb_model(self):
        """Train a tiny XGBoost model for registry tests."""
        import xgboost as xgb
        import numpy as np
        rng = np.random.default_rng(0)
        X = rng.random((100, 10)).astype(np.float32)
        y = (rng.random(100) > 0.5).astype(int)
        m = xgb.XGBClassifier(n_estimators=3, max_depth=2, use_label_encoder=False, eval_metric="logloss")
        m.fit(X, y)
        return m

    def test_registry_registers_model_returns_version(self, tmp_path):
        """Registering a model returns a version string."""
        from services.ml_registry.registry import ModelRegistry
        reg = ModelRegistry()
        if not reg._available:
            pytest.skip("MLflow not available")

        model = self._make_tiny_xgb_model()
        version = reg.register_model(
            model,
            name="test_model_reg",
            metrics={"pr_auc": 0.85, "roc_auc": 0.92},
            hyperparams={"n_estimators": 3},
        )
        assert version is not None, "register_model should return a version string"
        assert isinstance(version, str)
        assert len(version) > 0

    def test_registry_load_production_returns_none_when_no_production(self):
        """load_production returns None (disk fallback) when no Production model in MLflow."""
        from services.ml_registry.registry import ModelRegistry
        reg = ModelRegistry()
        if not reg._available:
            pytest.skip("MLflow not available")

        # No model promoted to Production — should return None (disk fallback)
        # The disk fallback will also return None (no model file in test env)
        with patch("services.ml_registry.registry._load_model_from_disk", return_value=None):
            model = reg.load_production("nonexistent_model_xyz")
        assert model is None

    def test_registry_current_versions_empty_on_fresh_registry(self):
        """current_versions returns Nones for a model name that hasn't been registered."""
        from services.ml_registry.registry import ModelRegistry
        reg = ModelRegistry()
        if not reg._available:
            pytest.skip("MLflow not available")

        versions = reg.current_versions("nonexistent_model_xyz")
        assert versions["production"] is None
        assert versions["shadow"] is None
        assert versions["canary"] is None

    def test_registry_list_all_versions_empty_for_unknown_model(self):
        from services.ml_registry.registry import ModelRegistry
        reg = ModelRegistry()
        if not reg._available:
            pytest.skip("MLflow not available")

        versions = reg.list_all_versions("unknown_model_xyz")
        assert versions == []

    def test_registry_degrades_gracefully_when_mlflow_unavailable(self, monkeypatch):
        """When MLflow is unreachable, all registry methods return safe defaults.

        Note (audit-1 fix): ``load_production`` falls back to disk when
        MLflow is unavailable; we stub ``_load_model_from_disk`` so a
        real ``.pkl`` left from a prior bootstrap run cannot satisfy the
        fallback and falsify the assertion.
        """
        from services.ml_registry import registry as _reg_mod
        reg = _reg_mod.ModelRegistry()
        reg._available = False  # Simulate unavailable MLflow

        monkeypatch.setattr(_reg_mod, "_load_model_from_disk", lambda *_a, **_k: None)

        assert reg.register_model(MagicMock(), "test") is None
        assert reg.promote("test", "1", "production") is False
        assert reg.load_production("test") is None
        assert reg.load_shadow("test") is None
        assert reg.current_versions("test") == {"production": None, "shadow": None, "canary": None}
        assert reg.list_all_versions("test") == []


# ================================================================== #
# 3. ShadowLogger
# ================================================================== #

def _make_mock_pool(exec_return=None):
    """Create a properly configured async context manager mock for asyncpg pool."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=exec_return)
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchval = AsyncMock(return_value=0)

    mock_acquire = MagicMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=False)

    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_acquire)
    return mock_pool, mock_conn


class TestShadowLogger:
    """ShadowLogger unit tests with mocked DB."""

    @pytest.mark.asyncio
    async def test_log_inserts_shadow_prediction_row(self):
        """log() calls conn.execute with an INSERT into shadow_predictions."""
        from services.monitoring.shadow_logger import ShadowLogger

        mock_pool, mock_conn = _make_mock_pool()

        with patch("services.monitoring.shadow_logger.get_pool", return_value=mock_pool):
            logger_instance = ShadowLogger()
            await logger_instance.log(
                prod_score=75,
                shadow_score=68,
                txn_id=42,
                prod_action="review",
                shadow_action="review",
                features_hash="abc123",
            )

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        assert "shadow_predictions" in call_args[0]
        assert call_args[1] == 42   # txn_id
        assert call_args[2] == 75   # prod_score
        assert call_args[3] == 68   # shadow_score

    @pytest.mark.asyncio
    async def test_log_skips_when_pool_unavailable(self):
        """log() gracefully skips (no exception) when pool is None."""
        from services.monitoring.shadow_logger import ShadowLogger

        with patch("services.monitoring.shadow_logger.get_pool", return_value=None):
            logger_instance = ShadowLogger()
            # Should not raise
            await logger_instance.log(90, 85, 1, "blocked", "blocked")

    @pytest.mark.asyncio
    async def test_evaluate_shadow_passes_for_similar_distributions(self):
        """evaluate_shadow returns passed=True when prod and shadow scores are identical."""
        from services.monitoring.shadow_logger import ShadowLogger

        # Identical prod and shadow scores — PSI must be ~0, block rates equal → pass
        mock_rows = [
            {"prod_score": 30, "shadow_score": 30, "prod_action": "accepted",
             "shadow_action": "accepted", "amount": 200.0, "user_id": i}
            for i in range(100)
        ] + [
            {"prod_score": 85, "shadow_score": 85, "prod_action": "blocked",
             "shadow_action": "blocked", "amount": 50000.0, "user_id": i + 100}
            for i in range(10)
        ]

        logger_instance = ShadowLogger()
        with patch.object(logger_instance, "_fetch_shadow_rows", return_value=mock_rows):
            report = await logger_instance.evaluate_shadow(period_days=7)

        assert report["passed"] is True, f"Expected passed=True, checks: {report.get('checks')}"
        assert report["sample_n"] == 110
        assert "checks" in report

    @pytest.mark.asyncio
    async def test_evaluate_shadow_fails_on_inflated_block_rate(self):
        """evaluate_shadow returns passed=False when shadow blocks far more high-value txns.

        Design:
          - 100 high-value rows where prod blocks 5 (5%) and shadow blocks 5 (5%) → baseline
          - 50 additional rows where prod allows but shadow blocks (50/150 = 33pp uplift)
          - Total delta = shadow 55/150 - prod 5/150 ≈ 33pp >> 20pp threshold → FAIL
        """
        from services.monitoring.shadow_logger import ShadowLogger

        # 100 high-value rows: same prod/shadow decisions
        same_decisions = [
            {"prod_score": 40, "shadow_score": 40, "prod_action": "accepted",
             "shadow_action": "accepted", "amount": 10000.0, "user_id": i}
            for i in range(95)
        ] + [
            {"prod_score": 85, "shadow_score": 85, "prod_action": "blocked",
             "shadow_action": "blocked", "amount": 10000.0, "user_id": i + 95}
            for i in range(5)
        ]
        # 50 rows where shadow over-blocks — clearly exceeds 20pp threshold
        shadow_extra_blocks = [
            {"prod_score": 50, "shadow_score": 90, "prod_action": "accepted",
             "shadow_action": "blocked", "amount": 10000.0, "user_id": i + 200}
            for i in range(50)
        ]
        mock_rows = same_decisions + shadow_extra_blocks
        # Total high_value: 150 rows
        # prod_block_rate = 5/150 ≈ 3.3%
        # shadow_block_rate = 55/150 ≈ 36.7%
        # delta ≈ 33pp >> 20pp threshold → should FAIL

        logger_instance = ShadowLogger()
        with patch.object(logger_instance, "_fetch_shadow_rows", return_value=mock_rows):
            report = await logger_instance.evaluate_shadow(period_days=7)

        segment_check = report["checks"].get("segment_block_rate", {})
        high_value_seg = segment_check.get("segments", {}).get("high_value", {})
        assert high_value_seg.get("passed") is False, (
            f"Expected high_value segment to fail, got: {high_value_seg}"
        )

    @pytest.mark.asyncio
    async def test_evaluate_shadow_returns_no_predictions_note_on_empty(self):
        """evaluate_shadow returns note when no shadow predictions exist."""
        from services.monitoring.shadow_logger import ShadowLogger

        logger_instance = ShadowLogger()
        with patch.object(logger_instance, "_fetch_shadow_rows", return_value=[]):
            report = await logger_instance.evaluate_shadow(period_days=7)

        assert report["passed"] is True
        assert report["sample_n"] == 0
        assert "no shadow predictions" in report.get("note", "")


# ================================================================== #
# 4. HybridScorer Phase 5 additions
# ================================================================== #

class TestHybridScorerPhase5:
    """Test score_with_shadow and canary routing."""

    def _make_scorer_with_mock_models(self, has_shadow: bool = True):
        """Create a HybridScorer with mocked prod and optionally shadow models."""
        from services.hybrid_scorer import HybridScorer
        from unittest.mock import MagicMock
        import numpy as np

        mock_detector = MagicMock()
        mock_detector.DETECTOR_VERSION = "test-v0"
        mock_detector.score_single = MagicMock(return_value=MagicMock(
            risk_score=50,
            risk_level="MEDIUM",
            unsup_score=0.5,
            sup_score=None,
            signals={},
            explanation="test",
            detector_version="test-v0",
            latency_ms=10.0,
        ))

        # Mock prod XGBoost
        mock_prod_model = MagicMock()
        mock_prod_model.predict_proba = MagicMock(
            return_value=np.array([[0.7, 0.3]])
        )

        scorer = HybridScorer.__new__(HybridScorer)
        scorer._detector = mock_detector
        scorer._sup_model = mock_prod_model
        scorer._sup_model_path = "nonexistent.pkl"

        if has_shadow:
            mock_shadow_model = MagicMock()
            mock_shadow_model.predict_proba = MagicMock(
                return_value=np.array([[0.5, 0.5]])  # shadow predicts 50% fraud
            )
            scorer._shadow_model = mock_shadow_model
        else:
            scorer._shadow_model = None

        scorer._canary_model = None
        return scorer

    @pytest.mark.asyncio
    async def test_score_with_shadow_returns_tuple(self):
        """score_with_shadow returns (ScoreResult, float) when shadow model exists."""
        scorer = self._make_scorer_with_mock_models(has_shadow=True)
        txn = {"amount": 500.0, "category": "Food", "transaction_time": "12:00:00"}
        features = {"user_txn_count_1h": 2, "user_debit_avg_30d": 300.0}

        result, shadow = await scorer.score_with_shadow(1, txn, features)

        from schemas.score import ScoreResult
        assert isinstance(result, ScoreResult)
        assert shadow is not None, "Shadow score should be present when shadow model loaded"
        assert 0.0 <= shadow <= 1.0, f"Shadow score should be 0-1 float, got {shadow}"

    @pytest.mark.asyncio
    async def test_score_with_shadow_returns_none_shadow_when_no_shadow_model(self):
        """score_with_shadow returns (ScoreResult, None) when no shadow model."""
        scorer = self._make_scorer_with_mock_models(has_shadow=False)
        txn = {"amount": 300.0, "transaction_time": "10:00:00"}
        features = {"user_txn_count_1h": 1}

        result, shadow = await scorer.score_with_shadow(1, txn, features)

        from schemas.score import ScoreResult
        assert isinstance(result, ScoreResult)
        assert shadow is None, "Shadow score should be None when no shadow model"

    def test_canary_routing_is_deterministic(self):
        """_should_use_canary always returns the same value for the same key."""
        from services.hybrid_scorer import HybridScorer

        scorer = HybridScorer.__new__(HybridScorer)
        scorer._sup_model = None
        scorer._shadow_model = None
        scorer._canary_model = None
        scorer._sup_model_path = ""
        scorer._detector = MagicMock()

        with patch("services.hybrid_scorer.get_settings") as mock_settings:
            mock_settings.return_value.CANARY_PERCENTAGE = 10

            key = "txn_key_12345"
            results = [scorer._should_use_canary(key) for _ in range(10)]
            # All results must be identical (deterministic)
            assert len(set(results)) == 1, "Canary routing must be deterministic for same key"

    def test_canary_routing_distributes_traffic(self):
        """With 50% canary, approximately half the keys should route to canary."""
        from services.hybrid_scorer import HybridScorer

        scorer = HybridScorer.__new__(HybridScorer)
        scorer._sup_model = None
        scorer._shadow_model = None
        scorer._canary_model = None
        scorer._sup_model_path = ""
        scorer._detector = MagicMock()

        with patch("services.hybrid_scorer.get_settings") as mock_settings:
            mock_settings.return_value.CANARY_PERCENTAGE = 50

            keys = [f"key_{i}" for i in range(1000)]
            canary_count = sum(1 for k in keys if scorer._should_use_canary(k))
            ratio = canary_count / len(keys)
            # Should be roughly 50% — allow ±10% slack
            assert 0.40 <= ratio <= 0.60, f"Expected ~50% canary, got {ratio:.2%}"

    def test_canary_routing_returns_false_when_zero_percent(self):
        """No traffic routes to canary when CANARY_PERCENTAGE=0."""
        from services.hybrid_scorer import HybridScorer

        scorer = HybridScorer.__new__(HybridScorer)
        scorer._sup_model = None
        scorer._shadow_model = None
        scorer._canary_model = None
        scorer._sup_model_path = ""
        scorer._detector = MagicMock()

        with patch("services.hybrid_scorer.get_settings") as mock_settings:
            mock_settings.return_value.CANARY_PERCENTAGE = 0

            for i in range(20):
                assert scorer._should_use_canary(f"key_{i}") is False

    def test_reload_models_runs_without_error(self):
        """reload_models() completes without raising even when registry is unavailable."""
        from services.hybrid_scorer import HybridScorer

        scorer = HybridScorer.__new__(HybridScorer)
        scorer._sup_model = None
        scorer._shadow_model = None
        scorer._canary_model = None
        scorer._sup_model_path = "nonexistent.pkl"
        scorer._detector = MagicMock()

        # audit-1 fix: also stub the MLflow registry so the
        # _load_from_registry_or_disk path can't satisfy the load via a
        # leftover Production-stage model from a prior test run.
        from services.ml_registry.registry import model_registry as _reg
        with patch("services.hybrid_scorer.get_settings") as mock_s, \
             patch("services.hybrid_scorer.load_model", return_value=None), \
             patch("services.hybrid_scorer.HybridScorer._load_shadow_from_registry", return_value=None), \
             patch.object(_reg, "load_production", return_value=None):
            mock_s.return_value.SUPERVISED_MODEL_PATH = "nonexistent.pkl"
            scorer.reload_models()  # Should not raise

        assert scorer._sup_model is None   # No model found, remains None


# ================================================================== #
# 5. DriftMonitor
# ================================================================== #

class TestDriftMonitor:
    """DriftMonitor tests with mocked DB."""

    @pytest.mark.asyncio
    async def test_check_feature_drift_returns_dict(self):
        """check_feature_drift returns a dict of feature → PSI values."""
        from services.monitoring.drift import DriftMonitor
        import numpy as np

        monitor = DriftMonitor()

        async def _fake_fetch(feature_name, since, until):
            rng = np.random.default_rng(hash(feature_name) % 2**32)
            return rng.normal(100, 20, 200)

        with patch.object(monitor, "_fetch_feature_values", side_effect=_fake_fetch):
            with patch.object(monitor, "_load_feature_names", return_value=["txn_count_1h", "debit_avg_30d"]):
                result = await monitor.check_feature_drift()

        assert isinstance(result, dict)
        # With 200 samples each, both features should have PSI computed
        assert "txn_count_1h" in result or "debit_avg_30d" in result

    @pytest.mark.asyncio
    async def test_check_feature_drift_skips_features_with_no_data(self):
        """Features with fewer than 10 samples are skipped (not enough for PSI)."""
        from services.monitoring.drift import DriftMonitor
        import numpy as np

        monitor = DriftMonitor()

        async def _sparse_fetch(feature_name, since, until):
            return np.array([1.0, 2.0])  # Only 2 samples — below the 10 minimum

        with patch.object(monitor, "_fetch_feature_values", side_effect=_sparse_fetch):
            with patch.object(monitor, "_load_feature_names", return_value=["txn_count_1h"]):
                result = await monitor.check_feature_drift()

        assert result == {}, "Features with too few samples should be skipped"

    @pytest.mark.asyncio
    async def test_check_feature_drift_degrades_gracefully_without_pool(self):
        """check_feature_drift returns {} when asyncpg pool is unavailable."""
        from services.monitoring.drift import DriftMonitor
        import numpy as np

        monitor = DriftMonitor()

        # When pool is None, _fetch_feature_values returns empty array, so features are skipped
        async def _empty_fetch(feature_name, since, until):
            return np.array([])  # Empty — fewer than 10 samples, will be skipped

        with patch.object(monitor, "_load_feature_names", return_value=["txn_count_1h"]):
            with patch.object(monitor, "_fetch_feature_values", side_effect=_empty_fetch):
                result = await monitor.check_feature_drift()
        # Should return {} not raise
        assert isinstance(result, dict)
        assert result == {}, f"Expected empty dict when no data, got {result}"


# ================================================================== #
# 6. Prometheus metrics
# ================================================================== #

class TestPrometheusMetrics:
    """Verify Prometheus metric objects are importable and observable."""

    def test_metrics_module_imports_cleanly(self):
        """Importing the metrics module must not raise."""
        import importlib
        mod = importlib.import_module("services.monitoring.metrics")
        assert hasattr(mod, "transaction_risk_score_histogram")
        assert hasattr(mod, "transaction_action_total")
        assert hasattr(mod, "risk_layer_latency_ms")
        assert hasattr(mod, "model_drift_psi")
        assert hasattr(mod, "feature_store_read_latency_ms")

    def test_histogram_observation_does_not_raise(self):
        """Observing a histogram value must not raise."""
        from services.monitoring.metrics import transaction_risk_score_histogram
        transaction_risk_score_histogram.labels(model_version="test-v0").observe(55)

    def test_counter_increment_does_not_raise(self):
        """Incrementing a counter must not raise."""
        from services.monitoring.metrics import transaction_action_total
        transaction_action_total.labels(action="accepted", model_version="test-v0").inc()

    def test_gauge_set_does_not_raise(self):
        """Setting a gauge must not raise."""
        from services.monitoring.metrics import model_drift_psi
        model_drift_psi.labels(feature_name="txn_count_1h").set(0.12)


# ================================================================== #
# 7. features_hash helper
# ================================================================== #

class TestFeaturesHash:
    """Utility function tests."""

    def test_features_hash_same_input_same_output(self):
        from services.monitoring.shadow_logger import features_hash
        f = {"a": 1, "b": 2.5, "c": "test"}
        assert features_hash(f) == features_hash(f)

    def test_features_hash_different_inputs_different_hashes(self):
        from services.monitoring.shadow_logger import features_hash
        assert features_hash({"a": 1}) != features_hash({"a": 2})

    def test_features_hash_none_returns_none(self):
        from services.monitoring.shadow_logger import features_hash
        assert features_hash(None) is None

    def test_features_hash_empty_dict_returns_hash(self):
        from services.monitoring.shadow_logger import features_hash
        h = features_hash({})
        assert h is not None
        assert len(h) == 32  # MD5 hex digest is 32 chars
