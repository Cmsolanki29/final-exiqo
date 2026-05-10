"""Online lookup of a user's GraphSAGE embedding.

Two-tier read path:
    1. Redis (``gnn:user_emb:{user_id}``) — sub-millisecond hit.
    2. Postgres (``gnn_user_embeddings``) — durable fallback used when
       Redis is unavailable or has expired the key.

Returns ``None`` when the embedding doesn't exist *anywhere* — callers
must treat ``None`` as "GNN feature unavailable" and continue without it
(the hybrid scorer is already feature-flag-guarded for this).

Caching
-------
We deliberately do **not** add an in-process LRU here.  Embeddings are
small (64 floats) and Redis is fast; an extra layer would be premature
complexity for a one-call-per-score-request workload.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from core.db import get_pool
from core.redis import get_redis

logger = logging.getLogger(__name__)


async def get_user_embedding(user_id: int | str) -> list[float] | None:
    """Return the user's GNN embedding, or None if unknown.

    The function never raises — DB/Redis errors are downgraded to a
    ``None`` return so the calling scorer can keep working.
    """
    if user_id is None:
        return None

    # ---- Redis fast path ---- #
    redis = get_redis()
    if redis is not None:
        try:
            raw = await redis.get(f"gnn:user_emb:{user_id}")
            if raw:
                vec = json.loads(raw)
                if isinstance(vec, list) and vec:
                    return [float(x) for x in vec]
        except Exception as exc:  # noqa: BLE001
            logger.debug("phase_10.inference: redis read failed: %s", exc)

    # ---- Postgres durable fallback ---- #
    try:
        pool = get_pool()
    except RuntimeError:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT embedding FROM gnn_user_embeddings WHERE user_id = $1",
                int(user_id),
            )
        if row is None:
            return None
        vec = row["embedding"]
        if vec is None:
            return None
        return [float(x) for x in vec]
    except Exception as exc:  # noqa: BLE001
        logger.debug("phase_10.inference: db read failed: %s", exc)
        return None


async def get_status() -> dict[str, Any]:
    """Summary used by the admin /api/risk/gnn/status endpoint."""
    out: dict[str, Any] = {
        "phase": 10,
        "redis_available": get_redis() is not None,
        "embeddings": {"total": 0, "dim": None, "model_version": None,
                       "newest_at": None},
        "last_run": None,
    }
    try:
        pool = get_pool()
    except RuntimeError:
        out["db_available"] = False
        return out
    out["db_available"] = True

    try:
        async with pool.acquire() as conn:
            stats = await conn.fetchrow(
                """
                SELECT COUNT(*)        AS n,
                       MAX(updated_at) AS newest,
                       MAX(embed_dim)  AS dim,
                       MAX(model_version) AS version
                FROM gnn_user_embeddings
                """,
            )
            if stats:
                out["embeddings"] = {
                    "total": int(stats["n"] or 0),
                    "dim": int(stats["dim"]) if stats["dim"] is not None else None,
                    "model_version": stats["version"],
                    "newest_at": stats["newest"].isoformat() if stats["newest"] else None,
                }
            run = await conn.fetchrow(
                """
                SELECT id, model_version, num_users, num_merchants, label_source,
                       labelled_users, embed_dim, num_layers, epochs, lr,
                       final_loss, sup_loss, unsup_loss, train_acc,
                       embeddings_written, duration_sec, error,
                       started_at, completed_at
                FROM gnn_training_runs
                ORDER BY started_at DESC
                LIMIT 1
                """,
            )
            if run is not None:
                d = dict(run)
                d["id"] = str(d["id"])
                d["started_at"] = d["started_at"].isoformat() if d["started_at"] else None
                d["completed_at"] = d["completed_at"].isoformat() if d["completed_at"] else None
                if d.get("final_loss") is not None: d["final_loss"] = float(d["final_loss"])
                if d.get("sup_loss") is not None: d["sup_loss"] = float(d["sup_loss"])
                if d.get("unsup_loss") is not None: d["unsup_loss"] = float(d["unsup_loss"])
                if d.get("train_acc") is not None: d["train_acc"] = float(d["train_acc"])
                if d.get("duration_sec") is not None: d["duration_sec"] = float(d["duration_sec"])
                if d.get("lr") is not None: d["lr"] = float(d["lr"])
                out["last_run"] = d
    except Exception as exc:  # noqa: BLE001
        logger.debug("phase_10.inference.get_status failed: %s", exc)

    return out
