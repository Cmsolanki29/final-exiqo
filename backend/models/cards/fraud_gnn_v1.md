# Model Card — `fraud_gnn` v1

> **Status:** Staging.  Embeddings are produced and persisted, but **not
> blended into the production risk score**.  The hybrid scorer surfaces
> the embedding in `signals.gnn_emb_*` so downstream consumers (Phase
> 11/12) can use it; the score itself is unchanged.

## What it is

A heterogeneous **GraphSAGE** model that produces a 64-dimensional
embedding per user.  Implemented in pure PyTorch + scipy.sparse — same
math as PyTorch Geometric's `SAGEConv` but without the Windows / wheel
fragility, so the branch builds green on every checkout.

## Intended use

* **Today:** topology-aware user representation.  Users that share
  merchants, categories, banks, locations (and devices/IPs/cards when
  available) end up close in the embedding space.
* **Tomorrow:** become a feature in Phase 3's hybrid scorer + Phase 11's
  multi-branch DNN.  The plumbing is wired (`HybridScorer.score()` reads
  embeddings via `services.phase_10_gnn.inference.get_user_embedding`),
  the blending coefficient is intentionally **`feature_only`** until the
  data scale justifies a measured weight.

## Training data (May 2026 snapshot)

| Item | Value |
| --- | --- |
| Transactions in 90-day window | 2 564 |
| Distinct users (= user nodes) | **4** |
| Distinct merchants | 133 |
| Distinct categories | 11 |
| Distinct locations | 2 |
| Distinct banks | 5 |
| Real `is_fraud=TRUE` labels | **0** |
| Proxy labels (`anomaly_flag=TRUE`) | 181 rows over 4 users |
| `device_id` / `ip_address` / `card_token` populated | **0** |

## Honest caveats

This is a **non-trivial CTO call to ship at this scale**:

1. **Four user nodes.**  The whole point of a GNN is multi-hop fraud-ring
   detection across many users.  At four users we cannot learn rings —
   there are none.  The embedding still encodes useful "what merchants
   does this user prefer / which banks / what locations" structure, but
   we will not claim a fraud-detection accuracy lift until the user
   count grows by ~250x.
2. **No `is_fraud` labels.**  The supervised loss term uses
   `anomaly_flag` as a proxy (Phase 1 detector flag).  The loss curve is
   real, but the supervised head is essentially predicting Phase 1's own
   anomaly classifier — circular at our scale.  The unsupervised
   contrastive term (user ↔ merchant edge prediction) carries the real
   signal.
3. **Bipartite-ish graph.**  With device/IP/card all NULL, the graph
   reduces to user ↔ merchant ↔ category ↔ location ↔ bank.  This is
   plenty for embedding learning, not enough for ring detection.
4. **No blending into the production score.**  We deliberately did NOT
   add a `gnn_weight` to the hybrid scorer.  Phase 11 will retrain the
   XGBoost / DNN model with the embedding *as a feature column*, at
   which point the model itself learns the weight.  Today's hooked-in
   feature is `feature_only` — visible in `signals` for inspection,
   zero impact on the decision.

## Architecture

```
Input  : x_dict       — {node_type: tensor(num_nodes, embed_dim)}
         adj_dict     — {(src, rel, dst): scipy CSR -> torch.sparse}

Stack  : 2 × HeteroSAGEConv (mean aggregator, residual self-transform)
         per-node-type post-MLP (Linear → ReLU → Dropout)

Output : embeddings dict; user slot is L2-normalised before persistence.
         supervised head: Linear(64 → 2) for proxy-label cross-entropy.

Loss   : L = (1 - w) * unsup_BPR + w * sup_CE       w = 0.30
         unsup_BPR  : margin loss on positive vs random user-merchant pairs.
         sup_CE     : 2-class CE on user labels with a 5%/0.5% anomaly-rate
                      smoothing cutoff (so noisy single-anomaly users get -1).
```

## Storage

* **Redis** (`gnn:user_emb:{user_id}`, TTL = `PHASE_10_EMBED_TTL_SEC`,
  default 24h) — fast read path.
* **Postgres** `gnn_user_embeddings` table — durable source of truth.
  Inference falls back to it when Redis is down or the key has expired.
* **Postgres** `gnn_training_runs` table — one row per training run with
  loss curve, hyperparams, edge counts and label provenance.

## Performance

* Training: end-to-end < 10s on a 4-user / 133-merchant graph on CPU.
* Inference: O(1) lookup; Redis hit ~1ms, DB fallback ~5-10ms.
* Embedding payload per user: 64 × 4 bytes ≈ 256 bytes.

## Feature flag & rollback

* **Off by default**: `PHASE_10_GNN_ENABLED=false` makes the entire
  subsystem a no-op.  No retraining triggers, no Redis reads, no DB
  writes from the hot path.
* `git revert <phase-10 commit>` is safe — the migration is forward-only
  but the two new tables are append-only and contain no PII.

## When to upgrade

Re-evaluate this model card when **any** of the following becomes true:

1. User count > 100 in the 90-day training window.
2. Real `is_fraud` labels > 50.
3. `device_id` / `ip_address` populated on > 10% of rows (then we get
   actual fraud-ring topology to learn).

At that point this card should be replaced with v2 carrying real
PR-AUC / ROC-AUC numbers from a held-out test set, plus a measured
blending weight in the hybrid scorer.
