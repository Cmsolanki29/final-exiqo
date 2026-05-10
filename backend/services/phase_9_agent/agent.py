"""InvestigationAgent — orchestrates the LLM tool-use loop.

Pattern
-------
1. Build messages: system + user (with redacted transaction).
2. Call Groq with tool schemas.
3. If response contains tool_calls: execute each, append tool results,
   loop.
4. If response is a final assistant message: parse JSON, return.

Hard caps
---------
* ``settings.PHASE_9_MAX_TOOL_ROUNDS`` rounds total
* ``settings.PHASE_9_MAX_OUTPUT_TOKENS`` per LLM reply
* Whole investigation must finish under
  ``settings.PHASE_9_TIMEOUT_SEC`` (asyncio.wait_for)
* Every LLM call is gated by ``BudgetGuard.check_and_reserve``

Failure modes
-------------
On any error path — budget exceeded, LLM unavailable, JSON parse
failure on the final reply, timeout — the agent returns an
``inconclusive`` result with the failure reason in ``error``.
The system NEVER raises out to the caller; investigations must always
produce a row that can be persisted.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from core.config import get_settings
from services.phase_9_agent.tools import default_tools
from services.phase_9_agent.tools.base_tool import BaseTool
from services.risk_common import groq_llm_client
from services.risk_common.budget_guard import (
    BudgetExceeded,
    budget_guard,
    cost_from_tokens,
)
from services.risk_common.pii_redactor import redact_dict

logger = logging.getLogger(__name__)
settings = get_settings()

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
SYSTEM_PROMPT = (_PROMPTS_DIR / "system_prompt.txt").read_text(encoding="utf-8")
INVESTIGATION_TEMPLATE = (_PROMPTS_DIR / "investigation_template.txt").read_text(encoding="utf-8")


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def _truncate_for_tool_payload(s: str, limit: int = 6000) -> str:
    if len(s) <= limit:
        return s
    return s[:limit] + f"... [truncated {len(s) - limit} chars]"


# ---------------------------------------------------------------------- #
# Agent
# ---------------------------------------------------------------------- #
class InvestigationAgent:
    """Stateless agent — one ``investigate(...)`` call = one investigation."""

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        self.tools: list[BaseTool] = tools if tools is not None else default_tools()
        self._tools_by_name: dict[str, BaseTool] = {t.name: t for t in self.tools}
        self._tool_schemas: list[dict[str, Any]] = [
            t.get_function_schema() for t in self.tools
        ]

    # ------------------------------------------------------------------ #
    # Public entrypoint
    # ------------------------------------------------------------------ #
    async def investigate(
        self,
        transaction: dict[str, Any],
        risk_score: int,
        user_id: int,
        *,
        triggered_by: str = "auto_high_risk",
        model: str | None = None,
    ) -> dict[str, Any]:
        """Run a full investigation and return a structured result dict.

        Always returns; never raises.  The result keys are stable and
        consumed by ``investigation_service.investigate_transaction`` for
        persistence.
        """
        started = time.perf_counter()
        chosen_model = model or settings.PHASE_9_DEFAULT_MODEL
        temperature = 0.1 if risk_score >= 85 else 0.2

        # Phase-9 disabled flag
        if not settings.PHASE_9_AGENT_ENABLED:
            return self._inconclusive(
                "phase_9_disabled", started, model=chosen_model, rounds=0,
            )
        # LLM unavailable (no API key, SDK missing)
        if not groq_llm_client.is_available():
            return self._inconclusive(
                "llm_unavailable", started, model=chosen_model, rounds=0,
            )

        # PII-redact the transaction before sending to LLM
        redacted_txn = redact_dict(transaction)
        user_prompt = INVESTIGATION_TEMPLATE.format(
            risk_score=risk_score,
            triggered_by=triggered_by,
            transaction_json=json.dumps(redacted_txn, indent=2, default=str),
            user_id=user_id,
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        tool_calls_log: list[dict[str, Any]] = []
        total_input = 0
        total_output = 0
        rounds_used = 0

        try:
            return await asyncio.wait_for(
                self._run_loop(
                    messages=messages,
                    chosen_model=chosen_model,
                    temperature=temperature,
                    user_id=user_id,
                    tool_calls_log=tool_calls_log,
                    total_tokens_ref=[total_input, total_output],
                    rounds_ref=[rounds_used],
                    started=started,
                ),
                timeout=settings.PHASE_9_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            return self._inconclusive(
                "timeout", started,
                model=chosen_model,
                rounds=rounds_used,
                tool_calls=tool_calls_log,
                input_t=total_input, output_t=total_output,
            )

    # ------------------------------------------------------------------ #
    # Internal loop
    # ------------------------------------------------------------------ #
    async def _run_loop(
        self,
        *,
        messages: list[dict[str, Any]],
        chosen_model: str,
        temperature: float,
        user_id: int,
        tool_calls_log: list[dict[str, Any]],
        total_tokens_ref: list[int],
        rounds_ref: list[int],
        started: float,
    ) -> dict[str, Any]:
        max_rounds = max(1, int(settings.PHASE_9_MAX_TOOL_ROUNDS))
        max_tokens = max(256, int(settings.PHASE_9_MAX_OUTPUT_TOKENS))

        for round_num in range(max_rounds):
            rounds_ref[0] = round_num + 1

            # Budget guard — estimate next call's cost (conservative)
            estimated_cost = 0.005 if round_num == 0 else 0.003
            try:
                await budget_guard.check_and_reserve(chosen_model, estimated_cost)
            except BudgetExceeded:
                return self._inconclusive(
                    "daily_llm_budget_exceeded", started,
                    model=chosen_model, rounds=rounds_ref[0],
                    tool_calls=tool_calls_log,
                    input_t=total_tokens_ref[0], output_t=total_tokens_ref[1],
                )

            try:
                result = await groq_llm_client.chat(
                    messages=messages,
                    model=chosen_model,
                    tools=self._tool_schemas,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("agent: LLM call failed round=%d err=%s", round_num, exc)
                return self._inconclusive(
                    f"llm_call_failed: {exc}", started,
                    model=chosen_model, rounds=rounds_ref[0],
                    tool_calls=tool_calls_log,
                    input_t=total_tokens_ref[0], output_t=total_tokens_ref[1],
                )

            total_tokens_ref[0] += result.input_tokens
            total_tokens_ref[1] += result.output_tokens

            # Record actual spend
            actual_cost = cost_from_tokens(
                result.model, result.input_tokens, result.output_tokens
            )
            await budget_guard.record_actual(
                result.model, result.input_tokens, result.output_tokens, actual_cost
            )

            tool_calls_in_msg = result.tool_calls
            if tool_calls_in_msg:
                # Append the assistant message including tool_calls
                # (OpenAI / Groq need the assistant tool_calls echoed back)
                messages.append({
                    "role": "assistant",
                    "content": result.text_content or None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls_in_msg
                    ],
                })
                # Execute each tool call
                for tc in tool_calls_in_msg:
                    tool = self._tools_by_name.get(tc.function.name)
                    try:
                        raw_args = tc.function.arguments or "{}"
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except Exception:
                        args = {}
                    if not tool:
                        tool_payload = {"ok": False, "error": f"unknown_tool: {tc.function.name}"}
                    else:
                        try:
                            tool_result = await tool.execute(args)
                            tool_payload = redact_dict(tool_result.to_payload())
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("tool %s execution error: %s", tc.function.name, exc)
                            tool_payload = {"ok": False, "error": f"tool_exception: {exc}"}

                    serialised = json.dumps(tool_payload, default=str)
                    serialised = _truncate_for_tool_payload(serialised)

                    tool_calls_log.append({
                        "tool": tc.function.name,
                        "input": redact_dict(args),
                        "output_summary": serialised[:1500],
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "content": serialised,
                    })
                continue

            # No tool calls -> this is the final response
            text = result.text_content
            parsed = groq_llm_client.parse_json_response(text)
            if parsed is None:
                # audit-10: one-shot retry through chat_for_json which
                # enforces response_format={"type": "json_object"}.
                # Tools are dropped (Groq disallows JSON mode + tools in
                # the same call) so the model is forced to emit a clean
                # object instead of free-form prose.
                if round_num < max_rounds - 1:
                    retry_messages = list(messages)
                    retry_messages.append({"role": "assistant", "content": text})
                    retry_messages.append({
                        "role": "user",
                        "content": (
                            "Your previous response was not valid JSON.  "
                            "Return ONLY the JSON object now, with the keys "
                            "decision, confidence, narrative, key_evidence, "
                            "suggested_rules.  No markdown, no extra text."
                        ),
                    })
                    try:
                        retry_result = await groq_llm_client.chat_for_json(
                            messages=retry_messages,
                            model=chosen_model,
                            temperature=0.1,
                            max_tokens=max_tokens,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "agent: JSON-mode retry failed round=%d err=%s",
                            round_num, exc,
                        )
                        return self._inconclusive(
                            "json_parse_failed", started,
                            model=result.model, rounds=rounds_ref[0],
                            tool_calls=tool_calls_log,
                            input_t=total_tokens_ref[0], output_t=total_tokens_ref[1],
                        )
                    total_tokens_ref[0] += retry_result.input_tokens
                    total_tokens_ref[1] += retry_result.output_tokens
                    actual_cost = cost_from_tokens(
                        retry_result.model,
                        retry_result.input_tokens,
                        retry_result.output_tokens,
                    )
                    await budget_guard.record_actual(
                        retry_result.model,
                        retry_result.input_tokens,
                        retry_result.output_tokens,
                        actual_cost,
                    )
                    parsed = groq_llm_client.parse_json_response(
                        retry_result.text_content
                    )
                    if parsed is None:
                        return self._inconclusive(
                            "json_parse_failed", started,
                            model=retry_result.model, rounds=rounds_ref[0],
                            tool_calls=tool_calls_log,
                            input_t=total_tokens_ref[0], output_t=total_tokens_ref[1],
                        )
                    # Use the JSON-mode result for the rest of the
                    # logic below (decision/confidence parsing).
                    result = retry_result
                else:
                    return self._inconclusive(
                        "json_parse_failed", started,
                        model=result.model, rounds=rounds_ref[0],
                        tool_calls=tool_calls_log,
                        input_t=total_tokens_ref[0], output_t=total_tokens_ref[1],
                    )

            decision = str(parsed.get("decision", "inconclusive"))
            if decision not in ("fraud_confirmed", "legitimate", "inconclusive"):
                decision = "inconclusive"
            try:
                confidence = float(parsed.get("confidence", 0.0) or 0.0)
            except (TypeError, ValueError):
                confidence = 0.0
            confidence = max(0.0, min(confidence, 1.0))
            # Force "inconclusive" if confidence is low — matches our own rule
            if confidence < 0.6 and decision != "inconclusive":
                decision = "inconclusive"

            narrative = str(parsed.get("narrative") or "").strip()
            suggested_rules = parsed.get("suggested_rules") or []
            if not isinstance(suggested_rules, list):
                suggested_rules = []
            key_evidence = parsed.get("key_evidence") or []
            if not isinstance(key_evidence, list):
                key_evidence = []

            total_cost = cost_from_tokens(
                result.model, total_tokens_ref[0], total_tokens_ref[1]
            )
            return {
                "decision": decision,
                "confidence": confidence,
                "narrative": narrative,
                "key_evidence": key_evidence,
                "suggested_rules": suggested_rules,
                "tool_calls": tool_calls_log,
                "input_tokens": total_tokens_ref[0],
                "output_tokens": total_tokens_ref[1],
                "cost_usd": total_cost,
                "model": result.model,
                "rounds_used": rounds_ref[0],
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "error": None,
            }

        # Hit the round cap — return inconclusive
        return self._inconclusive(
            "max_rounds_exceeded", started,
            model=chosen_model, rounds=rounds_ref[0],
            tool_calls=tool_calls_log,
            input_t=total_tokens_ref[0], output_t=total_tokens_ref[1],
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _inconclusive(
        reason: str,
        started: float,
        *,
        model: str,
        rounds: int,
        tool_calls: list[dict[str, Any]] | None = None,
        input_t: int = 0,
        output_t: int = 0,
    ) -> dict[str, Any]:
        return {
            "decision": "inconclusive",
            "confidence": 0.0,
            "narrative": f"Investigation could not complete: {reason}.",
            "key_evidence": [],
            "suggested_rules": [],
            "tool_calls": tool_calls or [],
            "input_tokens": input_t,
            "output_tokens": output_t,
            "cost_usd": cost_from_tokens(model, input_t, output_t),
            "model": model,
            "rounds_used": rounds,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "error": reason,
        }


# Module-level lazy singleton
_singleton: InvestigationAgent | None = None


def get_agent() -> InvestigationAgent:
    global _singleton
    if _singleton is None:
        _singleton = InvestigationAgent()
    return _singleton
