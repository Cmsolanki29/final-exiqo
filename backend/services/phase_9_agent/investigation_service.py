"""High-level orchestration: fetch transaction → run agent → persist result.

Used by:
    routes/investigations.py        (manual/admin trigger)
    workers/alert_consumer.py       (auto trigger on score >= threshold)

Always returns a dict.  Never raises out (callers expect graceful failure
with ``decision='inconclusive'``).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from core.config import get_settings
from core.db import get_pool
from services.phase_9_agent.agent import get_agent

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------- #
# Entry point
# ---------------------------------------------------------------------- #
async def investigate_transaction(
    transaction_id: int,
    user_id: int | None = None,
    *,
    triggered_by: str = "auto_high_risk",
) -> dict[str, Any]:
    """Run an investigation for a transaction and persist the result.

    Returns a dict containing the investigation payload plus an
    ``investigation_id`` if persistence succeeded.

    Feature-flag: returns immediately with ``skipped=True`` when
    ``PHASE_9_AGENT_ENABLED`` is False — no DB write, no LLM call.
    """
    if not settings.PHASE_9_AGENT_ENABLED:
        return {
            "skipped": True,
            "reason": "phase_9_disabled",
            "transaction_id": transaction_id,
        }

    # ---- Fetch transaction ---- #
    try:
        pool = get_pool()
    except RuntimeError as exc:
        return {
            "skipped": True,
            "reason": f"db_unavailable: {exc}",
            "transaction_id": transaction_id,
        }

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, user_id, amount, type, description, merchant, category,
                   subcategory, payment_method, location, transaction_date,
                   transaction_time, risk_score, risk_level, anomaly_flag,
                   anomaly_reason, ip_address, device_id, card_token, bank_name
            FROM transactions
            WHERE id = $1
            """,
            transaction_id,
        )
    if row is None:
        return {
            "skipped": True,
            "reason": "transaction_not_found",
            "transaction_id": transaction_id,
        }

    txn = {k: v for k, v in dict(row).items()}
    risk_score = int(txn.get("risk_score") or 0)
    txn_user_id = int(user_id if user_id is not None else (txn.get("user_id") or 0))

    # Stringify date/time so the JSON dump in the prompt is clean
    txn["transaction_date"] = str(txn["transaction_date"]) if txn["transaction_date"] else None
    txn["transaction_time"] = str(txn["transaction_time"]) if txn["transaction_time"] else None
    txn["amount"] = float(txn["amount"]) if txn["amount"] is not None else None

    # Pick model based on risk
    model = (
        settings.PHASE_9_HIGH_STAKES_MODEL
        if risk_score >= 85
        else settings.PHASE_9_DEFAULT_MODEL
    )

    # ---- Run agent ---- #
    agent = get_agent()
    result = await agent.investigate(
        transaction=txn,
        risk_score=risk_score,
        user_id=txn_user_id,
        triggered_by=triggered_by,
        model=model,
    )

    # ---- Persist ---- #
    investigation_id: str | None = None
    try:
        async with pool.acquire() as conn:
            inv_id = await conn.fetchval(
                """
                INSERT INTO risk_investigations (
                    transaction_id, user_id, triggered_by, agent_model,
                    tool_calls, tool_call_count,
                    decision, confidence, narrative, suggested_rules,
                    pii_redacted,
                    input_tokens, output_tokens, cost_usd,
                    latency_ms, rounds_used, completed_at, error
                ) VALUES (
                    $1, $2, $3, $4,
                    $5::jsonb, $6,
                    $7, $8, $9, $10::jsonb,
                    TRUE,
                    $11, $12, $13,
                    $14, $15, NOW(), $16
                )
                RETURNING id
                """,
                transaction_id,
                txn_user_id,
                triggered_by,
                result["model"],
                json.dumps(result.get("tool_calls", []), default=str),
                len(result.get("tool_calls", []) or []),
                result["decision"],
                float(result["confidence"]),
                result.get("narrative") or "",
                json.dumps(result.get("suggested_rules", []), default=str),
                int(result.get("input_tokens") or 0),
                int(result.get("output_tokens") or 0),
                float(result.get("cost_usd") or 0.0),
                int(result.get("latency_ms") or 0),
                int(result.get("rounds_used") or 0),
                result.get("error"),
            )
            investigation_id = str(inv_id) if inv_id else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("persist investigation failed for txn=%s: %s", transaction_id, exc)

    logger.info(
        "investigation_complete txn=%s decision=%s confidence=%.2f cost_usd=%.6f latency_ms=%s",
        transaction_id, result["decision"], result["confidence"],
        result.get("cost_usd") or 0.0, result.get("latency_ms") or 0,
    )

    out = {
        "investigation_id": investigation_id,
        "transaction_id": transaction_id,
        "user_id": txn_user_id,
        "triggered_by": triggered_by,
        **result,
    }
    # `recommended_action` alias for frontend & E2E tests; uppercased for consistency.
    if "recommended_action" not in out and "decision" in out:
        out["recommended_action"] = str(out["decision"]).upper()
    return out


# ---------------------------------------------------------------------- #
# Read helpers
# ---------------------------------------------------------------------- #
async def get_investigation(transaction_id: int) -> dict[str, Any] | None:
    """Return the most recent investigation for a transaction, or None."""
    try:
        pool = get_pool()
    except RuntimeError:
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, transaction_id, user_id, triggered_by, agent_model,
                   tool_calls, tool_call_count, decision, confidence,
                   narrative, suggested_rules, pii_redacted,
                   input_tokens, output_tokens, cost_usd,
                   latency_ms, rounds_used, started_at, completed_at, error
            FROM risk_investigations
            WHERE transaction_id = $1
            ORDER BY started_at DESC
            LIMIT 1
            """,
            transaction_id,
        )
    if row is None:
        return None
    out = dict(row)
    out["id"] = str(out["id"])
    out["confidence"] = float(out["confidence"])
    out["cost_usd"] = float(out["cost_usd"])
    out["started_at"] = out["started_at"].isoformat() if out["started_at"] else None
    out["completed_at"] = out["completed_at"].isoformat() if out["completed_at"] else None
    # Normalise `recommended_action` so frontend + E2E tests can use a stable field name.
    if "recommended_action" not in out and "decision" in out:
        out["recommended_action"] = str(out["decision"] or "inconclusive").upper()
    return out
