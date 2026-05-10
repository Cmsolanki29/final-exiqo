"""Phase 12 — the orchestrator service.

Wraps :class:`services.hybrid_scorer.HybridScorer` +
:class:`services.decision_engine.DecisionEngine` and adds:

* deterministic tier labelling (always),
* selective sync Phase-9 investigation (when the routing policy asks for it),
* LLM-as-Judge cross-check (when policy asks for it),
* persistence to ``orchestration_decisions`` for audit.

The orchestrator is **purely additive**: when
``PHASE_12_ORCHESTRATOR_ENABLED`` is False it returns a transparent
passthrough — the baseline action is returned unchanged and only the
tier label is recorded (best-effort).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from core.config import get_settings
from core.db import get_pool
from schemas.decision import Decision
from schemas.score import ScoreResult
from services.decision_engine import decision_engine
from services.hybrid_scorer import hybrid_scorer
from services.phase_12_orchestrator.llm_judge import JudgeResult, judge_decision
from services.phase_12_orchestrator.routing_policy import (
    RoutingDecision,
    RoutingPolicy,
    Tier,
    route,
    tier_to_human,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------- #
# Public dataclass returned to callers
# --------------------------------------------------------------------- #


@dataclass
class OrchestrationOutcome:
    """Final orchestration result.  Suitable for direct JSON return."""

    tier: Tier
    tier_human: str
    routing_reason: str

    baseline_score: int
    baseline_action: str
    baseline_reasons: list[str]
    baseline_overrides: list[str]

    final_action: str
    final_reasons: list[str]

    investigation: Optional[dict[str, Any]] = None
    judge: Optional[JudgeResult] = None

    signals: dict[str, Any] = field(default_factory=dict)
    total_latency_ms: int = 0
    error: Optional[str] = None
    record_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier":              self.tier.value,
            "tier_human":        self.tier_human,
            "routing_reason":    self.routing_reason,
            "baseline_score":    self.baseline_score,
            "baseline_action":   self.baseline_action,
            "baseline_reasons":  list(self.baseline_reasons),
            "baseline_overrides": list(self.baseline_overrides),
            "final_action":      self.final_action,
            "final_reasons":     list(self.final_reasons),
            "investigation":     self.investigation,
            "judge":             self.judge.to_dict() if self.judge else None,
            "signals":           dict(self.signals),
            "total_latency_ms":  self.total_latency_ms,
            "error":             self.error,
            "record_id":         self.record_id,
        }


# --------------------------------------------------------------------- #
# Action ladder used to enforce "judge can only escalate, not relax"
# --------------------------------------------------------------------- #


_ACTION_RANK = {"allow": 0, "review": 1, "challenge": 2, "block": 3}


def _is_escalation(from_action: str, to_action: str) -> bool:
    return _ACTION_RANK.get(to_action, -1) > _ACTION_RANK.get(from_action, -1)


# --------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------- #


async def _maybe_run_investigation(
    transaction_id: int | None,
    user_id: int | None,
    *,
    triggered_by: str,
) -> Optional[dict[str, Any]]:
    """Synchronously call the Phase 9 investigator if a transaction id
    is available.  Returns its result dict or ``None`` if the call
    cannot be made (no txn id, agent disabled, agent error)."""
    if transaction_id is None:
        return None
    try:
        from services.phase_9_agent.investigation_service import (
            investigate_transaction,
        )
        return await investigate_transaction(
            transaction_id=int(transaction_id),
            user_id=int(user_id) if user_id is not None else None,
            triggered_by=triggered_by,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("phase_12: sync investigation failed: %s", exc)
        return {"error": f"investigation_failed: {type(exc).__name__}"}


async def _persist(
    *,
    txn_id: int | None,
    user_id: int | None,
    routing: RoutingDecision,
    baseline_score: int,
    baseline: Decision,
    final_action: str,
    final_reasons: list[str],
    investigation: dict[str, Any] | None,
    judge: JudgeResult | None,
    total_latency_ms: int,
    error: str | None,
) -> Optional[str]:
    """Insert a row into ``orchestration_decisions``.  Returns the id
    or ``None`` on failure (we never let a write failure break the
    orchestration path)."""
    pool = get_pool()
    if pool is None:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO orchestration_decisions
                    (transaction_id, user_id, tier, routing_reason,
                     baseline_score, baseline_action,
                     baseline_reasons, baseline_overrides,
                     final_action, final_reasons,
                     investigation_id, investigation_decision,
                     judge_invoked, judge_agree, judge_confidence, judge_concerns,
                     judge_suggested_action, judge_narrative, judge_model,
                     judge_input_tokens, judge_output_tokens, judge_cost_usd,
                     total_latency_ms, error)
                VALUES
                    ($1, $2, $3, $4,
                     $5, $6,
                     $7::jsonb, $8::jsonb,
                     $9, $10::jsonb,
                     $11, $12,
                     $13, $14, $15, $16::jsonb,
                     $17, $18, $19,
                     $20, $21, $22,
                     $23, $24)
                RETURNING id
                """,
                txn_id,
                user_id,
                routing.tier.value,
                routing.reason,
                baseline_score,
                baseline.action,
                json.dumps(baseline.reasons or []),
                json.dumps(baseline.rule_overrides or []),
                final_action,
                json.dumps(final_reasons or []),
                _safe_uuid(investigation),
                (investigation or {}).get("decision"),
                bool(judge.invoked) if judge else False,
                bool(judge.agree) if judge else None,
                float(judge.confidence) if judge else None,
                json.dumps((judge.concerns if judge else []) or []),
                judge.suggested_action if judge else None,
                (judge.narrative if judge else "") or "",
                (judge.model if judge else "") or "",
                int(judge.input_tokens) if judge else 0,
                int(judge.output_tokens) if judge else 0,
                float(judge.cost_usd) if judge else 0.0,
                int(total_latency_ms),
                error,
            )
        return str(row["id"]) if row is not None else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("phase_12: persist failed: %s", exc)
        return None


