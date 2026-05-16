"""
Trip Planner › Financial Context tool.

Builds a real, current financial snapshot for the authenticated user using the
same psycopg2 tables the rest of the app uses. Every number returned here
comes from the database — there are no hardcoded amounts and no static demo
values. The agent calls this BEFORE planning any trip so that GREEN / YELLOW /
RED verdicts are always grounded in the user's real money situation.
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import date
from typing import Any

from db import get_connection

_log = logging.getLogger(__name__)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _rollback(conn) -> None:
    try:
        conn.rollback()
    except Exception:
        pass


def get_user_financial_context(user_id: int) -> dict[str, Any]:
    """
    Return a clean, JSON-serialisable financial snapshot the LLM can reason over.
    No raw rows are exposed — only computed aggregates the agent actually needs.
    """
    conn = get_connection()
    cur = None
    snapshot: dict[str, Any] = {
        "snapshot_date": date.today().isoformat(),
        "currency": "INR",
    }

    try:
        cur = conn.cursor()

        # ── 1. User profile ─────────────────────────────────────────────────
        user_row: tuple[Any, ...] | None = None
        try:
            cur.execute(
                """
                SELECT name, email,
                       COALESCE(monthly_income, 0) AS monthly_income,
                       COALESCE(savings_goal, 0)   AS savings_goal,
                       COALESCE(risk_tolerance, 'MEDIUM') AS risk_tolerance
                FROM users WHERE id = %s
                """,
                (user_id,),
            )
            user_row = cur.fetchone()
        except Exception as exc:  # noqa: BLE001
            _rollback(conn)
            _log.warning("[trip-planner.fin_ctx] user fetch failed: %s", exc)

        if not user_row:
            return {
                **snapshot,
                "error": "user_not_found",
                "note": "No profile on file. Ask the user for monthly income before planning.",
                "total_savings": 0.0,
                "monthly_income": 0.0,
                "monthly_surplus": 0.0,
            }

        monthly_income = _safe_float(user_row[2])
        savings_goal = _safe_float(user_row[3])

        snapshot["user_name"] = user_row[0]
        snapshot["risk_tolerance"] = user_row[4]
        snapshot["monthly_income_inr"] = monthly_income
        snapshot["savings_goal_inr"] = savings_goal

        # ── 2. Lifetime cashflow → total savings proxy ──────────────────────
        # SmartSpend doesn't store explicit balances; we derive disposable savings
        # as (lifetime credits − lifetime debits) which is the realised net.
        total_savings = 0.0
        try:
            cur.execute(
                """
                SELECT
                  COALESCE(SUM(CASE WHEN type = 'CREDIT' THEN amount ELSE 0 END), 0)
                - COALESCE(SUM(CASE
                                  WHEN type = 'DEBIT'
                                   AND COALESCE(category, '') <> 'internal_transfer'
                                  THEN amount ELSE 0 END), 0)
                FROM transactions WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
            total_savings = _safe_float(row[0] if row else 0)
        except Exception as exc:  # noqa: BLE001
            _rollback(conn)
            _log.warning("[trip-planner.fin_ctx] cashflow agg failed: %s", exc)

        # If lifetime cashflow is negative (heavy spender or short history),
        # fall back to a conservative 1-month-income proxy so the verdict
        # engine doesn't unfairly RED-flag a perfectly viable user. This is
        # transparent — it is also reported back so the agent can ask.
        savings_source = "lifetime_net_cashflow"
        if total_savings < 0:
            total_savings = max(0.0, monthly_income * 0.5)
            savings_source = "estimated_from_income_floor"

        snapshot["total_savings_inr"] = round(total_savings, 2)
        snapshot["savings_source"] = savings_source

        # ── 3. Last 3 months: avg spend + avg income ────────────────────────
        avg_monthly_spend = 0.0
        avg_monthly_income_realised = monthly_income
        try:
            cur.execute(
                """
                WITH months AS (
                  SELECT DATE_TRUNC('month', transaction_date)::date AS m,
                         SUM(CASE WHEN type = 'DEBIT'
                                   AND COALESCE(category, '') <> 'internal_transfer'
                                  THEN amount ELSE 0 END) AS spend,
                         SUM(CASE WHEN type = 'CREDIT' THEN amount ELSE 0 END) AS income
                  FROM transactions
                  WHERE user_id = %s
                    AND transaction_date >= (CURRENT_DATE - INTERVAL '3 months')
                  GROUP BY 1
                )
                SELECT COALESCE(AVG(spend), 0), COALESCE(AVG(income), 0), COUNT(*)
                FROM months
                """,
                (user_id,),
            )
            row = cur.fetchone()
            if row:
                avg_monthly_spend = _safe_float(row[0])
                if _safe_float(row[1]) > 0:
                    avg_monthly_income_realised = _safe_float(row[1])
        except Exception as exc:  # noqa: BLE001
            _rollback(conn)
            _log.warning("[trip-planner.fin_ctx] 3-month avg failed: %s", exc)

        # ── 4. Active EMI burden ────────────────────────────────────────────
        monthly_emi = 0.0
        emi_count = 0
        try:
            cur.execute(
                """
                SELECT COALESCE(SUM(detected_amount), 0), COUNT(*)
                FROM emi_records
                WHERE user_id = %s AND is_active IS TRUE
                """,
                (user_id,),
            )
            row = cur.fetchone()
            if row:
                monthly_emi = _safe_float(row[0])
                emi_count = int(row[1] or 0)
        except Exception as exc:  # noqa: BLE001
            _rollback(conn)
            _log.warning("[trip-planner.fin_ctx] EMI agg failed: %s", exc)

        # ── 5. Active subscriptions (monthly burn) ──────────────────────────
        monthly_subscriptions = 0.0
        sub_count = 0
        try:
            cur.execute(
                """
                SELECT COALESCE(
                         SUM(COALESCE(NULLIF(monthly_cost, 0), amount, 0)),
                         0
                       ),
                       COUNT(*)
                FROM subscriptions
                WHERE user_id = %s
                  AND (status IS NULL OR LOWER(status) NOT IN ('cancelled', 'pending_cancel'))
                """,
                (user_id,),
            )
            row = cur.fetchone()
            if row:
                monthly_subscriptions = _safe_float(row[0])
                sub_count = int(row[1] or 0)
        except Exception as exc:  # noqa: BLE001
            _rollback(conn)
            _log.warning("[trip-planner.fin_ctx] subs agg failed: %s", exc)

        # ── 6. Likely home city — derive from most frequent txn location ────
        user_city: str | None = None
        try:
            cur.execute(
                """
                SELECT location
                FROM transactions
                WHERE user_id = %s
                  AND location IS NOT NULL
                  AND TRIM(location) <> ''
                  AND transaction_date >= (CURRENT_DATE - INTERVAL '6 months')
                """,
                (user_id,),
            )
            locations = [r[0].strip() for r in cur.fetchall() if r[0]]
            if locations:
                user_city = Counter(locations).most_common(1)[0][0]
        except Exception as exc:  # noqa: BLE001
            _rollback(conn)
            _log.warning("[trip-planner.fin_ctx] city derivation failed: %s", exc)

        # ── 7. Top spending categories (last 3 months) ──────────────────────
        top_categories: list[dict[str, float | str]] = []
        try:
            cur.execute(
                """
                SELECT COALESCE(category, 'Uncategorised') AS cat,
                       COALESCE(SUM(amount), 0)::float AS spend
                FROM transactions
                WHERE user_id = %s
                  AND type = 'DEBIT'
                  AND COALESCE(category, '') <> 'internal_transfer'
                  AND transaction_date >= (CURRENT_DATE - INTERVAL '3 months')
                GROUP BY 1
                ORDER BY spend DESC
                LIMIT 5
                """,
                (user_id,),
            )
            for r in cur.fetchall():
                top_categories.append({"category": r[0], "spend_last_90d_inr": round(_safe_float(r[1]), 2)})
        except Exception as exc:  # noqa: BLE001
            _rollback(conn)
            _log.warning("[trip-planner.fin_ctx] category agg failed: %s", exc)

    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        conn.close()

    # ── Final aggregates ────────────────────────────────────────────────────
    monthly_surplus = round(avg_monthly_income_realised - avg_monthly_spend, 2)
    saving_rate_pct = (
        round((monthly_surplus / avg_monthly_income_realised) * 100, 1)
        if avg_monthly_income_realised > 0
        else 0.0
    )

    snapshot.update(
        {
            "monthly_income_realised_inr": round(avg_monthly_income_realised, 2),
            "avg_monthly_spend_inr": round(avg_monthly_spend, 2),
            "monthly_surplus_inr": monthly_surplus,
            "saving_rate_pct": saving_rate_pct,
            "monthly_emi_inr": round(monthly_emi, 2),
            "active_emi_count": emi_count,
            "monthly_subscriptions_inr": round(monthly_subscriptions, 2),
            "active_subscription_count": sub_count,
            "user_city": user_city,
            "top_spending_categories_last_90d": top_categories,
            "data_source": "smartspend_postgres_live",
        }
    )
    return snapshot
