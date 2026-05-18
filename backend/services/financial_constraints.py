"""Shared monthly cash picture for festival / purchase affordability checks."""

from __future__ import annotations

from typing import Any


def monthly_surplus_snapshot(conn, user_id: int) -> dict[str, Any]:
    from routes.emi_detector import _build_emi_detection

    report = _build_emi_detection(conn, user_id)
    income = float(report.get("monthly_income") or 0)
    emi = float(report.get("total_emi_burden") or 0)
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(monthly_fixed_expenses, 0)::float FROM users WHERE id = %s;",
        (user_id,),
    )
    fixed = float((cur.fetchone() or [0])[0] or 0)
    cur.execute(
        """
        SELECT COALESCE(SUM(monthly_target), 0)::float
        FROM purchase_goals
        WHERE user_id = %s
          AND UPPER(COALESCE(status, '')) NOT IN ('CANCELLED', 'COMPLETED');
        """,
        (user_id,),
    )
    goals = float((cur.fetchone() or [0])[0] or 0)
    cur.close()
    available = round(income - emi - fixed - goals, 2)
    return {
        "monthly_income": round(income, 2),
        "active_emi_monthly": round(emi, 2),
        "fixed_expenses_monthly": round(fixed, 2),
        "purchase_goals_monthly": round(goals, 2),
        "available_monthly_surplus": available,
        "debt_to_income_pct": float(report.get("debt_to_income_ratio") or 0),
    }
