"""GraphSAGE training pipeline.

The trainer is intentionally honest about the regime it operates in:

* If the graph has fewer than ``PHASE_10_MIN_USERS_FOR_TRAINING`` users
  it bails out with ``trained=False`` and a clear ``reason``.  This is
  the difference between "we trained and it didn't work" and "we declined
  to train because the data wasn't there" — important for the model card.

* The loss function blends two terms:

    L = unsup * (1 - w)  +  sup * w           (w = PHASE_10_SUPERVISED_LOSS_WEIGHT)

  - **Unsupervised** (always available):  classic SAGE-style negative
    sampling — a user-merchant edge in the graph should score higher
    than a random non-edge.  This works even with zero labels and is
    the backbone of what the model actually learns at our data scale.
  - **Supervised** (when labels exist):  cross-entropy on a 2-class
    user head using the proxy labels from the graph builder.

* Training runs entirely on CPU and finishes in a few seconds for the
  current data size.  No GPU dependency.

Outputs
-------
1. Embeddings → Redis (``gnn:user_emb:{user_id}``, TTL = settings.
   PHASE_10_EMBED_TTL_SEC) **and** the ``gnn_user_embeddings`` table
   (durable).
2. A run row in ``gnn_training_runs`` with the loss curve and metadata.
3. Returns a JSON-serialisable dict suitable for the admin endpoint.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

from core.config import get_settings
from core.db import get_pool
from core.redis import get_redis
from services.phase_10_gnn.gnn_model import HeteroGraphSAGE, csr_to_torch_sparse
from services.phase_10_gnn.graph_builder import (
    EDGE_USER_MERCHANT,
    GraphData,
    build_graph,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def _initial_features(num_nodes: dict[str, int], dim: int,
                       seed: int = 42) -> dict[str, torch.Tensor]:
    """Each node type gets a deterministic random embedding to start.

    For ``user``, where we have a small, fixed set, we use a one-hot-style
    init to give the model maximal initial discriminability.
    """
    g = torch.Generator().manual_seed(seed)
    out: dict[str, torch.Tensor] = {}
    for nt, n in num_nodes.items():
        if n == 0:
            out[nt] = torch.zeros((0, dim), dtype=torch.float32)
            continue
        if nt == "user" and n <= dim:
            x = torch.zeros((n, dim), dtype=torch.float32)
            for i in range(n):
                x[i, i] = 1.0
            out[nt] = x
        else:
            out[nt] = torch.randn((n, dim), generator=g, dtype=torch.float32) * 0.1
    return out


def _negative_sample_pairs(
    pos_rows: np.ndarray,
    pos_cols: np.ndarray,
    n_src: int,
    n_dst: int,
    n_neg: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample ``n_neg`` random ``(src, dst)`` pairs that are NOT in the
    positive edge set.  Used for the contrastive loss.
    """
    pos_set = set(zip(pos_rows.tolist(), pos_cols.tolist()))
    neg_rows: list[int] = []
    neg_cols: list[int] = []
    while len(neg_rows) < n_neg:
        r = int(rng.integers(0, n_src))
        c = int(rng.integers(0, n_dst))
        if (r, c) in pos_set:
            continue
        neg_rows.append(r)
        neg_cols.append(c)
    return np.asarray(neg_rows, dtype=np.int64), np.asarray(neg_cols, dtype=np.int64)


