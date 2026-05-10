"""Heterogeneous GraphSAGE — pure PyTorch + scipy.sparse.

Why we re-implement instead of using PyG
----------------------------------------
PyG's wheels are fragile on Windows / Python 3.13 and break our
"checkout-and-run" guarantee for the rest of the app.  The math here is
identical to PyG's ``SAGEConv`` (mean aggregation, concat self+neigh,
linear, ReLU): we just multiply with a row-normalised CSR matrix.

Architecture
------------
``HeteroSAGEConv`` — one per ``(src_type, rel, dst_type)`` edge layer.
                      Aggregates *destination* features into the *source*
                      node by left-multiplying ``adj_norm @ X_dst``.

``HeteroGraphSAGE`` — a stack of ``num_layers`` rounds; at each round we
                      pool messages from all incoming edge types into
                      every node type, then update with a per-type MLP.

Output shape
------------
``forward(...)`` returns a dict mapping node-type → embedding tensor of
shape ``(num_nodes_of_that_type, embed_dim)``.  We only use the ``user``
slot downstream, but exposing the full dict makes Phase 12's cross-type
explainability trivial.

Optional supervised head
------------------------
``classify_users`` adds a 2-class linear head on top of user embeddings
for the supervised loss term during training.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from scipy.sparse import csr_matrix


# ---------------------------------------------------------------------- #
# Sparse utilities
# ---------------------------------------------------------------------- #
def csr_to_torch_sparse(m: csr_matrix) -> torch.Tensor:
    """Convert a scipy CSR to a torch.sparse_coo_tensor (row-normalised).

    Row-normalisation gives the SAGE *mean* aggregator — sum-divided-by-
    -degree — for free.  Rows with zero degree stay zero (no division by
    zero) which is what we want: those nodes have no neighbours to
    aggregate from.
    """
    coo = m.tocoo()
    if coo.nnz == 0:
        # Return a sparse all-zero tensor of the right shape.
        return torch.sparse_coo_tensor(
            indices=torch.zeros((2, 0), dtype=torch.long),
            values=torch.zeros((0,), dtype=torch.float32),
            size=coo.shape,
        ).coalesce()
    # Row-normalise
    row_sum = np.asarray(coo.sum(axis=1)).flatten()
    row_sum[row_sum == 0] = 1.0
    norm_vals = coo.data / row_sum[coo.row]
    indices = torch.tensor(np.vstack([coo.row, coo.col]), dtype=torch.long)
    values = torch.tensor(norm_vals, dtype=torch.float32)
    return torch.sparse_coo_tensor(indices, values, coo.shape).coalesce()


# ---------------------------------------------------------------------- #
# Single SAGE conv on one (src, rel, dst) edge
# ---------------------------------------------------------------------- #
class HeteroSAGEConv(nn.Module):
    """One SAGE-style aggregation step over a single relation.

    Equivalent to PyG's ``SAGEConv((-1, -1), out_dim, aggr='mean')`` but
    operating on a fixed sparse adjacency built upstream.
    """

    def __init__(self, in_src: int, in_dst: int, out_dim: int) -> None:
        super().__init__()
        self.lin_self = nn.Linear(in_src, out_dim, bias=True)
        self.lin_neigh = nn.Linear(in_dst, out_dim, bias=False)

    def forward(self, x_src: torch.Tensor, x_dst: torch.Tensor,
                adj_norm: torch.Tensor) -> torch.Tensor:
        # ``adj_norm`` is row-normalised (src x dst) sparse.
        # ``adj_norm @ x_dst`` gives the mean of neighbour features per source.
        neigh_msg = torch.sparse.mm(adj_norm, x_dst)
        return self.lin_self(x_src) + self.lin_neigh(neigh_msg)


# ---------------------------------------------------------------------- #
# Heterogeneous wrapper
# ---------------------------------------------------------------------- #
class HeteroGraphSAGE(nn.Module):
    """Multi-layer SAGE over a fixed set of edge types.

    Typical usage:
        model = HeteroGraphSAGE(
            node_types=["user","merchant","category","location","bank"],
            edge_types=[(s,r,d), ...],
            in_dim=64, hidden_dim=64, out_dim=64, num_layers=2,
        )
        x_dict = {nt: torch.randn(num_nodes[nt], 64) for nt in node_types}
        adj_dict = {(s,r,d): csr_to_torch_sparse(m) for (s,r,d), m in edges.items()}
        emb = model(x_dict, adj_dict)["user"]
    """

    def __init__(
        self,
        node_types: Iterable[str],
        edge_types: Iterable[tuple[str, str, str]],
        in_dim: int = 64,
        hidden_dim: int = 64,
        out_dim: int = 64,
        num_layers: int = 2,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.node_types = list(node_types)
        self.edge_types = list(edge_types)
        self.num_layers = max(1, int(num_layers))
        self.dropout = dropout

        # Per-layer dict of HeteroSAGEConv keyed by edge type
        self.layers: nn.ModuleList = nn.ModuleList()
        for layer in range(self.num_layers):
            in_d = in_dim if layer == 0 else hidden_dim
            out_d = out_dim if layer == self.num_layers - 1 else hidden_dim
            convs = nn.ModuleDict({
                self._edge_key(s, r, d): HeteroSAGEConv(in_d, in_d, out_d)
                for (s, r, d) in self.edge_types
            })
            self.layers.append(convs)

        # Per-node-type post-aggregation MLP (mixes signals from all relations)
        self.post: nn.ModuleDict = nn.ModuleDict({
            nt: nn.Sequential(
                nn.Linear(out_dim, out_dim),
                nn.ReLU(),
                nn.Dropout(self.dropout),
            )
            for nt in self.node_types
        })

        # Optional supervised head on user embeddings
        self.user_classifier = nn.Linear(out_dim, 2)

    @staticmethod
    def _edge_key(s: str, r: str, d: str) -> str:
        return f"{s}__{r}__{d}"

    def forward(
        self,
        x_dict: dict[str, torch.Tensor],
        adj_dict: dict[tuple[str, str, str], torch.Tensor],
    ) -> dict[str, torch.Tensor]:
        h: dict[str, torch.Tensor] = {nt: x for nt, x in x_dict.items()}

        for layer in range(self.num_layers):
            convs = self.layers[layer]
            new_h: dict[str, list[torch.Tensor]] = {nt: [] for nt in self.node_types}

            for (s, r, d) in self.edge_types:
                conv = convs[self._edge_key(s, r, d)]
                adj = adj_dict.get((s, r, d))
                if adj is None or adj._nnz() == 0:
                    # No edges of this type — pass src through self-transform
                    msg = conv.lin_self(h[s])
                else:
                    msg = conv(h[s], h[d], adj)
                new_h[s].append(msg)

            # Pool messages per source node type, fall back to self-transform
            # for nodes that have no incoming edges in this layer.
            updated: dict[str, torch.Tensor] = {}
            for nt in self.node_types:
                if new_h[nt]:
                    pooled = torch.stack(new_h[nt], dim=0).mean(dim=0)
                else:
                    pooled = h[nt]   # passthrough
                pooled = F.relu(pooled)
                pooled = self.post[nt](pooled)
                updated[nt] = pooled
            h = updated

        return h

    def classify_users(
        self,
        x_dict: dict[str, torch.Tensor],
        adj_dict: dict[tuple[str, str, str], torch.Tensor],
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Convenience: return ``(logits, user_embedding)``."""
        emb = self.forward(x_dict, adj_dict)
        logits = self.user_classifier(emb["user"])
        return logits, emb["user"]
