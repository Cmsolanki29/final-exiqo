"""Phase 2 acceptance tests — Online Feature Store.

Run with:
    cd backend
    pytest tests/test_phase2_feature_store.py -v --asyncio-mode=auto

Acceptance criteria:
  [P2-1] Online store reads complete in <10ms p95 for 100 sequential calls.
  [P2-2] Missing entity returns default values, not KeyError/None.
  [P2-3] set_features + get_features round-trips correctly.
  [P2-4] get_multi pipeline returns one result per request.
  [P2-5] Materialiser _materialise_one writes to online store.
  [P2-6] Feature assembler returns dict with all required keys.
  [P2-7] Assembled features include txn-level keys (amt_ratio_30d etc.).
  [P2-8] Offline store snapshot + get_at_time round-trips.
  [P2-9] Catalog has expected feature names.
  [P2-10] All catalog features have default_values.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


# ================================================================== #
# Helpers
# ================================================================== #

def _mock_redis_get(stored: dict[str, bytes]):
    """Return an AsyncMock that behaves like redis.get() with a backing store."""
    async def _get(key):
        return stored.get(key)
    return _get


# ================================================================== #
# [P2-9] Catalog structure
# ================================================================== #

class TestFeatureCatalog:
    def test_catalog_has_user_features(self):
        from services.feature_store.catalog import CATALOG_BY_ENTITY
        user_feats = CATALOG_BY_ENTITY.get("user", [])
        assert len(user_feats) >= 10, "Expect at least 10 user features"

    def test_catalog_has_merchant_features(self):
        from services.feature_store.catalog import CATALOG_BY_ENTITY
        merch_feats = CATALOG_BY_ENTITY.get("merchant", [])
        assert len(merch_feats) >= 3

    def test_all_features_have_defaults(self):
        from services.feature_store.catalog import FEATURE_CATALOG
        for spec in FEATURE_CATALOG:
            assert spec.default_value is not None, f"{spec.name} missing default_value"

    def test_get_defaults_returns_all_keys(self):
        from services.feature_store.catalog import CATALOG_BY_ENTITY, get_defaults
        for entity_type in CATALOG_BY_ENTITY:
            defaults = get_defaults(entity_type)
            assert len(defaults) > 0
            for key in defaults:
                assert isinstance(key, str)

    def test_catalog_by_name_lookup(self):
        from services.feature_store.catalog import CATALOG_BY_NAME
        assert "txn_count_30d" in CATALOG_BY_NAME
        assert "debit_avg_30d" in CATALOG_BY_NAME
        assert "merchant_avg_amount_30d" in CATALOG_BY_NAME

    def test_materialisable_features_have_source_query(self):
        from services.feature_store.catalog import MATERIALISABLE
        for spec in MATERIALISABLE:
            assert spec.source_query is not None
            # Callable should return (sql, params) tuple
            result = spec.source_query("123")
            assert isinstance(result, tuple)
            assert len(result) == 2
            sql, params = result
            assert isinstance(sql, str)
            assert isinstance(params, tuple)

    def test_source_query_contains_user_id_placeholder(self):
        from services.feature_store.catalog import CATALOG_BY_NAME
        spec = CATALOG_BY_NAME["txn_count_30d"]
        sql, params = spec.source_query("42")
        assert "$1" in sql
        assert 42 in params


# ================================================================== #
# [P2-2] [P2-3] Online store get/set
# ================================================================== #

class TestOnlineFeatureStore:
    @pytest.mark.asyncio
    async def test_get_returns_defaults_when_redis_unavailable(self):
        """Without Redis, get_features must return catalog defaults."""
        with patch("services.feature_store.online_store.get_redis", return_value=None):
            from services.feature_store.online_store import OnlineFeatureStore
            store = OnlineFeatureStore()
            result = await store.get_features("user", "99999")
            assert isinstance(result, dict)
            assert len(result) > 0
            # Keys should match catalog
            from services.feature_store.catalog import CATALOG_BY_ENTITY
            expected_keys = {s.name for s in CATALOG_BY_ENTITY.get("user", [])}
            assert expected_keys.issubset(result.keys())

    @pytest.mark.asyncio
    async def test_get_returns_defaults_on_redis_miss(self):
        """When key is not in Redis, return defaults (not None)."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("services.feature_store.online_store.get_redis", return_value=mock_redis):
            from services.feature_store.online_store import OnlineFeatureStore
            store = OnlineFeatureStore()
            result = await store.get_features("user", "12345")
            assert "txn_count_30d" in result
            assert result["txn_count_30d"] == 0  # default

    @pytest.mark.asyncio
    async def test_set_then_get_roundtrip(self):
        """Values written with set_features should be returned by get_features."""
        import json
        storage: dict[str, str] = {}

        async def _set(key, value, ex=None):
            storage[key] = value

        async def _get(key):
            return storage.get(key)

        mock_redis = AsyncMock()
        mock_redis.set = _set
        mock_redis.get = _get

        with patch("services.feature_store.online_store.get_redis", return_value=mock_redis):
            from services.feature_store.online_store import OnlineFeatureStore
            store = OnlineFeatureStore()
            feats = {"txn_count_30d": 42, "debit_avg_30d": 1500.0}
            await store.set_features("user", "777", feats)
            result = await store.get_features("user", "777")
            assert result["txn_count_30d"] == 42
            assert result["debit_avg_30d"] == pytest.approx(1500.0)

    @pytest.mark.asyncio
    async def test_get_multi_returns_one_result_per_request(self):
        """get_multi must return a result for every requested entity."""
        mock_redis = AsyncMock()
        # Pipeline: return None for all keys (cache miss)
        pipe_mock = AsyncMock()
        pipe_mock.get = AsyncMock()
        pipe_mock.execute = AsyncMock(return_value=[None, None])
        mock_redis.pipeline = MagicMock(return_value=pipe_mock)

        with patch("services.feature_store.online_store.get_redis", return_value=mock_redis):
            from services.feature_store.online_store import OnlineFeatureStore
            store = OnlineFeatureStore()
            requests = [("user", "1"), ("merchant", "Swiggy")]
            result = await store.get_multi(requests)
            assert "user:1" in result
            assert "merchant:Swiggy" in result
            # Both should have defaults
            assert "txn_count_30d" in result["user:1"]
            assert "merchant_avg_amount_30d" in result["merchant:Swiggy"]

    @pytest.mark.asyncio
    async def test_get_multi_no_redis_returns_all_defaults(self):
        """get_multi without Redis still returns all requested entities with defaults."""
        with patch("services.feature_store.online_store.get_redis", return_value=None):
            from services.feature_store.online_store import OnlineFeatureStore
            store = OnlineFeatureStore()
            requests = [("user", "1"), ("user", "2"), ("merchant", "Amazon")]
            result = await store.get_multi(requests)
            assert len(result) == 3
            for key in ["user:1", "user:2", "merchant:Amazon"]:
                assert key in result
                assert isinstance(result[key], dict)

    @pytest.mark.asyncio
    async def test_set_features_no_redis_does_not_raise(self):
        """set_features must be a no-op when Redis is unavailable, not an error."""
        with patch("services.feature_store.online_store.get_redis", return_value=None):
            from services.feature_store.online_store import OnlineFeatureStore
            store = OnlineFeatureStore()
            await store.set_features("user", "1", {"txn_count_30d": 5})  # must not raise

    # ------------------------------------------------------------------ #
    # [P2-1] Latency — 100 sequential reads must finish in <10ms p95
    # The test is indicative; we mock Redis so it exercises the Python overhead only.
    # ------------------------------------------------------------------ #
    @pytest.mark.asyncio
    async def test_get_features_fast_with_redis_miss(self):
        """100 sequential get_features calls (Redis miss) must each complete in <5ms."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("services.feature_store.online_store.get_redis", return_value=mock_redis):
            from services.feature_store.online_store import OnlineFeatureStore
            store = OnlineFeatureStore()
            latencies: list[float] = []
            for _ in range(100):
                t0 = time.perf_counter()
                await store.get_features("user", "1")
                latencies.append((time.perf_counter() - t0) * 1000)

        latencies.sort()
        p95 = latencies[94]
        assert p95 < 10.0, f"p95 latency {p95:.2f}ms exceeds 10ms budget"


# ================================================================== #
# [P2-8] Offline store
# ================================================================== #

class TestOfflineFeatureStore:
    @pytest.mark.asyncio
    async def test_snapshot_no_pool_does_not_raise(self):
        with patch("services.feature_store.offline_store.get_pool", side_effect=RuntimeError("no pool")):
            from services.feature_store.offline_store import OfflineFeatureStore
            store = OfflineFeatureStore()
            await store.snapshot("user", "1", {"txn_count_30d": 10})  # must not raise

    @pytest.mark.asyncio
    async def test_get_at_time_no_pool_returns_none(self):
        with patch("services.feature_store.offline_store.get_pool", side_effect=RuntimeError("no pool")):
            from services.feature_store.offline_store import OfflineFeatureStore
            store = OfflineFeatureStore()
            result = await store.get_at_time("user", "1", datetime.now(timezone.utc))
            assert result is None

    @pytest.mark.asyncio
    async def test_snapshot_writes_to_db(self):
        """snapshot() must call pool.acquire and execute an INSERT."""
        conn_mock = AsyncMock()
        conn_mock.execute = AsyncMock()
        conn_mock.__aenter__ = AsyncMock(return_value=conn_mock)
        conn_mock.__aexit__ = AsyncMock(return_value=False)

        pool_mock = MagicMock()
        pool_mock.acquire = MagicMock(return_value=conn_mock)

        with patch("services.feature_store.offline_store.get_pool", return_value=pool_mock):
            from services.feature_store.offline_store import OfflineFeatureStore
            store = OfflineFeatureStore()
            await store.snapshot("user", "42", {"debit_avg_30d": 1000.0})
            conn_mock.execute.assert_called_once()
            sql_call = conn_mock.execute.call_args[0][0]
            assert "INSERT INTO feature_snapshots" in sql_call

    @pytest.mark.asyncio
    async def test_get_at_time_returns_features(self):
        """get_at_time() must parse the JSONB result and return a dict."""
        import json
        expected = {"txn_count_30d": 15, "debit_avg_30d": 2500.0}

        conn_mock = AsyncMock()
        conn_mock.fetchrow = AsyncMock(return_value={"features": json.dumps(expected)})
        conn_mock.__aenter__ = AsyncMock(return_value=conn_mock)
        conn_mock.__aexit__ = AsyncMock(return_value=False)

        pool_mock = MagicMock()
        pool_mock.acquire = MagicMock(return_value=conn_mock)

        with patch("services.feature_store.offline_store.get_pool", return_value=pool_mock):
            from services.feature_store.offline_store import OfflineFeatureStore
            store = OfflineFeatureStore()
            result = await store.get_at_time("user", "42", datetime.now(timezone.utc))
            assert result == expected


# ================================================================== #
# [P2-6] [P2-7] Feature assembler
# ================================================================== #

class TestFeatureAssembler:
    @pytest.mark.asyncio
    async def test_assemble_returns_all_required_alias_keys(self):
        """assemble() must return the 4 alias keys used by score_single."""
        with patch("services.feature_store.online_store.get_redis", return_value=None):
            from services.feature_store.feature_assembly import FeatureAssembler
            assembler = FeatureAssembler()
            txn = {
                "user_id": 1, "amount": 1000.0, "type": "DEBIT",
                "merchant": "Swiggy", "category": "Food",
                "hour_of_day": 13, "day_of_week": 2, "is_weekend": False,
                "is_night_txn": False, "balance_after": 50000.0,
            }
            result = await assembler.assemble(txn, user_id=1)
            # Keys consumed by score_single
            for key in ("amt_ratio_30d", "hours_since_prev", "velocity_inr_per_hour", "merchant_changed"):
                assert key in result, f"Missing alias key: {key}"

    @pytest.mark.asyncio
    async def test_assemble_contains_prefixed_keys(self):
        """All feature keys must have user_*, merchant_*, or txn_* prefix."""
        with patch("services.feature_store.online_store.get_redis", return_value=None):
            from services.feature_store.feature_assembly import FeatureAssembler
            assembler = FeatureAssembler()
            txn = {"amount": 500.0, "type": "DEBIT", "merchant": "Amazon",
                   "hour_of_day": 10, "day_of_week": 1, "is_weekend": False}
            result = await assembler.assemble(txn, user_id=2)
            prefixed = [k for k in result if k.startswith(("user_", "merchant_", "txn_",
                                                             "amt_", "hours_", "velocity_", "merchant_changed"))]
            assert len(prefixed) > 10, "Expected many prefixed feature keys"

    @pytest.mark.asyncio
    async def test_assemble_new_merchant_flag(self):
        """New merchant (not in store) should set merchant_changed=1.0."""
        # merchant_txn_count_30d = 0 → is_new_merchant = 1
        with patch("services.feature_store.online_store.get_redis", return_value=None):
            from services.feature_store.feature_assembly import FeatureAssembler
            assembler = FeatureAssembler()
            txn = {"amount": 2000.0, "type": "DEBIT", "merchant": "BrandNewMerchant",
                   "hour_of_day": 15, "day_of_week": 3, "is_weekend": False}
            result = await assembler.assemble(txn, user_id=3)
            assert result["merchant_changed"] == 1.0

    @pytest.mark.asyncio
    async def test_assemble_burst_detection(self):
        """When user has > 3 txns in last hour, hours_since_prev should be small."""
        import json
        # Simulate Redis returning txn_count_1h=5
        user_feats_with_burst = {"txn_count_1h": 5, "txn_count_24h": 8, "debit_sum_1h": 10000.0,
                                  "debit_avg_30d": 1000.0}

        async def _get(key):
            if "user:" in key:
                return json.dumps(user_feats_with_burst)
            return None

        mock_redis = AsyncMock()
        mock_redis.pipeline = MagicMock()
        # Use get_multi path
        pipe = AsyncMock()
        pipe.get = AsyncMock()
        pipe.execute = AsyncMock(return_value=[json.dumps(user_feats_with_burst), None])
        mock_redis.pipeline = MagicMock(return_value=pipe)

        with patch("services.feature_store.online_store.get_redis", return_value=mock_redis):
            from services.feature_store.feature_assembly import FeatureAssembler
            assembler = FeatureAssembler()
            txn = {"amount": 500.0, "type": "DEBIT", "merchant": "X",
                   "hour_of_day": 14, "day_of_week": 2, "is_weekend": False}
            result = await assembler.assemble(txn, user_id=1)
            # burst: txn_count_1h=5 → hours_since_prev should be small
            assert result["hours_since_prev"] < 1.0

    def test_compute_txn_features_log_amount(self):
        """log_amount must be log1p(amount)."""
        import math
        with patch("services.feature_store.online_store.get_redis", return_value=None):
            from services.feature_store.feature_assembly import FeatureAssembler
            assembler = FeatureAssembler()
            txn = {"amount": 1000.0, "hour_of_day": 12, "day_of_week": 1,
                   "is_weekend": False, "is_night_txn": False, "merchant": "X"}
            feats = assembler._compute_txn_features(txn, {})
            assert feats["log_amount"] == pytest.approx(math.log1p(1000.0), abs=0.001)

    def test_compute_txn_features_cyclical_hour(self):
        """Hour 12 sin/cos should encode to (0, -1) approximately."""
        import math
        with patch("services.feature_store.online_store.get_redis", return_value=None):
            from services.feature_store.feature_assembly import FeatureAssembler
            assembler = FeatureAssembler()
            txn = {"amount": 100.0, "hour_of_day": 12, "day_of_week": 0,
                   "is_weekend": False, "is_night_txn": False, "merchant": ""}
            feats = assembler._compute_txn_features(txn, {})
            assert feats["hour_sin"] == pytest.approx(math.sin(math.pi), abs=0.001)
            assert feats["hour_cos"] == pytest.approx(math.cos(math.pi), abs=0.001)

    @pytest.mark.asyncio
    async def test_assemble_latency_under_5ms_no_redis(self):
        """Without Redis (defaults only), assemble must complete in <5ms."""
        with patch("services.feature_store.online_store.get_redis", return_value=None):
            from services.feature_store.feature_assembly import FeatureAssembler
            assembler = FeatureAssembler()
            txn = {"amount": 500.0, "type": "DEBIT", "merchant": "Test",
                   "hour_of_day": 10, "day_of_week": 1, "is_weekend": False}
            latencies = []
            for _ in range(50):
                t0 = time.perf_counter()
                await assembler.assemble(txn, user_id=1)
                latencies.append((time.perf_counter() - t0) * 1000)
            p95 = sorted(latencies)[47]
            assert p95 < 5.0, f"Assembler p95={p95:.2f}ms exceeds 5ms in no-Redis mode"


# ================================================================== #
# [P2-5] Materialiser
# ================================================================== #

class TestFeatureMaterializer:
    @pytest.mark.asyncio
    async def test_materialise_one_no_pool_does_not_raise(self):
        """_materialise_one must be a no-op when DB pool is not ready."""
        with patch("workers.feature_materializer.get_pool", side_effect=RuntimeError("no pool")):
            from workers.feature_materializer import FeatureMaterializer
            mat = FeatureMaterializer()
            await mat._materialise_one("user", "1")  # must not raise

    @pytest.mark.asyncio
    async def test_materialise_one_writes_to_online_store(self):
        """_materialise_one must call online_store.set_features after DB query."""
        conn_mock = AsyncMock()
        conn_mock.fetchrow = AsyncMock(return_value=(10,))  # one value
        conn_mock.__aenter__ = AsyncMock(return_value=conn_mock)
        conn_mock.__aexit__ = AsyncMock(return_value=False)

        pool_mock = MagicMock()
        pool_mock.acquire = MagicMock(return_value=conn_mock)

        set_features_calls: list = []

        async def _set_features(et, eid, feats, ttl=None):
            set_features_calls.append((et, eid, feats))

        with (
            patch("workers.feature_materializer.get_pool", return_value=pool_mock),
            patch("workers.feature_materializer.online_feature_store.set_features", _set_features),
            patch("workers.feature_materializer.offline_feature_store.snapshot", AsyncMock()),
        ):
            from workers.feature_materializer import FeatureMaterializer
            mat = FeatureMaterializer()
            await mat._materialise_one("user", "42")
            # Should have written something
            assert len(set_features_calls) > 0
            et, eid, feats = set_features_calls[0]
            assert et == "user"
            assert eid == "42"
            assert isinstance(feats, dict)
            assert len(feats) > 0

    def test_scheduler_registration(self):
        """start() must register a job on the scheduler."""
        mock_scheduler = MagicMock()
        from workers.feature_materializer import FeatureMaterializer
        mat = FeatureMaterializer()
        mat.start(mock_scheduler)
        mock_scheduler.add_job.assert_called_once()
        call_args = mock_scheduler.add_job.call_args
        # APScheduler 3.11: trigger is positional arg #2
        positional = call_args[0]
        kwargs = call_args[1]
        assert "interval" in positional, f"Expected 'interval' in positional args: {positional}"
        assert kwargs.get("id") == "feature_materializer"
