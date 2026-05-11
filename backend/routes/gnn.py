"""Phase 10 — GNN admin / inspection API surface.

Endpoints (mounted at /api/risk/gnn from main.py):

  POST /train                                — train + persist embeddings (admin)
  GET  /status                               — last-run + embedding inventory (admin)
  GET  /users/{user_id}/embedding            — read one user's embedding (admin)
  GET  /health                               — feature-flag + readiness (open)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.config import get_settings
from services.phase_10_gnn.inference import get_status, get_user_embedding
from services.phase_10_gnn.trainer import train_gnn
from services.risk_common.admin_auth import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/risk/gnn", tags=["phase-10-gnn"])


# audit-8: admin auth is JWT-OR-X-Admin-Token via the shared
# `require_admin` dependency.


@router.get("/health")
async def health() -> dict[str, Any]:
    """Public probe — feature flag + minimal config disclosure.

    ``enabled`` is the canonical key going forward; we keep
    ``feature_flag_enabled`` for one release for backward compat with
    older frontends.
    """
    s = get_settings()
    flag = bool(s.PHASE_10_GNN_ENABLED)
    return {
        "phase": 10,
        "enabled": flag,
        "feature_flag_enabled": flag,
        "embed_dim": s.PHASE_10_EMBED_DIM,
        "num_layers": s.PHASE_10_NUM_LAYERS,
        "training_days": s.PHASE_10_TRAINING_DAYS,
        "min_users_for_training": s.PHASE_10_MIN_USERS_FOR_TRAINING,
    }


@router.post("/train", dependencies=[Depends(require_admin)])
async def train(
    days: Optional[int] = Query(default=None, ge=1, le=365),
    epochs: Optional[int] = Query(default=None, ge=1, le=2000),
    lr: Optional[float] = Query(default=None, gt=0.0, lt=1.0),
) -> dict[str, Any]:
    """Trigger a training run.  Synchronous because at our data scale it
    finishes in a few seconds.  For larger graphs, swap this for a
    background task."""
    return await train_gnn(days=days, epochs=epochs, lr=lr)


@router.get("/status", dependencies=[Depends(require_admin)])
async def status() -> dict[str, Any]:
    """Embedding inventory + most recent training run."""
    return await get_status()


@router.get("/users/{user_id}/embedding", dependencies=[Depends(require_admin)])
async def get_embedding(user_id: int) -> dict[str, Any]:
    """Read a single user's embedding (Redis-first, DB fallback)."""
    vec = await get_user_embedding(user_id)
    if vec is None:
        raise HTTPException(status_code=404, detail=f"No embedding for user {user_id}")
    return {
        "user_id": user_id,
        "embedding": vec,
        "dim": len(vec),
    }
