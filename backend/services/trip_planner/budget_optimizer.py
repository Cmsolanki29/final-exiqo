"""
Trip Planner › Budget optimiser.

Pure compute — no external API. Takes the trip components priced from the
flight/hotel tools, layers food/transport/activities estimates, applies a
safety buffer, then compares total against the user's REAL savings and
monthly surplus to produce a GREEN / YELLOW / RED verdict.

The verdict thresholds are deliberate and tuned for the spec:
  • GREEN  — savings ≥ 120% of total trip cost (1.2× buffer)
  • YELLOW — savings ≥ 70% of total but below GREEN line
  • RED    — savings <  70% of total
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from .financial_context import get_user_financial_context


def budget_optimizer(
    user_id: int,
    *,
    flight_cost: float,
    hotel_cost_per_night: float,
    nights: int,
    travelers: int = 1,
    daily_food_budget: float = 800.0,
    local_transport: float = 3000.0,
    activities_budget: float = 5000.0,
    buffer_percentage: float = 15.0,
) -> dict[str, Any]:
    travelers = max(1, int(travelers))
    nights = max(1, int(nights))
    flight_cost = max(0.0, float(flight_cost))
    hotel_cost_per_night = max(0.0, float(hotel_cost_per_night))
    daily_food_budget = max(0.0, float(daily_food_budget))
    local_transport = max(0.0, float(local_transport))
    activities_budget = max(0.0, float(activities_budget))
    buffer_percentage = max(0.0, min(50.0, float(buffer_percentage)))

    flight_total = flight_cost * travelers
    hotel_total = hotel_cost_per_night * nights
    food_total = daily_food_budget * nights * travelers
    subtotal = flight_total + hotel_total + food_total + local_transport + activities_budget
    buffer = round(subtotal * (buffer_percentage / 100.0), 2)
    total = round(subtotal + buffer, 2)

    financials = get_user_financial_context(user_id)
    user_saving = float(financials.get("total_savings_inr") or 0.0)
    surplus = float(financials.get("monthly_surplus_inr") or 0.0)

    # ── Verdict ─────────────────────────────────────────────────────────────
    if total <= 0:
        verdict = "RED"
        analysis = "Could not price the trip — flight or hotel cost was zero."
    elif user_saving >= total * 1.2:
        verdict = "GREEN"
        analysis = (
            f"You can comfortably afford this trip. Total ₹{total:,.0f} "
            f"vs your savings ₹{user_saving:,.0f} — even after a 20% safety cushion."
        )
    elif user_saving >= total * 0.7:
        shortfall = max(0.0, total - user_saving)
        wait_months = math.ceil(shortfall / surplus) if surplus > 0 else None
        verdict = "YELLOW"
        analysis = (
            f"Borderline. Trip total ₹{total:,.0f}, you currently have ₹{user_saving:,.0f}. "
            f"Shortfall ≈ ₹{shortfall:,.0f}"
            + (f" — about {wait_months} month(s) at your current saving rate." if wait_months else ".")
        )
    else:
        shortfall = max(0.0, total - user_saving)
        wait_months = math.ceil(shortfall / surplus) if surplus > 0 else None
        verdict = "RED"
        analysis = (
            f"Trip total ₹{total:,.0f} is significantly above your savings ₹{user_saving:,.0f}. "
            "Suggest cheaper alternatives or a future month."
            + (f" At current saving rate, it would take ~{wait_months} months to fund." if wait_months else "")
        )

    months_to_save: int | None
    if user_saving >= total:
        months_to_save = 0
    elif surplus > 0:
        months_to_save = math.ceil((total - user_saving) / surplus)
    else:
        months_to_save = None

    return {
        "breakdown": {
            "flights_total_inr": round(flight_total, 2),
            "hotels_total_inr": round(hotel_total, 2),
            "food_total_inr": round(food_total, 2),
            "local_transport_inr": round(local_transport, 2),
            "activities_inr": round(activities_budget, 2),
            "buffer_inr": buffer,
            "buffer_pct": buffer_percentage,
            "total_inr": total,
        },
        "user_capacity": {
            "current_savings_inr": round(user_saving, 2),
            "monthly_surplus_inr": round(surplus, 2),
            "can_afford_now": user_saving >= total,
        },
        "verdict": verdict,
        "analysis": analysis,
        "months_to_save": months_to_save,
        "computed_at": datetime.utcnow().isoformat() + "Z",
        "currency": "INR",
    }


__all__ = ["budget_optimizer"]
