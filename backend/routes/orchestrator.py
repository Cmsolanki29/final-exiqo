"""Phase 12 — Orchestrator admin / observability API.

Endpoints (mounted at /api/risk/orchestrator from main.py):

  GET  /health                       — feature flags + readiness (open)
  GET  /tiers/distribution           — tier histogram for last N days (admin)
  GET  /decisions/{transaction_id}   — most recent orchestration row (admin)
  POST /decide                       — fully orchestrated decision for a txn (admin)
  POST /judge/replay                 — re-run only the LLM judge against a stored decision (admin)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Body, Header, HTTPException, Query

from core.config import get_settings
from core.db import get_pool
from services.phase_12_orchestrator.orchestrator import (
    decide as orchestrator_decide,
    get_decision_for_txn,
    tier_distribution,
)
from services.phase_12_orchestrator.llm_judge import judge_decision
from services.phase_12_orchestrator.routing_policy import (
    RoutingPolicy,
    route,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/risk/orchestrator", tags=["phase-12-orchestrator"])


def _require_admin(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> None:
    expected = os.getenv("ADMIN_TOKEN", "dev-admin-secret")
    if x_admin_token != expected:
        raise HTTPException(
            status_code=403, detail="Invalid or missing X-Admin-Token header"
        )


@router.get("/health")
async def health() -> dict[str, Any]:
    s = get_settings()
    return {
        "phase": 12,
        "name": "multi_model_orchestrator",
        "enabled": s.PHASE_12_ORCHESTRATOR_ENABLED,
        "judge_enabled": s.PHASE_12_JUDGE_ENABLED,
        "auto_investigate": s.PHASE_12_AUTO_INVESTIGATE,
        "sync_investigation": s.PHASE_12_SYNC_INVESTIGATION,
        "thresholds": {
            "tier0_max": s.PHASE_12_TIER0_MAX,
            "tier1_max": s.PHASE_12_TIER1_MAX,
            "tier2_max": s.PHASE_12_TIER2_MAX,
            "tier3_max": s.PHASE_12_TIER3_MAX,
            "dnn_disagree_delta": s.PHASE_12_DNN_DISAGREE_DELTA,
            "judge_min_confidence": s.PHASE_12_JUDGE_MIN_CONFIDENCE,
        },
    }


@router.get("/tiers/distribution")
async def tiers_distribution(
    period_days: int = Query(default=7, ge=1, le=90),
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, Any]:
    _require_admin(x_admin_token)
    return await tier_distribution(period_days)


@router.get("/decisions/{transaction_id}")
async def get_decision(
    transaction_id: int,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, Any]:
    _require_admin(x_admin_token)
    record = await get_decision_for_txn(transaction_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No orchestration record for this transaction")
    return record


@router.get("/route/preview")
async def preview_route(
    risk_score: int = Query(..., ge=0, le=100),
    has_gnn: bool = Query(default=False),
    has_dnn_shadow: bool = Query(default=False),
    has_rule_override: bool = Query(default=False),
    dnn_shadow_score: Optional[float] = Query(default=None, ge=0, le=100),
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, Any]:
    """Pure-logic preview of which tier a hypothetical score would land in.
    No DB writes, no LLM calls — useful for the UI when explaining policy."""
    _require_admin(x_admin_token)
    s = get_settings()
    signals: dict[str, Any] = {}
    if has_gnn:
        signals["gnn_emb_dim"] = 64
    if has_dnn_shadow:
        signals["dnn_shadow_score"] = (
            dnn_shadow_score if dnn_shadow_score is not None else float(risk_score)
        )
    overrides = ["preview_override"] if has_rule_override else []
    decision = route(
        risk_score=risk_score,
        signals=signals,
        rule_overrides=overrides,
        policy=RoutingPolicy.from_settings(s),
    )
    return decision.to_dict()


@router.post("/decide")
async def post_decide(
    payload: dict[str, Any] = Body(...),
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, Any]:
    """Fully orchestrated decision for a transaction.

    Body shape::

        {
          "user_id": 123,
          "txn":      {... transaction dict ...},
          "user":     {... user dict (optional, defaults to {"id": user_id}) ...},
          "features": {... assembled features (optional) ...}
        }
    """
    _require_admin(x_admin_token)
    user_id = payload.get("user_id")
    txn = payload.get("txn") or {}
    user = payload.get("user") or {"id": user_id}
    features = payload.get("features")

    if not isinstance(user_id, int):
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="user_id (int) is required")

    outcome = await orchestrator_decide(
        user_id=user_id,
        txn=txn,
        user=user,
        features=features,
        triggered_by="admin_decide_endpoint",
    )
    return outcome.to_dict()


@router.post("/judge/replay")
async def post_judge_replay(
    transaction_id: int = Query(..., description="Existing orchestration row to re-judge"),
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, Any]:
    """Re-run *only* the LLM judge against a stored orchestration row.

    Useful for:
    * sanity-checking a borderline decision that wasn't originally judged,
    * comparing model outputs after a prompt change,
    * debugging the judge prompt without re-running the full pipeline.
    """
    _require_admin(x_admin_token)
    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="db_unavailable")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT od.*, t.amount, t.merchant, t.category, t.payment_method,
                   t.transaction_date, t.user_id AS txn_user_id, t.id AS txn_id
            FROM   orchestration_decisions od
            LEFT   JOIN transactions t ON t.id = od.transaction_id
            WHERE  od.transaction_id = $1
            ORDER  BY od.created_at DESC
            LIMIT  1
            """,
            transaction_id,
        )

    if row is None:
        raise HTTPException(
            status_code=404, detail="No orchestration record for this transaction"
        )

    txn = {
        "id":               row["txn_id"],
        "user_id":          row["txn_user_id"],
        "amount":           float(row["amount"]) if row["amount"] is not None else None,
        "merchant":         row["merchant"],
        "category":         row["category"],
        "payment_method":   row["payment_method"],
        "transaction_date": row["transaction_date"].isoformat() if row["transaction_date"] else None,
    }

    import json as _json
    baseline_reasons = (
        _json.loads(row["baseline_reasons"]) if row["baseline_reasons"] else []
    )
    baseline_overrides = (
        _json.loads(row["baseline_overrides"]) if row["baseline_overrides"] else []
    )

    result = await judge_decision(
        transaction=txn,
        baseline_score=int(row["baseline_score"]),
        baseline_action=row["baseline_action"],
        baseline_reasons=baseline_reasons,
        baseline_overrides=baseline_overrides,
        signals={},  # not stored at decision time; intentional
        investigation=None,
    )
    return result.to_dict()
