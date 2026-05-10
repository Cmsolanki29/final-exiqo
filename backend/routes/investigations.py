"""Phase 9 — investigation API surface.

Endpoints (mounted at /api/risk/investigations from main.py):

  POST /{txn_id}/run                  — manually trigger an investigation (admin)
  GET  /{txn_id}                      — fetch the latest investigation row (admin)
  GET  /budget/today                  — today's LLM spend rollup       (admin)
  GET  /health                        — agent + LLM availability       (open)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from core.config import get_settings
from services.phase_9_agent.investigation_service import (
    get_investigation,
    investigate_transaction,
)
from services.risk_common import groq_llm_client
from services.risk_common.budget_guard import budget_guard

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/risk/investigations", tags=["phase-9-investigations"])


# ---------------------------------------------------------------------- #
# Auth — same simple header check used by /api/admin/*
# ---------------------------------------------------------------------- #
def _require_admin(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> None:
    expected = os.getenv("ADMIN_TOKEN", "dev-admin-secret")
    if x_admin_token != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Admin-Token header")


# ---------------------------------------------------------------------- #
# Endpoints
# ---------------------------------------------------------------------- #
@router.get("/health")
async def health() -> dict[str, Any]:
    """Public health/readiness probe.  Reveals nothing sensitive."""
    settings = get_settings()
    return {
        "phase": 9,
        "feature_flag_enabled": bool(settings.PHASE_9_AGENT_ENABLED),
        "llm_client_available": groq_llm_client.is_available(),
        "default_model": settings.PHASE_9_DEFAULT_MODEL,
        "high_stakes_model": settings.PHASE_9_HIGH_STAKES_MODEL,
        "auto_trigger_score": settings.PHASE_9_AUTO_TRIGGER_SCORE,
        "daily_budget_usd": settings.PHASE_9_DAILY_BUDGET_USD,
    }


@router.post("/{txn_id}/run", dependencies=[Depends(_require_admin)])
async def run_investigation(
    txn_id: int,
    user_id: Optional[int] = Query(default=None),
    triggered_by: str = Query(default="manual"),
) -> dict[str, Any]:
    """Trigger an investigation on demand.  Admin only."""
    if not get_settings().PHASE_9_AGENT_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Phase 9 agent disabled (set PHASE_9_AGENT_ENABLED=true)",
        )
    return await investigate_transaction(
        transaction_id=txn_id,
        user_id=user_id,
        triggered_by=triggered_by,
    )


@router.get("/{txn_id}", dependencies=[Depends(_require_admin)])
async def fetch_investigation(txn_id: int) -> dict[str, Any]:
    """Return the most recent investigation for a transaction."""
    inv = await get_investigation(txn_id)
    if inv is None:
        raise HTTPException(status_code=404, detail=f"No investigation for transaction {txn_id}")
    return inv


@router.get("/budget/today", dependencies=[Depends(_require_admin)])
async def today_budget() -> dict[str, Any]:
    """Today's LLM spend rollup, used by the admin UI to show the budget bar."""
    return await budget_guard.today_spend()
