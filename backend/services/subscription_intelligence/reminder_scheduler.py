"""Reminder scheduling and state transitions — all DB writes."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from psycopg2.extensions import connection as PgConnection


def schedule_reminders_for_subscription(conn: PgConnection, subscription_id: int, escalation_level: int = 1) -> int:
    """Insert T-10, T-3, T-1 (or escalated offsets) before next_billing_date."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT user_id, next_billing_date FROM subscriptions WHERE id = %s AND next_billing_date IS NOT NULL;
            """,
            (subscription_id,),
        )
        row = cur.fetchone()
        if not row:
            return 0
        user_id, next_b = row
        if not next_b:
            return 0

        if escalation_level >= 2:
            offsets = [("t15", 15), ("t10", 10), ("t5", 5), ("t2", 2), ("t1", 1)]
        else:
            offsets = [("t10", 10), ("t3", 3), ("t1", 1)]

        cur.execute(
            "DELETE FROM scheduled_reminders WHERE subscription_id = %s AND state = 'pending';",
            (subscription_id,),
        )
        inserted = 0
        for rtype, days_before in offsets:
            fire = datetime.combine(next_b, datetime.min.time()) - timedelta(days=days_before)
            cur.execute(
                """
                INSERT INTO scheduled_reminders (
                  subscription_id, user_id, fire_at, reminder_type, state, escalation_level
                ) VALUES (%s, %s, %s, %s, 'pending', %s);
                """,
                (subscription_id, user_id, fire, rtype, escalation_level),
            )
            inserted += 1
        return inserted
    finally:
        cur.close()


def tick_due_reminders(conn: PgConnection, user_id: int) -> list[dict[str, Any]]:
    """Promote pending reminders whose fire_at is due to 'shown'."""
    cur = conn.cursor()
    try:
        now = datetime.utcnow()
        cur.execute(
            """
            UPDATE scheduled_reminders
            SET state = 'shown', shown_at = %s
            WHERE user_id = %s AND fire_at <= %s AND state IN ('pending', 'snoozed')
            RETURNING id, subscription_id, reminder_type, fire_at, escalation_level;
            """,
            (now, user_id, now),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "subscription_id": r[1],
                "reminder_type": r[2],
                "fire_at": r[3].isoformat() if r[3] else None,
                "escalation_level": r[4],
            }
            for r in rows
        ]
    finally:
        cur.close()


def apply_reminder_action(
    conn: PgConnection,
    reminder_id: int,
    user_id: int,
    action: str,
) -> dict[str, Any]:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, subscription_id, state FROM scheduled_reminders
            WHERE id = %s AND user_id = %s;
            """,
            (reminder_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            return {"ok": False, "error": "Reminder not found"}
        _rid, sub_id, state = row
        now = datetime.utcnow()

        if action == "cancel_now":
            cur.execute(
                """
                UPDATE scheduled_reminders
                SET state = 'acted', acted_at = %s, user_action = 'cancel_now'
                WHERE id = %s;
                """,
                (now, reminder_id),
            )
            cur.execute(
                "UPDATE subscriptions SET sub_lifecycle = 'pending_cancel' WHERE id = %s;",
                (sub_id,),
            )
            cur.execute(
                """
                INSERT INTO reminder_outcomes (reminder_id, subscription_id, user_id, user_action, cancelled_within_7d, effectiveness_score)
                VALUES (%s, %s, %s, 'cancel_now', TRUE, 90);
                """,
                (reminder_id, sub_id, user_id),
            )
        elif action == "remind_later":
            cur.execute(
                """
                UPDATE scheduled_reminders
                SET state = 'pending', fire_at = %s, user_action = 'remind_later',
                    escalation_level = escalation_level + 1
                WHERE id = %s;
                """,
                (now + timedelta(hours=24), reminder_id),
            )
            cur.execute(
                """
                INSERT INTO reminder_outcomes (reminder_id, subscription_id, user_id, user_action, cancelled_within_7d, effectiveness_score)
                VALUES (%s, %s, %s, 'remind_later', FALSE, 40);
                """,
                (reminder_id, sub_id, user_id),
            )
        elif action == "keep":
            cur.execute(
                """
                UPDATE scheduled_reminders
                SET state = 'dismissed', acted_at = %s, user_action = 'keep'
                WHERE id = %s;
                """,
                (now, reminder_id),
            )
            cur.execute(
                """
                UPDATE scheduled_reminders SET state = 'dismissed'
                WHERE subscription_id = %s AND user_id = %s AND state IN ('pending', 'shown');
                """,
                (sub_id, user_id),
            )
            cur.execute(
                """
                INSERT INTO reminder_outcomes (reminder_id, subscription_id, user_id, user_action, cancelled_within_7d, effectiveness_score)
                VALUES (%s, %s, %s, 'keep', FALSE, 20);
                """,
                (reminder_id, sub_id, user_id),
            )
        else:
            return {"ok": False, "error": "Invalid action"}

        return {"ok": True, "subscription_id": sub_id}
    finally:
        cur.close()


def simulate_next_day(conn: PgConnection, user_id: int) -> int:
    """Demo: pull reminder fire_at 24h earlier so pending items become due."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE scheduled_reminders
            SET fire_at = fire_at - interval '24 hours'
            WHERE user_id = %s AND state IN ('pending', 'snoozed');
            """,
            (user_id,),
        )
        return cur.rowcount
    finally:
        cur.close()


def fetch_pending_reminders(conn: PgConnection, user_id: int) -> list[dict[str, Any]]:
    tick_due_reminders(conn, user_id)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT r.id, r.subscription_id, r.reminder_type, r.fire_at, r.state, r.escalation_level,
                   s.merchant, s.monthly_cost
            FROM scheduled_reminders r
            JOIN subscriptions s ON s.id = r.subscription_id
            WHERE r.user_id = %s AND r.state = 'shown'
            ORDER BY r.fire_at ASC
            LIMIT 5;
            """,
            (user_id,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "subscription_id": r[1],
                "reminder_type": r[2],
                "fire_at": r[3].isoformat() if r[3] else None,
                "state": r[4],
                "escalation_level": r[5],
                "merchant": r[6],
                "monthly_cost": float(r[7] or 0),
            }
            for r in rows
        ]
    finally:
        cur.close()
