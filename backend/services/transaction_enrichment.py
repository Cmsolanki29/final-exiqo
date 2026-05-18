"""Post-insert enrichment: anomaly heuristics and monthly_summary sync."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from services.scorer import calculate_health_score


def heuristic_anomaly(
    merchant: str,
    description: str,
    amount: float,
    txn_type: str,
) -> tuple[bool, int, str, str | None]:
    """
    Returns (anomaly_flag, risk_score, risk_level, anomaly_reason).
  """
    text = f"{merchant} {description}".upper()
    low = text.lower()

    if txn_type.upper() == "DEBIT" and amount <= 10 and any(
        k in low for k in ("micro auth", "apple.com/bill", "verify", "auth ")
    ):
        return True, 72, "HIGH", "Suspicious micro-authorization (card verification)"

    if txn_type.upper() == "DEBIT" and any(
        k in low for k in ("intl pos", "ireland", "international", "foreign", "meta ads")
    ):
        if amount >= 1000:
            return True, 68, "HIGH", "International debit — verify merchant"

    if txn_type.upper() == "CREDIT" and amount >= 50000 and any(k in low for k in ("payroll", "salary", "infosys")):
        return False, 5, "LOW", None

    return False, 0, "LOW", None


def sync_monthly_summary_for_month(conn, user_id: int, year: int, month: int) -> None:
    """Recompute monthly_summary from scoped transactions for one calendar month."""
    cur = conn.cursor()
    try:
        from services.dashboard_scope import fetch_dashboard_mode, transaction_scope_sql

        mode = fetch_dashboard_mode(cur, user_id)
        scope = transaction_scope_sql("t", mode)
        cur.execute(
            f"""
            SELECT
                COALESCE(SUM(CASE WHEN t.type = 'CREDIT' THEN t.amount ELSE 0 END), 0)::float,
                COALESCE(SUM(CASE WHEN t.type = 'DEBIT' THEN t.amount ELSE 0 END), 0)::float,
                COUNT(*)::bigint,
                COUNT(*) FILTER (WHERE COALESCE(t.anomaly_flag, FALSE))::bigint
            FROM transactions t
            WHERE t.user_id = %s
              AND EXTRACT(YEAR FROM t.transaction_date)::int = %s
              AND EXTRACT(MONTH FROM t.transaction_date)::int = %s
              AND ({scope});
            """,
            (user_id, year, month),
        )
        inc, exp, _cnt, anom = cur.fetchone()
        total_income = float(inc or 0)
        total_expense = float(exp or 0)
        saved = max(0.0, total_income - total_expense)
        savings_rate = round((saved / total_income) * 100, 2) if total_income > 0 else 0.0

        hs = calculate_health_score(conn, user_id, month, year, scope=mode)
        health_score = int(hs.score or 0)

        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'monthly_summary'
            """
        )
        ms_cols = {r[0] for r in cur.fetchall()}
        if not ms_cols:
            return

        row_vals: dict[str, Any] = {
            "user_id": user_id,
            "year": year,
            "month": month,
            "total_income": total_income,
            "total_expense": total_expense,
            "total_saved": saved,
            "savings_rate": savings_rate,
            "health_score": health_score,
            "anomaly_count": int(anom or 0),
            "high_risk_count": 0,
        }
        if "computed_at" in ms_cols:
            row_vals["computed_at"] = datetime.now(timezone.utc)

        keys = [k for k in row_vals if k in ms_cols]
        vals = [row_vals[k] for k in keys]
        updates = ", ".join(f"{k} = EXCLUDED.{k}" for k in keys if k not in ("user_id", "year", "month"))
        cur.execute(
            f"""
            INSERT INTO monthly_summary ({", ".join(keys)})
            VALUES ({", ".join(["%s"] * len(keys))})
            ON CONFLICT (user_id, month, year) DO UPDATE SET {updates};
            """,
            vals,
        )
    finally:
        cur.close()


def sync_monthly_summaries_for_document(conn, user_id: int, date_range: str | None) -> None:
    """Refresh monthly_summary for months mentioned in statement period text."""
    if not date_range:
        sync_monthly_summary_for_month(conn, user_id, date.today().year, date.today().month)
        return
    # e.g. "01 May 2026 - 30 May 2026"
    import re

    m = re.search(r"([A-Za-z]+)\s+(\d{4})", date_range)
    if not m:
        return
    mon_name = m.group(1).lower()[:3]
    year = int(m.group(2))
    month_map = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    month = month_map.get(mon_name)
    if month:
        sync_monthly_summary_for_month(conn, user_id, year, month)
