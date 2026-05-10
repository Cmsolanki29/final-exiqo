"""Daily LLM spend cap — fail-closed at the API call level.

Why this exists
---------------
We never want to wake up to a $50K Groq bill because of a stuck loop or
misconfigured model.  Before every LLM call, ``check_and_reserve``
compares today's accumulated spend (from ``risk_llm_budget_log``) against
``settings.PHASE_9_DAILY_BUDGET_USD``.  If the *estimated* cost of the
upcoming call would push us over the cap, ``BudgetExceeded`` is raised
and the agent falls back to ``inconclusive``.

Race-safety
-----------
Estimate-then-record is good enough for a single-process app and 1-3 RPS
investigation traffic.  If we ever run multiple agent processes, swap the
SELECT/INSERT pair below for an UPSERT-with-RETURNING that atomically
reserves the budget before the LLM call.

Pricing
-------
Groq Llama 3.3 70B (May 2026): $0.59 / 1M input,  $0.79 / 1M output.
Llama 3.1 70B (fallback):      $0.59 / 1M input,  $0.79 / 1M output.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

from core.config import get_settings
from core.db import get_pool

logger = logging.getLogger(__name__)


# Token pricing in USD per 1M tokens.  Update from Groq's pricing page.
GROQ_PRICING: dict[str, dict[str, float]] = {
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-70b-versatile": {"input": 0.59, "output": 0.79},
    # Conservative fallback if we ever hit a model not in this map.
    "_default": {"input": 1.00, "output": 2.00},
}


def cost_from_tokens(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return the USD cost of an LLM call given token counts."""
    rates = GROQ_PRICING.get(model) or GROQ_PRICING["_default"]
    return (
        input_tokens * rates["input"] + output_tokens * rates["output"]
    ) / 1_000_000.0


class BudgetExceeded(Exception):
    """Raised when an LLM call would push today's spend over the daily cap."""


class BudgetGuard:
    """Singleton-style budget guard.  Use the module-level ``budget_guard`` instance."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    @property
    def daily_cap_usd(self) -> float:
        return float(get_settings().PHASE_9_DAILY_BUDGET_USD)

    # ----------------------------------------------------------- #
    # Public API
    # ----------------------------------------------------------- #
    async def check_and_reserve(self, model: str, estimated_cost_usd: float) -> bool:
        """Verify today's spend + estimate <= cap.

        Returns True on success.  Raises ``BudgetExceeded`` (and logs a warning)
        when the cap would be exceeded.  This is a "soft reservation" — actual
        spend is logged via ``record_actual`` after the call returns.
        """
        try:
            pool = get_pool()
        except RuntimeError:
            # No DB pool (dev mode, Postgres down).  Allow the call but log
            # a warning so we don't silently lose budget tracking.
            logger.warning("budget_guard: DB pool unavailable, skipping cap check")
            return True

        today = date.today()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT cost_usd FROM risk_llm_budget_log WHERE date = $1 AND model = $2",
                today,
                model,
            )
        current = float(row["cost_usd"]) if row else 0.0

        if current + estimated_cost_usd > self.daily_cap_usd:
            logger.warning(
                "budget_exceeded model=%s today_spend=%.4f estimate=%.4f cap=%.2f",
                model,
                current,
                estimated_cost_usd,
                self.daily_cap_usd,
            )
            raise BudgetExceeded(
                f"Daily LLM budget exceeded: ${current:.4f} + "
                f"${estimated_cost_usd:.4f} > ${self.daily_cap_usd:.2f}"
            )
        return True

    async def record_actual(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        """Append the real spend after an LLM call completes."""
        try:
            pool = get_pool()
        except RuntimeError:
            logger.warning("budget_guard: DB pool unavailable, skipping spend record")
            return

        today = date.today()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO risk_llm_budget_log
                    (date, model, request_count, input_tokens, output_tokens, cost_usd, updated_at)
                VALUES ($1, $2, 1, $3, $4, $5, NOW())
                ON CONFLICT (date, model) DO UPDATE SET
                    request_count = risk_llm_budget_log.request_count + 1,
                    input_tokens  = risk_llm_budget_log.input_tokens  + EXCLUDED.input_tokens,
                    output_tokens = risk_llm_budget_log.output_tokens + EXCLUDED.output_tokens,
                    cost_usd      = risk_llm_budget_log.cost_usd      + EXCLUDED.cost_usd,
                    updated_at    = NOW()
                """,
                today,
                model,
                input_tokens,
                output_tokens,
                cost_usd,
            )

    async def today_spend(self) -> dict[str, Any]:
        """Return today's spend rolled up by model.  Useful for the admin endpoint."""
        try:
            pool = get_pool()
        except RuntimeError:
            return {"date": str(date.today()), "models": {}, "total_usd": 0.0,
                    "cap_usd": self.daily_cap_usd, "remaining_usd": self.daily_cap_usd,
                    "db_available": False}

        today = date.today()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT model, request_count, input_tokens, output_tokens, cost_usd
                FROM risk_llm_budget_log
                WHERE date = $1
                """,
                today,
            )
        per_model = {
            r["model"]: {
                "requests": r["request_count"],
                "input_tokens": r["input_tokens"],
                "output_tokens": r["output_tokens"],
                "cost_usd": float(r["cost_usd"]),
            }
            for r in rows
        }
        total = sum(m["cost_usd"] for m in per_model.values())
        cap = self.daily_cap_usd
        return {
            "date": str(today),
            "models": per_model,
            "total_usd": round(total, 6),
            "cap_usd": cap,
            "remaining_usd": round(max(0.0, cap - total), 6),
            "db_available": True,
        }


# Module-level singleton.
budget_guard = BudgetGuard()
