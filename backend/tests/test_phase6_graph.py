"""Phase 6 Graph / Network Signals test suite.

Tests:
  - GraphFeatureService: device_user_count, ip_user_count (from MVs)
  - GraphFeatureService: find_fraud_ring — finds connected fraud users
  - GraphFeatureService: shortest_path_to_fraud (levels 0, 1, 2, -1)
  - GraphFeatureService: connected_component_size
  - GraphFeatureService: get_network_summary
  - GraphFeatureService: graceful degradation when pool unavailable
  - FeatureCatalog: graph feature specs present and well-formed
  - graph features included in assembled feature vector (via online store)
  - refresh_materialized_views executes correct SQL

Run:
    cd backend
    python -m pytest tests/test_phase6_graph.py -v --asyncio-mode=auto
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _make_mock_pool(*fetch_side_effects):
    """Build a mock asyncpg pool whose conn methods return preset values."""
    mock_conn = AsyncMock()
    mock_acquire = MagicMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=False)
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_acquire)
    return mock_pool, mock_conn


# ================================================================== #
# 1. Feature catalog — graph specs
# ================================================================== #

class TestGraphFeatureCatalog:
    """Verify the 6 graph features are properly registered in the catalog."""

    def test_graph_features_present_in_catalog(self):
        from services.feature_store.catalog import FEATURE_CATALOG, CATALOG_BY_NAME
        graph_names = [
            "graph_device_count_30d",
            "graph_ip_count_7d",
            "graph_max_device_user_count",
            "graph_max_ip_user_count",
            "graph_shortest_path_to_fraud",
            "graph_component_size",
        ]
        for name in graph_names:
            assert name in CATALOG_BY_NAME, f"{name} not found in FEATURE_CATALOG"

    def test_graph_features_have_user_entity_type(self):
        from services.feature_store.catalog import CATALOG_BY_NAME
        graph_names = [
            "graph_device_count_30d", "graph_ip_count_7d",
            "graph_max_device_user_count", "graph_max_ip_user_count",
            "graph_shortest_path_to_fraud", "graph_component_size",
        ]
        for name in graph_names:
            spec = CATALOG_BY_NAME[name]
            assert spec.entity_type == "user", f"{name} should have entity_type='user'"

    def test_graph_features_have_correct_defaults(self):
        from services.feature_store.catalog import CATALOG_BY_NAME
        assert CATALOG_BY_NAME["graph_device_count_30d"].default_value == 0
        assert CATALOG_BY_NAME["graph_ip_count_7d"].default_value == 0
        assert CATALOG_BY_NAME["graph_shortest_path_to_fraud"].default_value == -1.0
        assert CATALOG_BY_NAME["graph_component_size"].default_value == 1

    def test_graph_features_have_none_source_query(self):
        """Graph features must have source_query=None — handled by GraphFeatureService."""
        from services.feature_store.catalog import CATALOG_BY_NAME
        graph_names = [
            "graph_device_count_30d", "graph_ip_count_7d",
            "graph_max_device_user_count", "graph_max_ip_user_count",
            "graph_shortest_path_to_fraud", "graph_component_size",
        ]
        for name in graph_names:
            assert CATALOG_BY_NAME[name].source_query is None, (
                f"{name} should have source_query=None (handled by GraphFeatureService)"
            )

    def test_total_catalog_size_includes_graph(self):
        """Catalog should have at least 35 features (Phase 2 baseline + 6 graph)."""
        from services.feature_store.catalog import FEATURE_CATALOG
        assert len(FEATURE_CATALOG) >= 35, (
            f"Catalog should have at least 35 features, got {len(FEATURE_CATALOG)}"
        )


# ================================================================== #
# 2. GraphFeatureService — unit tests with mocked DB
# ================================================================== #

class TestGraphFeatureService:
    """Unit tests for GraphFeatureService with mocked asyncpg pool."""

    # ---- Device / IP count ---- #

    @pytest.mark.asyncio
    async def test_device_count_30d(self):
        """_device_count_30d returns correct count from DB."""
        from services.graph.graph_features import GraphFeatureService

        svc = GraphFeatureService()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=3)

        count = await svc._device_count_30d(mock_conn, user_id=1)
        assert count == 3

    @pytest.mark.asyncio
    async def test_device_count_returns_zero_on_null(self):
        """_device_count_30d returns 0 when DB returns None."""
        from services.graph.graph_features import GraphFeatureService

        svc = GraphFeatureService()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=None)

        count = await svc._device_count_30d(mock_conn, user_id=1)
        assert count == 0

    @pytest.mark.asyncio
    async def test_max_device_user_count_from_mv(self):
        """_max_device_user_count reads from mv_device_user_count and returns max."""
        from services.graph.graph_features import GraphFeatureService

        svc = GraphFeatureService()
        mock_conn = AsyncMock()
        # Simulate: user shares a device with 5 other users
        mock_conn.fetchval = AsyncMock(return_value=5)

        result = await svc._max_device_user_count(mock_conn, user_id=1)
        assert result == 5, (
            f"Device shared by 5 users → max_device_user_count should be 5, got {result}"
        )

    @pytest.mark.asyncio
    async def test_max_ip_user_count_from_mv(self):
        """_max_ip_user_count reads from mv_ip_user_count_24h."""
        from services.graph.graph_features import GraphFeatureService

        svc = GraphFeatureService()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=12)

        result = await svc._max_ip_user_count(mock_conn, user_id=1)
        assert result == 12

    # ---- Shortest path to fraud ---- #

    @pytest.mark.asyncio
    async def test_shortest_path_returns_0_for_fraud_user(self):
        """User with fraud transactions → distance 0."""
        from services.graph.graph_features import GraphFeatureService

        svc = GraphFeatureService()
        mock_conn = AsyncMock()
        # First fetchval: is self-fraud? → True
        mock_conn.fetchval = AsyncMock(return_value=True)

        path = await svc._shortest_path_to_fraud(mock_conn, user_id=1)
        assert path == 0

    @pytest.mark.asyncio
    async def test_shortest_path_returns_1_for_direct_neighbor(self):
        """User shares merchant with fraud user → distance 1."""
        from services.graph.graph_features import GraphFeatureService

        svc = GraphFeatureService()
        mock_conn = AsyncMock()
        # is self-fraud? → False; hop1 exists? → True
        mock_conn.fetchval = AsyncMock(side_effect=[False, True])

        path = await svc._shortest_path_to_fraud(mock_conn, user_id=2)
        assert path == 1

    @pytest.mark.asyncio
    async def test_shortest_path_returns_2_for_two_hops(self):
        """User is two merchant hops from fraud → distance 2."""
        from services.graph.graph_features import GraphFeatureService

        svc = GraphFeatureService()
        mock_conn = AsyncMock()
        # is self-fraud? → False; hop1? → False; hop2? → True
        mock_conn.fetchval = AsyncMock(side_effect=[False, False, True])

        path = await svc._shortest_path_to_fraud(mock_conn, user_id=3)
        assert path == 2

    @pytest.mark.asyncio
    async def test_shortest_path_returns_minus_1_when_no_path(self):
        """User has no path to fraud → distance -1."""
        from services.graph.graph_features import GraphFeatureService

        svc = GraphFeatureService()
        mock_conn = AsyncMock()
        # is self-fraud? → False; hop1? → False; hop2? → False
        mock_conn.fetchval = AsyncMock(side_effect=[False, False, False])

        path = await svc._shortest_path_to_fraud(mock_conn, user_id=4)
        assert path == -1

    # ---- Connected component size ---- #

    @pytest.mark.asyncio
    async def test_connected_component_size_includes_self(self):
        """Component size = neighbors + 1 (self)."""
        from services.graph.graph_features import GraphFeatureService

        svc = GraphFeatureService()
        mock_conn = AsyncMock()
        # 4 distinct neighbors
        mock_conn.fetch = AsyncMock(return_value=[
            {"user_id": 10}, {"user_id": 11}, {"user_id": 12}, {"user_id": 13}
        ])

        size = await svc._connected_component_size(mock_conn, user_id=1)
        assert size == 5  # 4 neighbors + self

    @pytest.mark.asyncio
    async def test_connected_component_size_isolated_user(self):
        """Isolated user (no shared merchants) → component size 1."""
        from services.graph.graph_features import GraphFeatureService

        svc = GraphFeatureService()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        size = await svc._connected_component_size(mock_conn, user_id=99)
        assert size == 1

    # ---- find_fraud_ring ---- #

    @pytest.mark.asyncio
    async def test_find_fraud_ring_returns_connected_fraud_users(self):
        """find_fraud_ring returns user IDs that are connected AND fraud-flagged."""
        import services.graph.graph_features as gf_module
        from services.graph.graph_features import GraphFeatureService

        svc = GraphFeatureService()

        # User 1 shares merchant with users 2, 3, 4
        # User 2 is a fraud user, 3 and 4 are not
        async def _fake_neighbors(conn, user_ids, exclude):
            if 1 in user_ids:
                return {2, 3, 4} - exclude
            return set()

        async def _fake_filter_fraud(conn, user_ids):
            return [uid for uid in user_ids if uid == 2]

        mock_pool, mock_conn = _make_mock_pool()

        with patch.object(gf_module, "get_pool", return_value=mock_pool):
            with patch.object(svc, "_neighbors_via_shared_entities", side_effect=_fake_neighbors):
                with patch.object(svc, "_filter_fraud_users", side_effect=_fake_filter_fraud):
                    ring = await svc.find_fraud_ring(user_id=1, depth=2)

        assert 2 in ring, "Fraud user 2 should be in the ring"
        assert 3 not in ring, "Non-fraud user 3 should not be in the ring"
        assert 1 not in ring, "Starting user should not be in the ring"

    @pytest.mark.asyncio
    async def test_find_fraud_ring_returns_empty_when_no_fraud_neighbors(self):
        """find_fraud_ring returns [] when none of the neighbors are fraud users."""
        import services.graph.graph_features as gf_module
        from services.graph.graph_features import GraphFeatureService

        svc = GraphFeatureService()

        async def _fake_neighbors(conn, user_ids, exclude):
            return {10, 11} - exclude

        async def _fake_filter_fraud(conn, user_ids):
            return []  # no fraud users among neighbors

        mock_pool, mock_conn = _make_mock_pool()

        with patch.object(gf_module, "get_pool", return_value=mock_pool):
            with patch.object(svc, "_neighbors_via_shared_entities", side_effect=_fake_neighbors):
                with patch.object(svc, "_filter_fraud_users", side_effect=_fake_filter_fraud):
                    ring = await svc.find_fraud_ring(user_id=1, depth=2)

        assert ring == []

    @pytest.mark.asyncio
    async def test_find_fraud_ring_returns_empty_when_pool_unavailable(self):
        """find_fraud_ring degrades gracefully when pool is None."""
        import services.graph.graph_features as gf_module
        from services.graph.graph_features import GraphFeatureService

        svc = GraphFeatureService()
        with patch.object(gf_module, "get_pool", return_value=None):
            ring = await svc.find_fraud_ring(user_id=1, depth=2)
        assert ring == []

    # ---- compute_user_graph_features ---- #

    @pytest.mark.asyncio
    async def test_compute_user_graph_features_returns_all_6_keys(self):
        """compute_user_graph_features returns all 6 graph feature keys."""
        import services.graph.graph_features as gf_module
        from services.graph.graph_features import GraphFeatureService, GRAPH_FEATURE_NAMES

        svc = GraphFeatureService()

        mock_pool, mock_conn = _make_mock_pool()
        with patch.object(gf_module, "get_pool", return_value=mock_pool):
            with patch.object(svc, "_device_count_30d", return_value=2):
                with patch.object(svc, "_ip_count_7d", return_value=1):
                    with patch.object(svc, "_max_device_user_count", return_value=3):
                        with patch.object(svc, "_max_ip_user_count", return_value=0):
                            with patch.object(svc, "_shortest_path_to_fraud", return_value=1):
                                with patch.object(svc, "_connected_component_size", return_value=5):
                                    result = await svc.compute_user_graph_features(user_id=1)

        for key in GRAPH_FEATURE_NAMES:
            assert key in result, f"Missing graph feature: {key}"

    @pytest.mark.asyncio
    async def test_compute_user_graph_features_returns_defaults_when_pool_unavailable(self):
        """compute_user_graph_features returns defaults when pool is None."""
        import services.graph.graph_features as gf_module
        from services.graph.graph_features import GraphFeatureService, _DEFAULT_GRAPH_FEATURES

        svc = GraphFeatureService()
        with patch.object(gf_module, "get_pool", return_value=None):
            result = await svc.compute_user_graph_features(user_id=1)

        assert result == _DEFAULT_GRAPH_FEATURES

    @pytest.mark.asyncio
    async def test_compute_user_graph_features_all_floats(self):
        """All returned graph feature values are floats."""
        import services.graph.graph_features as gf_module
        from services.graph.graph_features import GraphFeatureService

        svc = GraphFeatureService()
        mock_pool, _ = _make_mock_pool()

        with patch.object(gf_module, "get_pool", return_value=mock_pool):
            with patch.object(svc, "_device_count_30d", return_value=1):
                with patch.object(svc, "_ip_count_7d", return_value=0):
                    with patch.object(svc, "_max_device_user_count", return_value=5):
                        with patch.object(svc, "_max_ip_user_count", return_value=2):
                            with patch.object(svc, "_shortest_path_to_fraud", return_value=-1):
                                with patch.object(svc, "_connected_component_size", return_value=3):
                                    result = await svc.compute_user_graph_features(1)

        for key, val in result.items():
            assert isinstance(val, float), f"{key} should be float, got {type(val)}"


# ================================================================== #
# 3. Graph features in assembled feature vector
# ================================================================== #

class TestGraphFeaturesInAssembledVector:
    """Verify graph features flow from online store into the assembled feature vector."""

    @pytest.mark.asyncio
    async def test_graph_features_returned_by_feature_assembler(self):
        """When online store contains graph features, assembler includes them (prefixed user_*)."""
        from services.feature_store.feature_assembly import FeatureAssembler
        from services.feature_store.online_store import online_feature_store

        assembler = FeatureAssembler()

        # The assembler calls get_multi which returns {entity_key: features_dict}
        # User features are stored under key "user:1"; assembler prefixes them with "user_"
        fake_user_features = {
            "txn_count_1h": 2,
            "debit_avg_30d": 500.0,
            "graph_device_count_30d": 1.0,
            "graph_ip_count_7d": 0.0,
            "graph_max_device_user_count": 3.0,
            "graph_max_ip_user_count": 0.0,
            "graph_shortest_path_to_fraud": 1.0,
            "graph_component_size": 4.0,
        }

        txn = {
            "user_id": 1,
            "amount": 200.0,
            "merchant": "Starbucks",
            "category": "Food",
            "transaction_date": "2025-01-01",
            "transaction_time": "10:00:00",
        }

        # get_multi returns {entity_key: feature_dict} where key = "user:1"
        fake_multi_result = {
            "user:1": fake_user_features,
            "merchant:Starbucks": {},
        }
        with patch.object(online_feature_store, "get_multi", return_value=fake_multi_result):
            result = await assembler.assemble(txn, user_id=1)

        # Assembler prefixes user entity keys with "user_"
        # So "graph_device_count_30d" becomes "user_graph_device_count_30d"
        present = {k for k in result if "graph_" in k}
        assert len(present) >= 4, (
            f"Expected at least 4 graph features (prefixed) in assembled vector, found: {present}"
        )
        # Verify the prefixed keys exist
        assert "user_graph_device_count_30d" in result
        assert "user_graph_shortest_path_to_fraud" in result


# ================================================================== #
# 4. Feature materializer — graph pass
# ================================================================== #

class TestFeatureMaterializerGraphPass:
    """Verify the materializer's graph features pass calls GraphFeatureService."""

    @pytest.mark.asyncio
    async def test_materialise_graph_features_updates_online_store(self):
        """_materialise_graph_features merges graph features into user's online store entry."""
        from workers.feature_materializer import FeatureMaterializer
        from services.feature_store import online_store as _ols
        from services.feature_store import offline_store as _offs

        materializer = FeatureMaterializer()

        mock_graph_svc = AsyncMock()
        mock_graph_svc.compute_user_graph_features = AsyncMock(return_value={
            "graph_device_count_30d": 2.0,
            "graph_ip_count_7d": 1.0,
            "graph_max_device_user_count": 5.0,
            "graph_max_ip_user_count": 0.0,
            "graph_shortest_path_to_fraud": -1.0,
            "graph_component_size": 3.0,
        })

        existing_user_features = {"txn_count_1h": 3, "debit_avg_30d": 400.0}

        with patch.object(
            _ols.online_feature_store, "get_features",
            return_value=existing_user_features,
        ), patch.object(
            _ols.online_feature_store, "set_features",
            return_value=None,
        ) as mock_set, patch.object(
            _offs.offline_feature_store, "snapshot",
            return_value=None,
        ):
            await materializer._materialise_graph_features("1", mock_graph_svc)

        # Verify online store was updated with merged features
        mock_set.assert_called_once()
        _entity_type, _entity_id, written_features = mock_set.call_args[0]
        assert "graph_device_count_30d" in written_features
        assert written_features["graph_device_count_30d"] == 2.0
        # Original features should be preserved
        assert "txn_count_1h" in written_features

    @pytest.mark.asyncio
    async def test_materialise_graph_features_skips_invalid_entity_id(self):
        """_materialise_graph_features skips non-integer entity IDs gracefully."""
        from workers.feature_materializer import FeatureMaterializer

        materializer = FeatureMaterializer()
        mock_graph_svc = AsyncMock()

        # Should not raise, should not call graph service
        await materializer._materialise_graph_features("not_an_int", mock_graph_svc)
        mock_graph_svc.compute_user_graph_features.assert_not_called()


