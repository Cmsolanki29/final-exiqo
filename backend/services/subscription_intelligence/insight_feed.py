"""Deduped behavioral insight rows (substitutions, future: value-swap, leakage)."""
from __future__ import annotations

from typing import Any

from psycopg2.extensions import connection as PgConnection


def persist_substitution_insights(conn: PgConnection, user_id: int, insights: list[dict[str, Any]]) -> int:
    """Upsert substitution / migration insights; preserves read_at when user already read."""
    if not insights:
        return 0
    cur = conn.cursor()
    n = 0
    try:
        for ins in insights:
            sid = ins.get("subscription_id")
            to_pkg = str(ins.get("to_package") or "")
            dedupe_key = f"substitution:{sid}:{to_pkg}"[:220]
            title = str(ins.get("headline") or "Substitution detected")[:240]
            body = str(ins.get("body") or "")
            cur.execute(
                """
                INSERT INTO subscription_intelligence_insights (
                  user_id, subscription_id, dedupe_key, insight_type, title, body, priority, updated_at
                ) VALUES (%s, %s, %s, 'substitution', %s, %s, 1, NOW())
                ON CONFLICT (user_id, dedupe_key) DO UPDATE SET
                  title = EXCLUDED.title,
                  body = EXCLUDED.body,
                  subscription_id = COALESCE(EXCLUDED.subscription_id, subscription_intelligence_insights.subscription_id),
                  priority = LEAST(subscription_intelligence_insights.priority, EXCLUDED.priority),
                  updated_at = NOW();
                """,
                (user_id, sid, dedupe_key, title, body),
            )
            n += 1
        return n
    finally:
        cur.close()


def fetch_intelligence_insights(conn: PgConnection, user_id: int, *, limit: int = 20) -> list[dict[str, Any]]:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, subscription_id, insight_type, title, body, priority, read_at, created_at
            FROM subscription_intelligence_insights
            WHERE user_id = %s
            ORDER BY (read_at IS NULL) DESC, priority ASC, created_at DESC
            LIMIT %s;
            """,
            (user_id, limit),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "subscription_id": r[1],
                "insight_type": r[2],
                "title": r[3],
                "body": r[4],
                "priority": r[5],
                "read_at": r[6].isoformat() if r[6] else None,
                "created_at": r[7].isoformat() if r[7] else None,
            }
            for r in rows
        ]
    finally:
        cur.close()


def sync_verdict_insights(conn: PgConnection, user_id: int) -> int:
    """
    Mirror declining / dormant / dead verdicts into the intelligence feed so the UI is not empty
    when substitution heuristics never fire. Removes rows when a subscription recovers.
    """
    cur = conn.cursor()
    n = 0
    try:
        cur.execute(
            """
            DELETE FROM subscription_intelligence_insights i
            WHERE i.user_id = %s
              AND i.insight_type = 'verdict'
              AND NOT EXISTS (
                SELECT 1 FROM subscriptions s
                WHERE s.id = i.subscription_id
                  AND s.user_id = %s
                  AND s.current_verdict IN ('declining', 'dormant', 'dead')
              );
            """,
            (user_id, user_id),
        )
        cur.execute(
            """
            SELECT id, merchant, current_verdict, verdict_reason, verdict_monthly_waste
            FROM subscriptions
            WHERE user_id = %s
              AND current_verdict IN ('declining', 'dormant', 'dead');
            """,
            (user_id,),
        )
        rows = cur.fetchall()
        for sid, merchant, verdict, reason, waste in rows:
            dedupe_key = f"verdict:{int(sid)}"
            title = f"{(verdict or '').title()} — {merchant or 'Subscription'}"
            waste_f = float(waste or 0)
            reason_s = (reason or "").strip() or "Usage pattern suggests revisiting this charge."
            body = reason_s
            if waste_f > 0.005:
                body = f"{body} Approx. waste flagged: ₹{waste_f:,.0f}/mo."
            cur.execute(
                """
                INSERT INTO subscription_intelligence_insights (
                  user_id, subscription_id, dedupe_key, insight_type, title, body, priority, updated_at
                ) VALUES (%s, %s, %s, 'verdict', %s, %s, 2, NOW())
                ON CONFLICT (user_id, dedupe_key) DO UPDATE SET
                  title = EXCLUDED.title,
                  body = EXCLUDED.body,
                  subscription_id = EXCLUDED.subscription_id,
                  priority = EXCLUDED.priority,
                  updated_at = NOW();
                """,
                (user_id, int(sid), dedupe_key, title[:240], body),
            )
            n += 1
        return n
    finally:
        cur.close()


def mark_insight_read(conn: PgConnection, user_id: int, insight_id: int) -> bool:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE subscription_intelligence_insights
            SET read_at = NOW(), updated_at = NOW()
            WHERE id = %s AND user_id = %s AND read_at IS NULL;
            """,
            (insight_id, user_id),
        )
        return cur.rowcount > 0
    finally:
        cur.close()
