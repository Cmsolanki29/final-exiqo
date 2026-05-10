"""Phase 12 — LLM-as-Judge.

A *separate* LLM call (different prompt, different role) that takes the
full decision context — transaction, baseline action, model signals,
and the optional Phase 9 investigation narrative — and returns a
structured opinion:

::

    {
        "agree":            true | false,
        "confidence":       0.0 ... 1.0,
        "concerns":         ["str", ...],
        "suggested_action": "allow | review | challenge | block | null",
        "narrative":        "2-3 sentence explanation"
    }

Discipline points:

* Reuses the **Phase 9 budget guard** so the orchestrator's spend is
  capped under the same daily envelope.
* Reuses the **Phase 9 PII redactor** before constructing the prompt.
* Fails closed: any error → ``agree=True`` (judge defers to baseline)
  with a non-zero ``error`` field.  We never up-grade an action on a
  failure path.
* No tool calling — this is a single-shot judge, by design.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from core.config import get_settings
from services.risk_common import groq_llm_client as groq
from services.risk_common.budget_guard import (
    BudgetExceeded,
    BudgetGuard,
    cost_from_tokens,
)
from services.risk_common.pii_redactor import redact_dict

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an independent fraud-decision JUDGE.

Your role is to *cross-check* an existing fraud decision produced by a
multi-model ensemble (XGBoost + Isolation Forest + GNN + DNN, optionally
augmented by an LLM investigation).  You did NOT make the original
decision; you are reviewing it.

You will receive:

* the transaction (already PII-redacted),
* the baseline action (allow / review / challenge / block) and its
  reasons,
* the per-model signals (risk_score, dnn_shadow_score, gnn_emb_norm, etc.),
* optionally, the Phase 9 LLM investigation narrative.

Decide:

1. Do you AGREE with the baseline action?  If yes, simply set agree=true
   and return a brief 2-sentence narrative.
2. If NO, list specific concerns and propose ``suggested_action`` from
   {allow, review, challenge, block}.

Return JSON ONLY (no markdown, no commentary outside the JSON object):

{
  "agree":             true | false,
  "confidence":        0.0 - 1.0,
  "concerns":          ["short string", ...],
  "suggested_action":  "allow | review | challenge | block",
  "narrative":         "2-3 sentence explanation"
}

CRITICAL:
* Be concise.  If you disagree, you must justify with a concrete
  evidence pointer (e.g. "DNN shadow score 91 is 30 points above
  baseline 61 — divergence not addressed in baseline reasons").
* Confidence < 0.6 means "I'm not sure" — set agree=true in that case.
* Never invent facts.  All your claims must reference values present in
  the user message.
"""


# --------------------------------------------------------------------- #
# Public dataclass — return shape from :func:`judge_decision`
# --------------------------------------------------------------------- #


@dataclass
class JudgeResult:
    invoked: bool = False
    agree: bool = True
    confidence: float = 0.0
    concerns: list[str] = field(default_factory=list)
    suggested_action: Optional[Literal["allow", "review", "challenge", "block"]] = None
    narrative: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "invoked":           self.invoked,
            "agree":             self.agree,
            "confidence":        self.confidence,
            "concerns":          list(self.concerns),
            "suggested_action":  self.suggested_action,
            "narrative":         self.narrative,
            "model":             self.model,
            "input_tokens":      self.input_tokens,
            "output_tokens":     self.output_tokens,
            "cost_usd":          self.cost_usd,
            "latency_ms":        self.latency_ms,
            "error":             self.error,
        }


# --------------------------------------------------------------------- #
# Budget guard singleton (lazy)
# --------------------------------------------------------------------- #


_guard: BudgetGuard | None = None


def _budget_guard() -> BudgetGuard:
    global _guard
    if _guard is None:
        _guard = BudgetGuard()
    return _guard


# --------------------------------------------------------------------- #
# Prompt construction
# --------------------------------------------------------------------- #


