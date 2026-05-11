"""Build a heterogeneous graph from the transactions table.

Node types
----------
* user      — every distinct ``user_id``
* merchant  — every distinct ``merchant``
* category  — every distinct ``category``
* location  — every distinct ``location``
* bank      — every distinct ``bank_name``

Optional (added when columns are populated; silently skipped otherwise):
* device, ip, card

Edge types (always undirected for SAGE aggregation)
---------------------------------------------------
* (user, transactedWith, merchant)   weight = txn count
* (user, spentIn,        category)
* (user, locatedAt,      location)
* (user, banksAt,        bank)
* (user, usedDevice,     device)         when device_id is populated
* (user, fromIp,         ip)             when ip_address is populated
* (user, ownsCard,       card)           when card_token is populated

Output
------
A ``GraphData`` value object with:
* ``num_nodes``          — dict[str, int] keyed by node type
* ``node_id_maps``       — dict[str, dict[raw_id, idx]] for each type
* ``edges``              — dict[(src_type, rel, dst_type), (rows, cols, vals)]
                            stored as scipy ``csr_matrix`` (src x dst)
* ``user_labels``        — torch.tensor of shape (num_users,), -1 = unlabeled
* ``train_mask``         — bool tensor, True where label != -1

Why pure-PyTorch + scipy.sparse and not torch_geometric?
--------------------------------------------------------
PyG's wheel install is fragile on Windows / Python 3.13.  Our scoring app
must build green on every checkout, so we run our own SAGE-mean
aggregation against ``scipy.sparse.csr_matrix`` adjacency matrices.  The
math is identical; the architecture is identical; only the package
boundary differs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import torch
from scipy.sparse import csr_matrix

from core.db import get_pool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------- #
# Edge keys
# ---------------------------------------------------------------------- #
EDGE_USER_MERCHANT = ("user", "transactedWith", "merchant")
EDGE_USER_CATEGORY = ("user", "spentIn", "category")
EDGE_USER_LOCATION = ("user", "locatedAt", "location")
EDGE_USER_BANK = ("user", "banksAt", "bank")
EDGE_USER_DEVICE = ("user", "usedDevice", "device")
EDGE_USER_IP = ("user", "fromIp", "ip")
EDGE_USER_CARD = ("user", "ownsCard", "card")

EdgeKey = tuple[str, str, str]


@dataclass
class GraphData:
    """Plain-old-data carrier for a built heterogeneous graph."""

    num_nodes: dict[str, int]
    node_id_maps: dict[str, dict[Any, int]]
    edges: dict[EdgeKey, csr_matrix] = field(default_factory=dict)
    user_labels: torch.Tensor | None = None
    train_mask: torch.Tensor | None = None
    label_proxy_source: str = "anomaly_flag"
    txn_window_days: int = 0

    @property
    def is_trainable(self) -> bool:
        """A graph is trainable when we have at least 3 user nodes
        and at least one edge type with edges.  Below that the GNN is
        overfitting noise."""
        if self.num_nodes.get("user", 0) < 3:
            return False
        return any(m.nnz > 0 for m in self.edges.values())

    @property
    def stats(self) -> dict[str, Any]:
        """Pretty summary, used by /train response and tests."""
        edge_counts = {f"{s}_{r}_{d}": int(m.nnz) for (s, r, d), m in self.edges.items()}
        labelled = int((self.user_labels != -1).sum().item()) if self.user_labels is not None else 0
        return {
            "num_nodes": dict(self.num_nodes),
            "edge_counts": edge_counts,
            "labelled_users": labelled,
            "label_proxy_source": self.label_proxy_source,
            "txn_window_days": self.txn_window_days,
            "is_trainable": self.is_trainable,
        }


# ---------------------------------------------------------------------- #
# Internal helpers
# ---------------------------------------------------------------------- #
def _idx(d: dict[Any, int], key: Any) -> int:
    """Stable id-to-index allocator (insertion order)."""
    if key not in d:
        d[key] = len(d)
    return d[key]


def _to_csr(rows: list[int], cols: list[int], vals: list[float],
            n_rows: int, n_cols: int) -> csr_matrix:
    """Build a (n_rows × n_cols) CSR matrix.  Empty edges -> empty matrix."""
    if not rows:
        return csr_matrix((n_rows, n_cols), dtype=np.float32)
    return csr_matrix(
        (np.asarray(vals, dtype=np.float32),
         (np.asarray(rows, dtype=np.int64), np.asarray(cols, dtype=np.int64))),
        shape=(n_rows, n_cols),
    )


# ---------------------------------------------------------------------- #
# Builder
# ---------------------------------------------------------------------- #
async def build_graph(days: int = 90) -> GraphData:
    """Read the transactions table and produce a ``GraphData`` snapshot.

    Label-source priority (highest fidelity first):

    1. ``fraud_confirmed`` (Phase 8 analyst-confirmed feedback) when at
       least ``min_confirmed_fraud_users`` distinct users carry a TRUE
       row.  Defaults to 3 — small enough that the smallest realistic
       review queue can flip the trainer onto real labels.
    2. ``is_fraud`` — analyst-set fraud column.  Used when at least one
       row has it populated.
    3. ``anomaly_flag`` — Phase 1 heuristic.  Honest fallback only.
    """
    days = max(1, int(days))
    pool = get_pool()  # raises if uninitialised — caller decides what to do
    min_confirmed_fraud_users = 3

    async with pool.acquire() as conn:
        has_confirmed_col = bool(await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                  FROM information_schema.columns
                 WHERE table_name = 'transactions'
                   AND column_name = 'fraud_confirmed'
            )
            """
        ))
        confirmed_users = 0
        if has_confirmed_col:
            confirmed_users = int(await conn.fetchval(
                """
                SELECT COUNT(DISTINCT user_id)
                  FROM transactions
                 WHERE fraud_confirmed = TRUE
                """
            ) or 0)

        has_real_fraud = await conn.fetchval(
            "SELECT COUNT(*) FROM transactions WHERE is_fraud = TRUE"
        )

        if has_confirmed_col and confirmed_users >= min_confirmed_fraud_users:
            label_source = "fraud_confirmed"
        elif (has_real_fraud or 0) > 0:
            label_source = "is_fraud"
        else:
            label_source = "anomaly_flag"

        logger.info(
            "phase_10.graph_label_source chosen=%s confirmed_users=%d is_fraud_rows=%d",
            label_source, confirmed_users, int(has_real_fraud or 0),
        )

        # Pull the working window
        rows = await conn.fetch(
            f"""
            SELECT user_id, merchant, category, location, bank_name,
                   device_id, ip_address, card_token,
                   {label_source} AS label_proxy
            FROM transactions
            WHERE transaction_date >= CURRENT_DATE - ($1::int) * INTERVAL '1 day'
            """,
            days,
        )

    # Allocate indices
    user_idx: dict[Any, int] = {}
    merchant_idx: dict[Any, int] = {}
    category_idx: dict[Any, int] = {}
    location_idx: dict[Any, int] = {}
    bank_idx: dict[Any, int] = {}
    device_idx: dict[Any, int] = {}
    ip_idx: dict[Any, int] = {}
    card_idx: dict[Any, int] = {}

    edge_um: dict[tuple[int, int], int] = {}
    edge_uc: dict[tuple[int, int], int] = {}
    edge_ul: dict[tuple[int, int], int] = {}
    edge_ub: dict[tuple[int, int], int] = {}
    edge_ud: dict[tuple[int, int], int] = {}
    edge_ui: dict[tuple[int, int], int] = {}
    edge_ucard: dict[tuple[int, int], int] = {}

    user_label_count: dict[int, int] = {}      # uidx -> #flagged-rows
    user_total_count: dict[int, int] = {}      # uidx -> #total-rows

    def _bump(d: dict[tuple[int, int], int], k: tuple[int, int]) -> None:
        d[k] = d.get(k, 0) + 1

    for r in rows:
        if r["user_id"] is None:
            continue
        u = _idx(user_idx, int(r["user_id"]))
        user_total_count[u] = user_total_count.get(u, 0) + 1
        if r["label_proxy"]:
            user_label_count[u] = user_label_count.get(u, 0) + 1

        if r["merchant"]:
            m = _idx(merchant_idx, str(r["merchant"]))
            _bump(edge_um, (u, m))
        if r["category"]:
            c = _idx(category_idx, str(r["category"]))
            _bump(edge_uc, (u, c))
        if r["location"]:
            l = _idx(location_idx, str(r["location"]))
            _bump(edge_ul, (u, l))
        if r["bank_name"]:
            b = _idx(bank_idx, str(r["bank_name"]))
            _bump(edge_ub, (u, b))
        if r["device_id"]:
            d = _idx(device_idx, str(r["device_id"]))
            _bump(edge_ud, (u, d))
        if r["ip_address"]:
            ip = _idx(ip_idx, str(r["ip_address"]))
            _bump(edge_ui, (u, ip))
        if r["card_token"]:
            ct = _idx(card_idx, str(r["card_token"]))
            _bump(edge_ucard, (u, ct))

    num_nodes = {
        "user": len(user_idx),
        "merchant": len(merchant_idx),
        "category": len(category_idx),
        "location": len(location_idx),
        "bank": len(bank_idx),
        "device": len(device_idx),
        "ip": len(ip_idx),
        "card": len(card_idx),
    }

    def _build(edge_dict: dict[tuple[int, int], int],
               n_src: int, n_dst: int) -> csr_matrix:
        rs, cs, vs = [], [], []
        for (a, b), w in edge_dict.items():
            rs.append(a); cs.append(b); vs.append(float(w))
        return _to_csr(rs, cs, vs, n_src, n_dst)

    edges: dict[EdgeKey, csr_matrix] = {
        EDGE_USER_MERCHANT: _build(edge_um, num_nodes["user"], num_nodes["merchant"]),
        EDGE_USER_CATEGORY: _build(edge_uc, num_nodes["user"], num_nodes["category"]),
        EDGE_USER_LOCATION: _build(edge_ul, num_nodes["user"], num_nodes["location"]),
        EDGE_USER_BANK:     _build(edge_ub, num_nodes["user"], num_nodes["bank"]),
    }
    # Optional layers — only include when there's at least one edge.
    # This keeps the model graph small and avoids zero-feature nodes.
    if edge_ud:
        edges[EDGE_USER_DEVICE] = _build(edge_ud, num_nodes["user"], num_nodes["device"])
    if edge_ui:
        edges[EDGE_USER_IP]     = _build(edge_ui, num_nodes["user"], num_nodes["ip"])
    if edge_ucard:
        edges[EDGE_USER_CARD]   = _build(edge_ucard, num_nodes["user"], num_nodes["card"])

    # Build user labels: 1 if anomaly_rate > 0.05, else 0; -1 if ambiguous
    # (all-or-nothing).  This intentional smoothing over per-row labels
    # gives us *user-level* supervised signal — which is what the GNN
    # head predicts.
    if num_nodes["user"] > 0:
        labels = torch.full((num_nodes["user"],), -1, dtype=torch.long)
        for u, total in user_total_count.items():
            if total < 5:
                continue  # not enough activity to label confidently
            rate = user_label_count.get(u, 0) / total
            if rate >= 0.05:
                labels[u] = 1
            elif rate <= 0.005:
                labels[u] = 0
        train_mask = labels != -1
    else:
        labels = torch.zeros(0, dtype=torch.long)
        train_mask = torch.zeros(0, dtype=torch.bool)

    g = GraphData(
        num_nodes=num_nodes,
        node_id_maps={
            "user": user_idx,
            "merchant": merchant_idx,
            "category": category_idx,
            "location": location_idx,
            "bank": bank_idx,
            "device": device_idx,
            "ip": ip_idx,
            "card": card_idx,
        },
        edges=edges,
        user_labels=labels,
        train_mask=train_mask,
        label_proxy_source=label_source,
        txn_window_days=days,
    )

    logger.info(
        "phase_10.graph_built users=%d merchants=%d edges=%s labelled=%d source=%s",
        num_nodes["user"], num_nodes["merchant"],
        {k: m.nnz for k, m in edges.items()},
        int((labels != -1).sum().item()) if labels.numel() > 0 else 0,
        label_source,
    )
    return g
