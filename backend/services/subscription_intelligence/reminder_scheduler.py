"""Reminder scheduling and state transitions — all DB writes."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from psycopg2.extensions import connection as PgConnection


def validate_snooze_reason(reason: str | None, *, min_len: int = 10) -> bool:
    """True if accountability text meets API rules for remind_later."""
    if not reason:
        return False
    cleaned = str(reason).strip()
    return len(cleaned) >= min_len


def schedule_reminders_for_subscription(conn: PgConnection, subscription_id: int, escalation_level: int | None = None) -> int:
    """Insert T-10, T-3, T-1 (or escalated offsets) before next_billing_date."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT user_id, next_billing_date, COALESCE(reminder_escalation_tier, 1)
            FROM subscriptions WHERE id = %s AND next_billing_date IS NOT NULL;
            """,
            (subscription_id,),
        )
        row = cur.fetchone()
        if not row:
            return 0
        user_id, next_b, tier = row
        if not next_b:
            return 0

        if escalation_level is None:
            t = int(tier or 1)
            if t >= 3:
                escalation_level = 3
            elif t >= 2:
                escalation_level = 2
            else:
                escalation_level = 1

        if int(escalation_level) >= 3:
            offsets = [("t20", 20), ("t15", 15), ("t10", 10), ("t7", 7), ("t3", 3), ("t1", 1)]
        elif int(escalation_level) >= 2:
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
    accountability_reason: str | None = None,
) -> dict[str, Any]:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, subscription_id, state, reminder_type FROM scheduled_reminders
            WHERE id = %s AND user_id = %s;
            """,
            (reminder_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            return {"ok": False, "error": "Reminder not found"}
        _rid, sub_id, state, reminder_type = row
        now = datetime.utcnow()
        reason = (accountability_reason or "").strip()

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
                "UPDATE subscriptions SET sub_lifecycle = 'pending_cancel', reminder_escalation_tier = 1 WHERE id = %s;",
                (sub_id,),
            )
            cur.execute(
                """
                INSERT INTO reminder_outcomes (reminder_id, subscription_id, user_id, user_action, cancelled_within_7d, effectiveness_score, accountability_reason)
                VALUES (%s, %s, %s, 'cancel_now', TRUE, 90, %s);
                """,
                (reminder_id, sub_id, user_id, reason or None),
            )
        elif action == "remind_later":
            if not validate_snooze_reason(reason):
                return {
                    "ok": False,
                    "error": "accountability_reason_required",
                    "detail": "Why are you keeping this subscription despite low usage? (min 10 characters)",
                }
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
                INSERT INTO reminder_outcomes (reminder_id, subscription_id, user_id, user_action, cancelled_within_7d, effectiveness_score, accountability_reason)
                VALUES (%s, %s, %s, 'remind_later', FALSE, 40, %s);
                """,
                (reminder_id, sub_id, user_id, reason),
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
                INSERT INTO reminder_outcomes (reminder_id, subscription_id, user_id, user_action, cancelled_within_7d, effectiveness_score, accountability_reason)
                VALUES (%s, %s, %s, 'keep', FALSE, 20, %s);
                """,
                (reminder_id, sub_id, user_id, reason or None),
            )
            if str(reminder_type or "") == "t1":
                cur.execute(
                    """
                    UPDATE subscriptions
                    SET reminder_escalation_tier = GREATEST(COALESCE(reminder_escalation_tier, 1), 2)
                    WHERE id = %s;
                    """,
                    (sub_id,),
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


def create_reminders_with_escalation(conn: PgConnection, user_id: int) -> dict[str, Any]:
    """
    Ensure renewal reminders exist for subscriptions billing in the next 30 days.
    Escalation density follows subscriptions.reminder_escalation_tier (1=t10/t3/t1,
    2=denser, 3=maximum cadence).
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, COALESCE(reminder_escalation_tier, 1)
            FROM subscriptions
            WHERE user_id = %s
              AND next_billing_date IS NOT NULL
              AND next_billing_date > CURRENT_DATE
              AND next_billing_date <= CURRENT_DATE + INTERVAL '30 days';
            """,
            (user_id,),
        )
        rows = cur.fetchall()
        reminder_rows = 0
        for sid, tier in rows:
            esc = 3 if int(tier or 1) >= 3 else (2 if int(tier or 1) >= 2 else 1)
            reminder_rows += schedule_reminders_for_subscription(conn, int(sid), esc)
        return {"subscriptions_scheduled": len(rows), "reminder_rows_inserted": reminder_rows}
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


if __name__ == "__main__":
    import sys
    from pathlib import Path

    _root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(_root))
    from db import get_connection

    uid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print("=" * 60)
    print("TESTING REMINDER SCHEDULER")
    print("=" * 60)
    with get_connection() as conn:
        summary = create_reminders_with_escalation(conn, uid)
        conn.commit()
        print(f"\ncreate_reminders_with_escalation: {summary}")

        print("\nvalidate_snooze_reason:")
        cases = [
            ("", False),
            ("   ", False),
            ("Ok", False),
            ("I use this during holidays", True),
            ("My family uses it", True),
        ]
        for text, expected in cases:
            got = validate_snooze_reason(text)
            mark = "OK" if got == expected else "MISMATCH"
            print(f"  {mark} len={len(text)!r} -> {got} (expected {expected})")
    print("=" * 60)
