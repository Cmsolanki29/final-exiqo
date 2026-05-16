"""
Trip Planner › Future-savings projection.

Linear projection: today's savings + (monthly surplus × months ahead).
The agent uses this to give YELLOW-verdict users a concrete "wait until <date>"
recommendation. The assumption is explicit in the payload so the LLM never
presents projected money as guaranteed money.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any

from .financial_context import get_user_financial_context


def _add_months(start: date, months: int) -> date:
    months = max(0, int(months))
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    day = min(start.day, monthrange(year, month)[1])
    return date(year, month, day)


def project_future_savings(user_id: int, months_ahead: int) -> dict[str, Any]:
    months_ahead = max(0, min(60, int(months_ahead)))

    financials = get_user_financial_context(user_id)
    current_savings = float(financials.get("total_savings_inr") or 0.0)
    surplus = float(financials.get("monthly_surplus_inr") or 0.0)

    projected_total = round(current_savings + surplus * months_ahead, 2)
    projected_date = _add_months(date.today(), months_ahead).isoformat()

    return {
        "current_savings_inr": round(current_savings, 2),
        "monthly_surplus_inr": round(surplus, 2),
        "months_projected": months_ahead,
        "projected_total_inr": projected_total,
        "projected_date": projected_date,
        "assumption": "Linear projection at current saving rate. Real value may vary with "
                      "bonuses, festivals, or unplanned expenses.",
        "data_source": "smartspend_postgres_live",
    }


__all__ = ["project_future_savings"]