# ================================================================== #
# 5. MV refresh
# ================================================================== #

class TestMaterializedViewRefresh:
    """Verify refresh_materialized_views executes REFRESH MATERIALIZED VIEW."""

    @pytest.mark.asyncio
    async def test_refresh_executes_for_all_5_views(self):
        """refresh_materialized_views calls REFRESH for all 5 phase-6 MVs."""
        import services.graph.graph_features as gf_module
        from services.graph.graph_features import GraphFeatureService

        svc = GraphFeatureService()
        mock_pool, mock_conn = _make_mock_pool()
        mock_conn.execute = AsyncMock(return_value=None)

        with patch.object(gf_module, "get_pool", return_value=mock_pool):
            result = await svc.refresh_materialized_views()

        expected_views = {
            "mv_device_user_count",
            "mv_user_device_count",
            "mv_ip_user_count_24h",
            "mv_user_ip_count_7d",
            "mv_card_user_count",
        }
        assert set(result.keys()) == expected_views
        assert all(result.values()), f"Some MVs failed to refresh: {result}"

    @pytest.mark.asyncio
    async def test_refresh_degrades_gracefully_when_pool_unavailable(self):
        """refresh_materialized_views returns {} when pool is None."""
        import services.graph.graph_features as gf_module
        from services.graph.graph_features import GraphFeatureService

        svc = GraphFeatureService()
        with patch.object(gf_module, "get_pool", return_value=None):
            result = await svc.refresh_materialized_views()

        assert result == {}

    @pytest.mark.asyncio
    async def test_refresh_records_failure_per_view(self):
        """refresh_materialized_views marks individual views as failed on error."""
        import services.graph.graph_features as gf_module
        from services.graph.graph_features import GraphFeatureService

        svc = GraphFeatureService()
        mock_pool, mock_conn = _make_mock_pool()

        call_count = 0

        async def _failing_execute(sql):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("REFRESH MATERIALIZED VIEW error: relation does not exist")

        mock_conn.execute = _failing_execute

        with patch.object(gf_module, "get_pool", return_value=mock_pool):
            result = await svc.refresh_materialized_views()

        # First view should have failed, rest should have succeeded
        values = list(result.values())
        assert values[0] is False  # first refresh failed
        assert all(values[1:])     # rest succeeded


# ================================================================== #
# 6. Graph feature names constant
# ================================================================== #

class TestGraphFeatureNames:
    """GRAPH_FEATURE_NAMES constant consistency check."""

    def test_graph_feature_names_matches_catalog(self):
        from services.graph.graph_features import GRAPH_FEATURE_NAMES
        from services.feature_store.catalog import CATALOG_BY_NAME
        for name in GRAPH_FEATURE_NAMES:
            assert name in CATALOG_BY_NAME, (
                f"GRAPH_FEATURE_NAMES includes '{name}' but it's not in FEATURE_CATALOG"
            )

    def test_graph_feature_names_has_6_entries(self):
        from services.graph.graph_features import GRAPH_FEATURE_NAMES
        assert len(GRAPH_FEATURE_NAMES) == 6
