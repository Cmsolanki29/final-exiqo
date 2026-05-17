"""Shared scoped transaction analytics (dashboard view mode)."""

from __future__ import annotations

from datetime import date
from typing import Any

from services.dashboard_scope import fetch_dashboard_mode, transaction_scope_sql


def statement_period_card_spend(cur, user_id: int, mode: str | None = None) -> list[dict[str, Any]]:
    """
    Per credit-card source: sum of debits between min/max txn dates on that source (statement period).
    """
    if mode is None:
        mode = fetch_dashboard_mode(cur, user_id)
    scope = transaction_scope_sql("t", mode)
    cur.execute(
        f"""
        SELECT cs.id,
               cs.institution_name,
               cs.source_type,
               COALESCE(SUM(t.amount), 0)::float AS statement_spend,
               COUNT(t.id)::int AS txn_count,
               MIN(t.transaction_date) AS period_start,
               MAX(t.transaction_date) AS period_end
        FROM transactions t
        JOIN connected_sources cs
          ON cs.id = t.connected_source_id AND cs.user_id = t.user_id
        WHERE t.user_id = %s
          AND UPPER(t.type) = 'DEBIT'
          AND cs.source_type = 'credit_card'
          AND ({scope})
        GROUP BY cs.id, cs.institution_name, cs.source_type
        HAVING COUNT(t.id) > 0
        ORDER BY statement_spend DESC;
        """,
        (user_id,),
    )
    out: list[dict[str, Any]] = []
    for row in cur.fetchall():
        out.append(
            {
                "source_id": row[0],
                "institution_name": row[1],
                "source_type": row[2],
                "statement_spend": round(float(row[3] or 0), 2),
                "transaction_count": int(row[4] or 0),
                "period_start": row[5].isoformat() if row[5] else None,
                "period_end": row[6].isoformat() if row[6] else None,
            }
        )
    return out


def total_statement_spend(cur, user_id: int, mode: str | None = None) -> float:
    rows = statement_period_card_spend(cur, user_id, mode)
    return round(sum(r["statement_spend"] for r in rows), 2)
