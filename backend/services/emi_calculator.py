"""Standard reducing-balance EMI math — amortization schedule and purchase-plan helpers."""

from __future__ import annotations

import math
from typing import Any


def calculate_emi(principal: float, annual_rate_pct: float, tenure_months: int) -> float:
    """
    EMI = P × r × (1+r)^n / ((1+r)^n − 1)
    r = annual_rate_pct / 12 / 100 (monthly rate as decimal).
    """
    p = max(0.0, float(principal))
    n = max(1, int(tenure_months))
    if p <= 0:
        return 0.0
    if annual_rate_pct <= 0:
        return round(p / n, 2)
    r = float(annual_rate_pct) / 12.0 / 100.0
    factor = (1.0 + r) ** n
    emi = p * r * factor / (factor - 1.0)
    return round(emi, 2)


def build_amortization_schedule(
    principal: float,
    annual_rate_pct: float,
    tenure_months: int,
) -> list[dict[str, Any]]:
    """Month-by-month schedule; balances rounded to 2 decimals per row."""
    p = max(0.0, float(principal))
    n = max(1, int(tenure_months))
    emi = calculate_emi(p, annual_rate_pct, n)
    r = float(annual_rate_pct) / 12.0 / 100.0 if annual_rate_pct > 0 else 0.0
    balance = p
    rows: list[dict[str, Any]] = []
    total_interest = 0.0
    for month in range(1, n + 1):
        interest = round(balance * r, 2) if r > 0 else 0.0
        principal_part = round(emi - interest, 2) if month < n else round(balance, 2)
        if month == n:
            principal_part = round(balance, 2)
            emi_row = round(principal_part + interest, 2)
        else:
            emi_row = emi
        balance = round(max(0.0, balance - principal_part), 2)
        total_interest += interest
        rows.append(
            {
                "month": month,
                "emi": emi_row,
                "principal": principal_part,
                "interest": interest,
                "balance": balance,
            }
        )
    return rows


def loan_summary(
    product_price: float,
    down_payment: float,
    annual_rate_pct: float,
    tenure_months: int,
) -> dict[str, Any]:
    price = max(0.0, float(product_price))
    down = max(0.0, min(float(down_payment), price))
    principal = round(price - down, 2)
    emi = calculate_emi(principal, annual_rate_pct, tenure_months)
    schedule = build_amortization_schedule(principal, annual_rate_pct, tenure_months)
    total_payable = round(sum(row["emi"] for row in schedule), 2)
    total_interest = round(total_payable - principal, 2)
    return {
        "product_price": round(price, 2),
        "down_payment": round(down, 2),
        "principal": principal,
        "annual_interest_rate_pct": round(float(annual_rate_pct), 4),
        "tenure_months": int(tenure_months),
        "emi_monthly": emi,
        "total_amount_payable": total_payable,
        "total_interest": total_interest,
        "amortization_schedule": schedule,
    }


def emi_vs_cash_from_loan(
    target_amount: float,
    annual_rate_pct: float = 12.0,
    tenure_months: int = 12,
    down_payment: float = 0.0,
) -> dict[str, Any]:
    """Purchase Planner JSON shape using real EMI math for the financed tenure."""
    price = max(0.0, float(target_amount))
    down = max(0.0, min(float(down_payment), price))
    principal = round(price - down, 2)
    emi_m = calculate_emi(principal, annual_rate_pct, tenure_months)
    sched = build_amortization_schedule(principal, annual_rate_pct, tenure_months)
    total_financed = round(sum(row["emi"] for row in sched), 2)
    interest = round(total_financed - principal, 2)
    cash_total = price
    return {
        "cash": {
            "total": round(cash_total, 2),
            "monthly": None,
            "interest": 0,
            "verdict": f"BEST — avoid ~₹{interest:,.0f} interest vs {tenure_months}m EMI at {annual_rate_pct}%",
        },
        "emi_plan": {
            "total": round(down + total_financed, 2),
            "monthly": emi_m,
            "interest": interest,
            "principal": principal,
            "down_payment": round(down, 2),
            "tenure_months": int(tenure_months),
            "annual_rate_pct": round(float(annual_rate_pct), 4),
            "verdict": f"₹{emi_m:,.0f}/mo for {tenure_months} months (incl. ~₹{interest:,.0f} interest)",
        },
        "emi_12": {
            "total": round(down + total_financed, 2) if tenure_months == 12 else None,
            "monthly": emi_m if tenure_months == 12 else calculate_emi(principal, annual_rate_pct, 12),
            "interest": interest if tenure_months == 12 else round(
                calculate_emi(principal, annual_rate_pct, 12) * 12 - principal, 2
            ),
            "verdict": f"{tenure_months}m plan at {annual_rate_pct}% p.a.",
        },
    }