# ---------------------------------------------------------------------- #
# audit-5: real-label count helper
# ---------------------------------------------------------------------- #
async def _count_real_fraud_labels() -> int:
    """Return the number of confirmed ``transactions.is_fraud=TRUE`` rows.

    Best-effort: if the DB pool is unavailable we conservatively return
    0 so the proxy-disabled guard fails closed (refuses to train).
    """
    try:
        pool = await get_pool()
        if pool is None:
            return 0
        async with pool.acquire() as conn:
            row = await conn.fetchval(
                "SELECT COUNT(*) FROM transactions WHERE is_fraud = TRUE"
            )
            return int(row or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("phase_10: real-label count failed (%s) — "
                        "treating as 0", exc)
        return 0


# ---------------------------------------------------------------------- #
# Persistence
# ---------------------------------------------------------------------- #
async def _persist_embeddings(
    user_idx: dict[Any, int],
    embeddings: torch.Tensor,
    model_version: str,
    ttl_sec: int,
) -> int:
    """Write each user's embedding to Redis (fast) + Postgres (durable).

    Returns the number of users actually persisted.  Both paths are
    best-effort: a missing Redis or DB just means we lean on the other.
    """
    redis = get_redis()
    pool_ok = True
    pool = None
    try:
        pool = get_pool()
    except RuntimeError:
        pool_ok = False

    written = 0
    rev_idx = {idx: uid for uid, idx in user_idx.items()}
    embed_dim = embeddings.shape[1]

    # ---- Redis ---- #
    if redis is not None:
        try:
            for idx, uid in rev_idx.items():
                vec = embeddings[idx].detach().cpu().tolist()
                await redis.setex(
                    f"gnn:user_emb:{uid}",
                    ttl_sec,
                    json.dumps(vec),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("phase_10: redis embedding write failed: %s", exc)

    # ---- Postgres (durable fallback / source of truth across restarts) ---- #
    if pool_ok and pool is not None:
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for idx, uid in rev_idx.items():
                        vec = embeddings[idx].detach().cpu().tolist()
                        await conn.execute(
                            """
                            INSERT INTO gnn_user_embeddings
                                (user_id, embedding, embed_dim, model_version, updated_at)
                            VALUES ($1, $2::real[], $3, $4, NOW())
                            ON CONFLICT (user_id) DO UPDATE SET
                                embedding     = EXCLUDED.embedding,
                                embed_dim     = EXCLUDED.embed_dim,
                                model_version = EXCLUDED.model_version,
                                updated_at    = NOW()
                            """,
                            int(uid), vec, embed_dim, model_version,
                        )
                        written += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("phase_10: postgres embedding write failed: %s", exc)

    return written


async def _record_run(run_id: uuid.UUID, payload: dict[str, Any]) -> None:
    """Insert a row into ``gnn_training_runs``.  Best-effort."""
    try:
        pool = get_pool()
    except RuntimeError:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO gnn_training_runs (
                    id, model_version,
                    num_users, num_merchants, edge_counts, label_source,
                    labelled_users, txn_window_days,
                    embed_dim, num_layers, epochs, lr,
                    final_loss, sup_loss, unsup_loss, train_acc,
                    loss_history, embeddings_written, duration_sec,
                    error, started_at, completed_at
                ) VALUES (
                    $1, $2,
                    $3, $4, $5::jsonb, $6,
                    $7, $8,
                    $9, $10, $11, $12,
                    $13, $14, $15, $16,
                    $17::jsonb, $18, $19,
                    $20, $21, $22
                )
                """,
                run_id,
                payload["model_version"],
                payload["num_users"], payload["num_merchants"],
                json.dumps(payload["edge_counts"]),
                payload["label_source"],
                payload["labelled_users"],
                payload["txn_window_days"],
                payload["embed_dim"], payload["num_layers"],
                payload["epochs"], payload["lr"],
                payload.get("final_loss"), payload.get("sup_loss"),
                payload.get("unsup_loss"), payload.get("train_acc"),
                json.dumps(payload.get("loss_history", [])),
                payload.get("embeddings_written", 0),
                payload.get("duration_sec", 0.0),
                payload.get("error"),
                payload.get("started_at"),
                payload.get("completed_at"),
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("phase_10: gnn_training_runs insert failed: %s", exc)


# ---------------------------------------------------------------------- #
# Public entry point
# ---------------------------------------------------------------------- #
async def train_gnn(
    *,
    days: int | None = None,
    epochs: int | None = None,
    lr: float | None = None,
) -> dict[str, Any]:
    """Build the graph, train SAGE, persist embeddings, log the run.

    Always returns a JSON-serialisable dict.  Never raises out — failure
    paths are recorded as ``trained=False`` + ``reason``.
    """
    settings = get_settings()
    started_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    started_at_perf = time.perf_counter()

    days = int(days if days is not None else settings.PHASE_10_TRAINING_DAYS)
    epochs = int(epochs if epochs is not None else settings.PHASE_10_EPOCHS)
    lr = float(lr if lr is not None else settings.PHASE_10_LR)
    embed_dim = int(settings.PHASE_10_EMBED_DIM)
    num_layers = int(settings.PHASE_10_NUM_LAYERS)
    sup_w = float(settings.PHASE_10_SUPERVISED_LOSS_WEIGHT)
    min_users = int(settings.PHASE_10_MIN_USERS_FOR_TRAINING)
    embed_ttl = int(settings.PHASE_10_EMBED_TTL_SEC)

    # ---- audit-5: real-label guard (anti-contamination) ---- #
    # If we do NOT have enough real `is_fraud=TRUE` labels and the
    # operator has NOT explicitly opted into the proxy fallback, refuse
    # to train.  Anomaly_flag is the OUTPUT of Phase 1 — using it as a
    # supervised label would teach the GNN to mimic Phase 1's mistakes,
    # not detect fraud.  See models/cards/fraud_gnn_v1.md.
    if not bool(settings.PHASE_10_ALLOW_PROXY_LABEL):
        real_count = await _count_real_fraud_labels()
        if real_count < int(settings.PHASE_10_MIN_REAL_LABELS):
            return {
                "trained": False,
                "reason": "insufficient_real_labels_proxy_disabled",
                "real_label_count": int(real_count),
                "required": int(settings.PHASE_10_MIN_REAL_LABELS),
                "hint": (
                    "Set PHASE_10_ALLOW_PROXY_LABEL=true to train on "
                    "anomaly_flag as a proxy (academic-only — see "
                    "fraud_gnn_v1.md for the contamination disclosure)."
                ),
                "duration_sec": time.perf_counter() - started_at_perf,
            }

    # ---- Build graph ---- #
    try:
        graph: GraphData = await build_graph(days=days)
    except Exception as exc:  # noqa: BLE001
        logger.warning("phase_10: graph build failed: %s", exc)
        return {
            "trained": False,
            "reason": f"graph_build_failed: {exc}",
            "duration_sec": time.perf_counter() - started_at_perf,
        }

    n_users = graph.num_nodes.get("user", 0)
    if n_users < min_users or not graph.is_trainable:
        return {
            "trained": False,
            "reason": "insufficient_graph_data",
            "graph_stats": graph.stats,
            "min_users": min_users,
            "duration_sec": time.perf_counter() - started_at_perf,
        }

    # ---- Build sparse adjacency tensors ---- #
    adj_dict: dict[tuple[str, str, str], torch.Tensor] = {}
    for key, m in graph.edges.items():
        adj_dict[key] = csr_to_torch_sparse(m)

    # ---- Init features + model ---- #
    x_dict = _initial_features(graph.num_nodes, embed_dim)
    model = HeteroGraphSAGE(
        node_types=list(graph.num_nodes.keys()),
        edge_types=list(graph.edges.keys()),
        in_dim=embed_dim,
        hidden_dim=embed_dim,
        out_dim=embed_dim,
        num_layers=num_layers,
        dropout=0.1,
    )
    optim = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)

    # ---- Pre-extract user-merchant edges for contrastive loss ---- #
    if EDGE_USER_MERCHANT in graph.edges:
        um_coo = graph.edges[EDGE_USER_MERCHANT].tocoo()
        pos_rows = um_coo.row.astype(np.int64)
        pos_cols = um_coo.col.astype(np.int64)
        n_dst_um = graph.num_nodes["merchant"]
    else:
        # Pick the first edge type as the contrastive anchor — but always
        # prefer user-merchant since that's the densest.
        any_key = next(iter(graph.edges))
        coo = graph.edges[any_key].tocoo()
        pos_rows = coo.row.astype(np.int64)
        pos_cols = coo.col.astype(np.int64)
        n_dst_um = graph.num_nodes[any_key[2]]

    rng = np.random.default_rng(42)

    labels = graph.user_labels if graph.user_labels is not None else torch.zeros(0)
    train_mask = graph.train_mask if graph.train_mask is not None else torch.zeros(0, dtype=torch.bool)
    has_supervised = train_mask.numel() > 0 and bool(train_mask.any().item())

    loss_history: list[float] = []
    sup_loss_val: float | None = None
    unsup_loss_val: float | None = None
    train_acc_val: float | None = None

    # ---- Train ---- #
    try:
        model.train()
        n_pos = len(pos_rows)
        n_neg = max(n_pos, 32)  # at least a small handful of negatives

        for epoch in range(epochs):
            optim.zero_grad()
            logits, user_emb = model.classify_users(x_dict, adj_dict)

            # ----- Unsupervised contrastive loss on user-merchant edges ----- #
            if EDGE_USER_MERCHANT in graph.edges and n_pos > 0:
                merch_emb = model.forward(x_dict, adj_dict)["merchant"]
                pos_score = (user_emb[pos_rows] * merch_emb[pos_cols]).sum(dim=1)
                neg_r, neg_c = _negative_sample_pairs(
                    pos_rows, pos_cols, graph.num_nodes["user"], n_dst_um, n_neg, rng
                )
                neg_score = (user_emb[neg_r] * merch_emb[neg_c]).sum(dim=1)
                # max-margin / BPR-style loss
                margin = 1.0
                unsup_loss = F.relu(margin - pos_score + neg_score.mean()).mean()
            else:
                unsup_loss = torch.tensor(0.0)

            # ----- Supervised cross-entropy on labelled users ----- #
            if has_supervised:
                sup_loss = F.cross_entropy(
                    logits[train_mask], labels[train_mask].long()
                )
            else:
                sup_loss = torch.tensor(0.0)

            if has_supervised and EDGE_USER_MERCHANT in graph.edges:
                loss = (1.0 - sup_w) * unsup_loss + sup_w * sup_loss
            elif has_supervised:
                loss = sup_loss
            else:
                loss = unsup_loss

            loss.backward()
            optim.step()
            loss_history.append(float(loss.item()))

        # Final outputs
        with torch.no_grad():
            model.eval()
            final_logits, user_emb_final = model.classify_users(x_dict, adj_dict)
            sup_loss_val = float(sup_loss.item()) if has_supervised else None
            unsup_loss_val = float(unsup_loss.item()) if EDGE_USER_MERCHANT in graph.edges else None
            if has_supervised:
                preds = final_logits.argmax(dim=1)
                train_acc_val = float(
                    (preds[train_mask] == labels[train_mask]).float().mean().item()
                )

    except Exception as exc:  # noqa: BLE001
        logger.warning("phase_10: training failed: %s", exc, exc_info=True)
        return {
            "trained": False,
            "reason": f"training_error: {exc}",
            "graph_stats": graph.stats,
            "duration_sec": time.perf_counter() - started_at_perf,
        }

    # L2-normalise embeddings before persisting — makes downstream cosine
    # similarity / dot-product comparisons stable and lets us pre-mix
    # them into Phase 3's feature vector without re-scaling.
    user_emb_norm = F.normalize(user_emb_final, p=2, dim=1)

    # ---- Persist ---- #
    model_version = "v1-" + uuid.uuid4().hex[:8]
    written = await _persist_embeddings(
        graph.node_id_maps["user"], user_emb_norm, model_version, embed_ttl
    )

    duration = float(time.perf_counter() - started_at_perf)
    completed_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    payload = {
        "trained": True,
        "model_version": model_version,
        "num_users": int(graph.num_nodes["user"]),
        "num_merchants": int(graph.num_nodes.get("merchant", 0)),
        "edge_counts": {f"{s}__{r}__{d}": int(m.nnz) for (s, r, d), m in graph.edges.items()},
        "label_source": graph.label_proxy_source,
        "labelled_users": int((labels != -1).sum().item()) if labels.numel() > 0 else 0,
        "txn_window_days": graph.txn_window_days,
        "embed_dim": embed_dim,
        "num_layers": num_layers,
        "epochs": epochs,
        "lr": lr,
        "final_loss": loss_history[-1] if loss_history else None,
        "sup_loss": sup_loss_val,
        "unsup_loss": unsup_loss_val,
        "train_acc": train_acc_val,
        "loss_history": loss_history,
        "embeddings_written": int(written),
        "duration_sec": duration,
        "started_at": started_iso,
        "completed_at": completed_iso,
        "graph_stats": graph.stats,
        "redis_used": get_redis() is not None,
    }

    await _record_run(uuid.uuid4(), payload)
    logger.info(
        "phase_10.train_done version=%s users=%d final_loss=%.4f duration=%.2fs",
        model_version, payload["num_users"],
        payload["final_loss"] or 0.0, duration,
    )
    return payload