def _safe_uuid(investigation: dict[str, Any] | None) -> Optional[str]:
    """Pluck the investigation row id (UUID) when present."""
    if not investigation:
        return None
    val = investigation.get("id") or investigation.get("investigation_id")
    return str(val) if val else None


# --------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------- #


async def decide(
    *,
    user_id: int,
    txn: dict[str, Any],
    user: dict[str, Any],
    features: dict[str, Any] | None = None,
    score_override: ScoreResult | None = None,
    triggered_by: str = "orchestrator_decide",
) -> OrchestrationOutcome:
    """Score, decide, optionally escalate, and persist.

    Parameters
    ----------
    user_id : int
        Domain user identifier.
    txn : dict
        Transaction dict.  ``txn["id"]`` is used as the txn id when
        present.
    user : dict
        At minimum ``{"id": <int>}``; ``is_premium`` and ``txn_count_1h``
        respected if present.
    features : dict | None
        Phase 2 assembled feature dict (passed through to the scorer +
        decision engine).
    score_override : ScoreResult | None
        For replay endpoints — skip the scoring step and use the
        provided ``ScoreResult``.  Production callers leave this None.
    triggered_by : str
        Free-text label persisted on Phase 9 investigation rows.

    Always returns an :class:`OrchestrationOutcome` — never raises.
    """
    started = time.perf_counter()
    settings = get_settings()
    policy = RoutingPolicy.from_settings(settings)

    # ---- 1. Baseline score (skip if replay) ---- #
    if score_override is not None:
        score_result = score_override
    else:
        try:
            score_result = await hybrid_scorer.score(user_id, txn, features)
        except Exception as exc:  # noqa: BLE001
            logger.warning("phase_12: scoring failed (%s) — cold-start fallback", exc)
            score_result = ScoreResult.cold_start(
                detector_version="phase_12_fallback", latency_ms=0,
            )

    # ---- 2. Baseline decision ---- #
    try:
        baseline = await decision_engine.decide(
            score=score_result, txn=txn, user=user, assembled_features=features,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("phase_12: decision_engine failed: %s", exc)
        baseline = Decision(
            action="review",
            score=int(score_result.risk_score),
            reasons=[f"decision_engine_failed:{type(exc).__name__}"],
            rule_overrides=[],
            challenge_type=None,
        )

    # ---- 3. Routing ---- #
    routing = route(
        risk_score=int(score_result.risk_score),
        signals=dict(score_result.signals or {}),
        rule_overrides=list(baseline.rule_overrides or []),
        policy=policy,
    )

    # When orchestrator master switch is OFF, we keep the routing label
    # for analytics but skip every escalation path.
    final_action = baseline.action
    final_reasons = list(baseline.reasons)
    investigation: Optional[dict[str, Any]] = None
    judge_result: Optional[JudgeResult] = None
    error: Optional[str] = None

    if policy.enabled:
        # ---- 4. Optional sync Phase 9 investigation ---- #
        if routing.invoke_investigation and policy.auto_investigate:
            investigation = await _maybe_run_investigation(
                transaction_id=(txn or {}).get("id"),
                user_id=user_id,
                triggered_by=triggered_by,
            )
            if investigation:
                inv_decision = investigation.get("decision")
                inv_conf = float(investigation.get("confidence") or 0.0)
                # Clear "fraud_confirmed" with high confidence → block.
                if inv_decision == "fraud_confirmed" and inv_conf >= 0.7:
                    if _is_escalation(final_action, "block"):
                        final_action = "block"
                        final_reasons.append(
                            f"phase_9 investigation: fraud_confirmed (conf={inv_conf:.2f})"
                        )

        # ---- 5. Optional LLM-as-Judge ---- #
        if routing.invoke_judge and policy.judge_enabled:
            judge_result = await judge_decision(
                transaction=txn,
                baseline_score=int(score_result.risk_score),
                baseline_action=baseline.action,
                baseline_reasons=baseline.reasons,
                baseline_overrides=baseline.rule_overrides,
                signals=dict(score_result.signals or {}),
                investigation=investigation,
            )

            if (
                judge_result.invoked
                and not judge_result.agree
                and judge_result.suggested_action
                and judge_result.confidence >= float(settings.PHASE_12_JUDGE_MIN_CONFIDENCE)
                and _is_escalation(final_action, judge_result.suggested_action)
            ):
                final_action = judge_result.suggested_action
                final_reasons.append(
                    f"llm_judge: escalated to {judge_result.suggested_action} "
                    f"(conf={judge_result.confidence:.2f}); "
                    f"concerns={judge_result.concerns[:3]}"
                )

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    # ---- 6. Persist (best-effort) ---- #
    record_id = await _persist(
        txn_id=(txn or {}).get("id"),
        user_id=user_id,
        routing=routing,
        baseline_score=int(score_result.risk_score),
        baseline=baseline,
        final_action=final_action,
        final_reasons=final_reasons,
        investigation=investigation,
        judge=judge_result,
        total_latency_ms=elapsed_ms,
        error=error,
    )

    return OrchestrationOutcome(
        tier=routing.tier,
        tier_human=tier_to_human(routing.tier),
        routing_reason=routing.reason,
        baseline_score=int(score_result.risk_score),
        baseline_action=baseline.action,
        baseline_reasons=list(baseline.reasons),
        baseline_overrides=list(baseline.rule_overrides),
        final_action=final_action,
        final_reasons=final_reasons,
        investigation=investigation,
        judge=judge_result,
        signals=dict(score_result.signals or {}),
        total_latency_ms=elapsed_ms,
        error=error,
        record_id=record_id,
    )


# --------------------------------------------------------------------- #
# Read-side helpers used by the routes module
# --------------------------------------------------------------------- #


async def get_decision_for_txn(transaction_id: int) -> Optional[dict[str, Any]]:
    pool = get_pool()
    if pool is None:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM orchestration_decisions
                 WHERE transaction_id = $1
                 ORDER BY created_at DESC
                 LIMIT 1
                """,
                transaction_id,
            )
        if row is None:
            return None
        out = dict(row)
        for k in ("id", "investigation_id"):
            if out.get(k) is not None:
                out[k] = str(out[k])
        if out.get("created_at") is not None:
            out["created_at"] = out["created_at"].isoformat()
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("phase_12: get_decision_for_txn failed: %s", exc)
        return None


async def tier_distribution(period_days: int) -> dict[str, Any]:
    """Aggregate tier counts for the last ``period_days``."""
    pool = get_pool()
    if pool is None:
        return {"period_days": period_days, "buckets": {}, "total": 0, "note": "db_unavailable"}
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT tier, COUNT(*) AS n
                  FROM orchestration_decisions
                 WHERE created_at >= NOW() - ($1 || ' days')::interval
                 GROUP BY tier
                 ORDER BY n DESC
                """,
                str(int(period_days)),
            )
        buckets = {r["tier"]: int(r["n"]) for r in rows}
        return {
            "period_days": period_days,
            "buckets": buckets,
            "total": sum(buckets.values()),
        }
    except Exception as exc:  # noqa: BLE001
        return {"period_days": period_days, "buckets": {}, "total": 0, "error": str(exc)}
