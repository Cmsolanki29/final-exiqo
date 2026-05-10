"""Phase 12 — Orchestrator admin / observability API.

Endpoints (mounted at /api/risk/orchestrator from main.py):

  GET  /health                       — feature flags + readiness (open)
  GET  /costs/today                  — unified LLM cost dashboard (admin) [audit-11]
  GET  /tiers/distribution           — tier histogram for last N days (admin)
  GET  /decisions/{transaction_id}   — most recent orchestration row (admin)
  POST /decide                       — fully orchestrated decision for a txn (admin)
  POST /judge/replay                 — re-run only the LLM judge against a stored decision (admin)
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

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
from services.risk_common.admin_auth import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/risk/orchestrator", tags=["phase-12-orchestrator"])

# audit-8: admin auth is JWT-OR-X-Admin-Token via the shared
# `require_admin` dependency.


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


@router.get("/costs/today")
async def costs_today(
    _admin: dict = Depends(require_admin),
) -> dict[str, Any]:
    """Aggregated LLM spend across the 2026-parity phases for today.

    Reads three sources:
      * ``risk_llm_budget_log`` (Phase 9 + 12 share this table for spend
        accounting via ``budget_guard``);
      * ``risk_investigations`` (Phase 9 row count);
      * ``orchestration_decisions`` (Phase 12 row count where the LLM
        judge actually ran).

    audit-11: this is the single endpoint the frontend Trust Center
    and ops monitoring are expected to call.  Falls back to a
    zero-spend response if the DB is unavailable, so the dashboard
    never breaks just because Postgres hiccuped.
    """
    s = get_settings()
    today = date.today()
    cap = float(s.PHASE_9_DAILY_BUDGET_USD)
    empty = {
        "date": today.isoformat(),
        "total_cost_usd": 0.0,
        "daily_cap_usd": cap,
        "remaining_usd": round(cap, 4),
        "by_model": [],
        "phase_9_investigations": 0,
        "phase_12_judge_calls": 0,
    }
    pool = get_pool()
    if pool is None:
        return {**empty, "note": "db_unavailable"}

    try:
        async with pool.acquire() as conn:
            budget_rows = await conn.fetch(
                "SELECT model, request_count, input_tokens, output_tokens, cost_usd "
                "FROM risk_llm_budget_log WHERE date = $1",
                today,
            )
            inv_count = await conn.fetchval(
                "SELECT COUNT(*) FROM risk_investigations "
                "WHERE started_at::date = $1",
                today,
            )
            judge_count = await conn.fetchval(
                "SELECT COUNT(*) FROM orchestration_decisions "
                "WHERE created_at::date = $1 AND judge_invoked = TRUE",
                today,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("costs_today: db query failed: %s", exc)
        return {**empty, "note": f"db_error: {exc.__class__.__name__}"}

    total_cost = sum(float(r["cost_usd"] or 0) for r in budget_rows)
    return {
        "date": today.isoformat(),
        "total_cost_usd": round(total_cost, 4),
        "daily_cap_usd": cap,
        "remaining_usd": round(max(cap - total_cost, 0.0), 4),
        "by_model": [
            {
                "model": r["model"],
                "requests": int(r["request_count"] or 0),
                "input_tokens": int(r["input_tokens"] or 0),
                "output_tokens": int(r["output_tokens"] or 0),
                "cost_usd": float(r["cost_usd"] or 0),
            }
            for r in budget_rows
        ],
        "phase_9_investigations": int(inv_count or 0),
        "phase_12_judge_calls": int(judge_count or 0),
    }


@router.get("/tiers/distribution")
async def tiers_distribution(
    period_days: int = Query(default=7, ge=1, le=90),
    _admin: dict = Depends(require_admin),
) -> dict[str, Any]:
    return await tier_distribution(period_days)


@router.get("/decisions/{transaction_id}")
async def get_decision(
    transaction_id: int,
    _admin: dict = Depends(require_admin),
) -> dict[str, Any]:
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
    _admin: dict = Depends(require_admin),
) -> dict[str, Any]:
    """Pure-logic preview of which tier a hypothetical score would land in.
    No DB writes, no LLM calls — useful for the UI when explaining policy."""
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
    _admin: dict = Depends(require_admin),
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
    _admin: dict = Depends(require_admin),
) -> dict[str, Any]:
    """Re-run *only* the LLM judge against a stored orchestration row.

    Useful for:
    * sanity-checking a borderline decision that wasn't originally judged,
    * comparing model outputs after a prompt change,
    * debugging the judge prompt without re-running the full pipeline.
    """
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
