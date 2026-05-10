"""Phase 10 — GraphSAGE GNN tests.

Strategy
--------
* Graph builder & trainer use the real DB pool, so we mock that out at
  the call boundary (``services.phase_10_gnn.graph_builder.get_pool``)
  with synthetic rows.
* The model itself is purely numerical — no DB / Redis — so we can run
  it on a hand-built graph in-memory.
* Inference is mocked to test both the "Redis hit" and "DB fallback"
  paths without standing up either.

What we're verifying
--------------------
1. csr_to_torch_sparse converts correctly + handles empty matrices.
2. HeteroSAGEConv produces the expected output shape.
3. HeteroGraphSAGE forward() returns embeddings for every node type.
4. classify_users adds a 2-class head on user embeddings.
5. graph_builder skips empty rows and labels users by anomaly rate.
6. trainer bails out (trained=False) when there's not enough data.
7. inference returns embedding from Redis when available.
8. inference falls back to Postgres when Redis is unavailable.
9. inference returns None when both are empty.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
import torch
from scipy.sparse import csr_matrix


# ====================================================================== #
# Sparse + model unit tests
# ====================================================================== #
class TestSparseAndModel:
    def test_csr_to_torch_sparse_handles_empty(self) -> None:
        from services.phase_10_gnn.gnn_model import csr_to_torch_sparse
        m = csr_matrix((5, 7), dtype=np.float32)
        t = csr_to_torch_sparse(m)
        assert t.shape == (5, 7)
        assert t._nnz() == 0

    def test_csr_to_torch_sparse_row_normalises(self) -> None:
        from services.phase_10_gnn.gnn_model import csr_to_torch_sparse
        # User 0 has 2 merchants weighted 3 and 1 -> normalised to 0.75 / 0.25
        m = csr_matrix(np.array([[3.0, 1.0, 0.0], [0.0, 0.0, 4.0]], dtype=np.float32))
        t = csr_to_torch_sparse(m).to_dense()
        assert pytest.approx(float(t[0, 0])) == 0.75
        assert pytest.approx(float(t[0, 1])) == 0.25
        assert pytest.approx(float(t[1, 2])) == 1.0

    def test_hetero_sage_conv_shape(self) -> None:
        from services.phase_10_gnn.gnn_model import HeteroSAGEConv, csr_to_torch_sparse
        conv = HeteroSAGEConv(in_src=8, in_dst=8, out_dim=4)
        x_src = torch.randn(3, 8)
        x_dst = torch.randn(5, 8)
        adj = csr_to_torch_sparse(csr_matrix(np.ones((3, 5), dtype=np.float32)))
        out = conv(x_src, x_dst, adj)
        assert out.shape == (3, 4)

    def test_full_model_forward(self) -> None:
        from services.phase_10_gnn.gnn_model import HeteroGraphSAGE, csr_to_torch_sparse

        node_types = ["user", "merchant"]
        edge_types = [("user", "transactedWith", "merchant")]
        model = HeteroGraphSAGE(
            node_types=node_types, edge_types=edge_types,
            in_dim=4, hidden_dim=4, out_dim=4, num_layers=2,
        )
        x_dict = {"user": torch.randn(3, 4), "merchant": torch.randn(5, 4)}
        adj = {("user", "transactedWith", "merchant"):
               csr_to_torch_sparse(csr_matrix(np.ones((3, 5), dtype=np.float32)))}
        emb = model(x_dict, adj)
        assert emb["user"].shape == (3, 4)
        assert emb["merchant"].shape == (5, 4)
        logits, user_emb = model.classify_users(x_dict, adj)
        assert logits.shape == (3, 2)
        assert user_emb.shape == (3, 4)


# ====================================================================== #
# Graph builder
# ====================================================================== #
class TestGraphBuilder:
    @pytest.mark.asyncio
    async def test_builder_handles_empty_rows(self, monkeypatch) -> None:
        from services.phase_10_gnn import graph_builder as gb

        fake_conn = AsyncMock()
        fake_conn.fetchval = AsyncMock(return_value=0)   # no real fraud
        fake_conn.fetch = AsyncMock(return_value=[])

        class _Acquire:
            async def __aenter__(self): return fake_conn
            async def __aexit__(self, *args): return False
        fake_pool = MagicMock()
        fake_pool.acquire = MagicMock(return_value=_Acquire())
        monkeypatch.setattr(gb, "get_pool", lambda: fake_pool)

        g = await gb.build_graph(days=30)
        assert g.num_nodes["user"] == 0
        assert not g.is_trainable

    @pytest.mark.asyncio
    async def test_builder_labels_high_anomaly_users(self, monkeypatch) -> None:
        from services.phase_10_gnn import graph_builder as gb

        # User 1 -> mostly anomaly (8/10 = 80%) -> label 1
        # User 2 -> 0/10 anomalies -> label 0
        # User 3 -> 1/10 anomalies (10%) -> label 1
        rows: list[dict] = []
        def _row(uid: int, merch: str, lp: bool) -> dict:
            return {"user_id": uid, "merchant": merch, "category": "Food",
                    "location": "Home", "bank_name": "HDFC",
                    "device_id": None, "ip_address": None, "card_token": None,
                    "label_proxy": lp}
        for i in range(10):
            rows.append(_row(1, f"M{i % 3}", lp=(i < 8)))
            rows.append(_row(2, f"M{i % 4}", lp=False))
            rows.append(_row(3, f"M{i % 2}", lp=(i == 0)))

        fake_conn = AsyncMock()
        fake_conn.fetchval = AsyncMock(return_value=0)   # use anomaly_flag proxy
        fake_conn.fetch = AsyncMock(return_value=rows)

        class _Acquire:
            async def __aenter__(self): return fake_conn
            async def __aexit__(self, *args): return False
        fake_pool = MagicMock()
        fake_pool.acquire = MagicMock(return_value=_Acquire())
        monkeypatch.setattr(gb, "get_pool", lambda: fake_pool)

        g = await gb.build_graph(days=30)
        assert g.num_nodes["user"] == 3
        assert g.num_nodes["merchant"] >= 4
        assert g.is_trainable
        # User 1 (80%) and User 3 (10%) labelled 1; User 2 labelled 0
        labels = g.user_labels.tolist()
        u1_idx = g.node_id_maps["user"][1]
        u2_idx = g.node_id_maps["user"][2]
        u3_idx = g.node_id_maps["user"][3]
        assert labels[u1_idx] == 1
        assert labels[u2_idx] == 0
        assert labels[u3_idx] == 1


# ====================================================================== #
# Trainer
# ====================================================================== #
class TestTrainer:
    @pytest.mark.asyncio
    async def test_trainer_skips_when_graph_too_small(self, monkeypatch) -> None:
        from services.phase_10_gnn import trainer as tr
        from services.phase_10_gnn.graph_builder import GraphData

        empty = GraphData(
            num_nodes={"user": 1, "merchant": 0, "category": 0, "location": 0,
                        "bank": 0, "device": 0, "ip": 0, "card": 0},
            node_id_maps={"user": {1: 0}, "merchant": {}, "category": {},
                          "location": {}, "bank": {}, "device": {},
                          "ip": {}, "card": {}},
            edges={},
        )

        async def _fake_build(*a, **kw):
            return empty
        monkeypatch.setattr(tr, "build_graph", _fake_build)

        result = await tr.train_gnn(epochs=2)
        assert result["trained"] is False
        assert result["reason"] == "insufficient_graph_data"


# ====================================================================== #
# Inference
# ====================================================================== #
class TestInference:
    @pytest.mark.asyncio
    async def test_redis_hit(self, monkeypatch) -> None:
        from services.phase_10_gnn import inference as inf

        fake_redis = AsyncMock()
        fake_redis.get = AsyncMock(return_value="[0.1, 0.2, 0.3]")
        monkeypatch.setattr(inf, "get_redis", lambda: fake_redis)

        vec = await inf.get_user_embedding(42)
        assert vec == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_db_fallback_when_redis_empty(self, monkeypatch) -> None:
        from services.phase_10_gnn import inference as inf

        fake_redis = AsyncMock()
        fake_redis.get = AsyncMock(return_value=None)
        monkeypatch.setattr(inf, "get_redis", lambda: fake_redis)

        fake_conn = AsyncMock()
        fake_conn.fetchrow = AsyncMock(return_value={"embedding": [0.5, 0.6]})

        class _Acquire:
            async def __aenter__(self): return fake_conn
            async def __aexit__(self, *args): return False
        fake_pool = MagicMock()
        fake_pool.acquire = MagicMock(return_value=_Acquire())
        monkeypatch.setattr(inf, "get_pool", lambda: fake_pool)

        vec = await inf.get_user_embedding(99)
        assert vec == [0.5, 0.6]

    @pytest.mark.asyncio
    async def test_returns_none_when_unknown(self, monkeypatch) -> None:
        from services.phase_10_gnn import inference as inf

        fake_redis = AsyncMock()
        fake_redis.get = AsyncMock(return_value=None)
        monkeypatch.setattr(inf, "get_redis", lambda: fake_redis)

        fake_conn = AsyncMock()
        fake_conn.fetchrow = AsyncMock(return_value=None)

        class _Acquire:
            async def __aenter__(self): return fake_conn
            async def __aexit__(self, *args): return False
        fake_pool = MagicMock()
        fake_pool.acquire = MagicMock(return_value=_Acquire())
        monkeypatch.setattr(inf, "get_pool", lambda: fake_pool)

        vec = await inf.get_user_embedding(123)
        assert vec is None