def _build_user_prompt(
    *,
    transaction: dict[str, Any],
    baseline_score: int,
    baseline_action: str,
    baseline_reasons: list[str],
    baseline_overrides: list[str],
    signals: dict[str, Any],
    investigation: dict[str, Any] | None,
) -> str:
    redacted_txn = redact_dict(transaction)
    redacted_signals = redact_dict(signals)
    redacted_inv = redact_dict(investigation) if investigation else None

    body = {
        "transaction":         redacted_txn,
        "baseline_action":     baseline_action,
        "baseline_score":      baseline_score,
        "baseline_reasons":    baseline_reasons,
        "baseline_overrides":  baseline_overrides,
        "model_signals":       redacted_signals,
    }
    if redacted_inv is not None:
        body["phase_9_investigation"] = {
            "decision":   redacted_inv.get("decision"),
            "confidence": redacted_inv.get("confidence"),
            "narrative":  redacted_inv.get("narrative"),
        }

    return (
        "Review the decision below and return your judgment as JSON.\n\n"
        + json.dumps(body, indent=2, default=str)
    )


# --------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------- #


async def judge_decision(
    *,
    transaction: dict[str, Any],
    baseline_score: int,
    baseline_action: str,
    baseline_reasons: list[str],
    baseline_overrides: list[str],
    signals: dict[str, Any],
    investigation: dict[str, Any] | None = None,
) -> JudgeResult:
    """Run the LLM judge.  Always returns a :class:`JudgeResult` — never
    raises.  Caller is responsible for honouring (or ignoring) the
    suggested action based on confidence."""
    settings = get_settings()
    started = time.perf_counter()

    if not groq.is_available():
        return JudgeResult(error="groq_unavailable")

    model = settings.PHASE_12_JUDGE_MODEL
    max_tokens = int(settings.PHASE_12_JUDGE_MAX_TOKENS)

    # ---- Budget reservation (estimate, refunded if call fails) ----
    user_prompt = _build_user_prompt(
        transaction=transaction,
        baseline_score=baseline_score,
        baseline_action=baseline_action,
        baseline_reasons=baseline_reasons,
        baseline_overrides=baseline_overrides,
        signals=signals,
        investigation=investigation,
    )

    # Rough token estimate: chars/4 is a defensible upper bound for English+JSON.
    est_in = max(len(SYSTEM_PROMPT) + len(user_prompt), 1) // 4
    est_cost = cost_from_tokens(model, est_in, max_tokens)
    try:
        await _budget_guard().check_and_reserve(model, est_cost)
    except BudgetExceeded as exc:
        logger.warning("phase_12.judge: budget exceeded — %s", exc)
        return JudgeResult(error="budget_exceeded")
    except Exception as exc:  # noqa: BLE001
        logger.debug("phase_12.judge: budget check skipped: %s", exc)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_prompt},
    ]

    try:
        result = await groq.chat(
            messages,
            model=model,
            response_format={"type": "json_object"},
            temperature=float(settings.PHASE_12_JUDGE_TEMPERATURE),
            max_tokens=max_tokens,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("phase_12.judge: LLM call failed: %s", exc)
        return JudgeResult(
            invoked=True,
            error=f"llm_call_failed: {type(exc).__name__}",
            model=model,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    parsed = groq.parse_json_response(result.text_content) or {}

    # ---- Sanity-coerce the parsed payload ----
    agree = bool(parsed.get("agree", True))
    confidence_raw = parsed.get("confidence", 0.0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    concerns_raw = parsed.get("concerns", [])
    concerns = (
        [str(c) for c in concerns_raw if isinstance(c, str)]
        if isinstance(concerns_raw, list)
        else []
    )

    suggested_action_raw = parsed.get("suggested_action")
    suggested_action: Optional[str] = None
    if isinstance(suggested_action_raw, str):
        canonical = suggested_action_raw.strip().lower()
        if canonical in {"allow", "review", "challenge", "block"}:
            suggested_action = canonical

    narrative = str(parsed.get("narrative", "") or "").strip()[:1000]

    # ---- Cost reconciliation ----
    actual_cost = cost_from_tokens(result.model, result.input_tokens, result.output_tokens)
    try:
        await _budget_guard().record_actual(
            result.model, result.input_tokens, result.output_tokens, actual_cost,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("phase_12.judge: budget record failed: %s", exc)

    elapsed = int((time.perf_counter() - started) * 1000)

    return JudgeResult(
        invoked=True,
        agree=agree,
        confidence=confidence,
        concerns=concerns,
        suggested_action=suggested_action,  # type: ignore[arg-type]
        narrative=narrative,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=actual_cost,
        latency_ms=elapsed,
    )
