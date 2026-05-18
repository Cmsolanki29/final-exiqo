"""Reminder scheduling and state transitions — all DB writes."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from psycopg2.extensions import connection as PgConnection

# Lower = more urgent (surfaced first when multiple offsets are due).
REMINDER_TYPE_URGENCY: dict[str, int] = {
    "t1": 0,
    "t2": 1,
    "t3": 2,
    "t5": 3,
    "t7": 4,
    "t10": 5,
    "t15": 6,
    "t20": 7,
}

# Demo / onboarding polish: one active cadence label per merchant (Tier 1 + Tier 2 mix).
REMINDER_SHOWCASE_TARGETS: list[tuple[str, str, int]] = [
    ("Netflix", "t3", 1),
    ("Spotify", "t10", 1),
    ("YouTube", "t1", 1),
    ("LinkedIn", "t15", 2),
    ("ChatGPT", "t5", 2),
    ("Canva", "t3", 1),
    ("Amazon", "t10", 2),
]


def _reminder_urgency(reminder_type: str | None) -> int:
    return REMINDER_TYPE_URGENCY.get(str(reminder_type or "").lower(), 99)


def validate_snooze_reason(reason: str | None, *, min_len: int = 10) -> bool:
    """True if accountability text meets API rules for escalated remind_later."""
    if not reason:
        return False
    cleaned = str(reason).strip()
    return len(cleaned) >= min_len


def snooze_requires_accountability_reason(subscription_escalation_tier: int | None) -> bool:
    """
    Tier 1 = first-cycle renewal nudges (T-10 / T-3 / T-1): snooze without a reason.
    Tier 2+ = denser cadence after prior-cycle ignore/keep escalation: mandatory accountability text.
    """
    return int(subscription_escalation_tier or 1) >= 2


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


def _collapse_duplicate_shown_reminders(conn: PgConnection, user_id: int) -> None:
    """Keep only the most urgent 'shown' row per subscription."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, subscription_id, reminder_type
            FROM scheduled_reminders
            WHERE user_id = %s AND state = 'shown'
            ORDER BY subscription_id, fire_at ASC;
            """,
            (user_id,),
        )
        best_by_sub: dict[int, tuple[int, int]] = {}
        all_rows: list[tuple[int, int, str]] = []
        for rid, sid, rtype in cur.fetchall():
            all_rows.append((int(rid), int(sid), str(rtype or "")))
        for rid, sid, rtype in all_rows:
            urg = _reminder_urgency(rtype)
            prev = best_by_sub.get(sid)
            if prev is None or urg < prev[1]:
                best_by_sub[sid] = (rid, urg)
        keep_ids = {rid for rid, _ in best_by_sub.values()}
        demote_ids = [rid for rid, sid, _ in all_rows if rid not in keep_ids]
        if not demote_ids:
            return
        cur.execute(
            """
            UPDATE scheduled_reminders
            SET state = 'pending', shown_at = NULL
            WHERE id = ANY(%s);
            """,
            (demote_ids,),
        )
    finally:
        cur.close()


def tick_due_reminders(conn: PgConnection, user_id: int) -> list[dict[str, Any]]:
    """Promote the single most urgent due reminder per subscription to 'shown'."""
    cur = conn.cursor()
    try:
        now = datetime.utcnow()
        cur.execute(
            """
            SELECT id, subscription_id, reminder_type, fire_at, escalation_level
            FROM scheduled_reminders
            WHERE user_id = %s AND fire_at <= %s AND state IN ('pending', 'snoozed')
            ORDER BY subscription_id, fire_at ASC;
            """,
            (user_id, now),
        )
        due_rows = cur.fetchall()
        cur.execute(
            """
            SELECT DISTINCT subscription_id
            FROM scheduled_reminders
            WHERE user_id = %s AND state = 'shown';
            """,
            (user_id,),
        )
        subs_with_shown = {int(r[0]) for r in cur.fetchall()}

        best_by_sub: dict[int, tuple] = {}
        for row in due_rows:
            sid = int(row[1])
            if sid in subs_with_shown:
                continue
            urgency = _reminder_urgency(row[2])
            prev = best_by_sub.get(sid)
            if prev is None or urgency < _reminder_urgency(prev[2]):
                best_by_sub[sid] = row

        promoted: list[dict[str, Any]] = []
        for row in best_by_sub.values():
            cur.execute(
                """
                UPDATE scheduled_reminders
                SET state = 'shown', shown_at = %s
                WHERE id = %s AND state IN ('pending', 'snoozed')
                RETURNING id, subscription_id, reminder_type, fire_at, escalation_level;
                """,
                (now, int(row[0])),
            )
            updated = cur.fetchone()
            if updated:
                promoted.append(
                    {
                        "id": updated[0],
                        "subscription_id": updated[1],
                        "reminder_type": updated[2],
                        "fire_at": updated[3].isoformat() if updated[3] else None,
                        "escalation_level": updated[4],
                    }
                )
        _collapse_duplicate_shown_reminders(conn, user_id)
        return promoted
    finally:
        cur.close()


def _shown_cadence_lacks_variety(conn: PgConnection, user_id: int) -> bool:
    """True when active reminders should be spread across T-15…T-1 and Tier 1/2."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(*)::int, COUNT(DISTINCT reminder_type)::int
            FROM scheduled_reminders
            WHERE user_id = %s AND state = 'shown';
            """,
            (user_id,),
        )
        total, distinct = cur.fetchone() or (0, 0)
        total_i = int(total or 0)
        distinct_i = int(distinct or 0)
        if total_i < 2:
            return False
        if distinct_i <= 1:
            return True
        if total_i >= 3 and distinct_i < 3:
            return True
        return False
    finally:
        cur.close()


def _dedupe_shown_one_per_merchant(conn: PgConnection, user_id: int) -> int:
    """Dismiss extra 'shown' rows when duplicate subscription rows share a merchant name."""
    cur = conn.cursor()
    dismissed = 0
    try:
        now = datetime.utcnow()
        cur.execute(
            """
            SELECT lower(trim(s.merchant)) AS mkey, array_agg(r.id ORDER BY r.fire_at ASC, r.id ASC)
            FROM scheduled_reminders r
            JOIN subscriptions s ON s.id = r.subscription_id
            WHERE r.user_id = %s AND r.state = 'shown' AND trim(coalesce(s.merchant, '')) <> ''
            GROUP BY lower(trim(s.merchant))
            HAVING COUNT(*) > 1;
            """,
            (user_id,),
        )
        for _mkey, ids in cur.fetchall():
            demote = [int(i) for i in (ids or [])[1:]]
            if not demote:
                continue
            cur.execute(
                """
                UPDATE scheduled_reminders
                SET state = 'dismissed', acted_at = %s
                WHERE id = ANY(%s);
                """,
                (now, demote),
            )
            dismissed += cur.rowcount
        return dismissed
    finally:
        cur.close()


def _dismiss_active_reminders_on_duplicate_subs(
    conn: PgConnection, user_id: int, primary_sub_id: int, merchant_hint: str
) -> None:
    """Hide reminders on duplicate subscription rows for the same merchant (keeps primary only)."""
    cur = conn.cursor()
    try:
        now = datetime.utcnow()
        cur.execute(
            """
            UPDATE scheduled_reminders r
            SET state = 'dismissed', acted_at = %s
            FROM subscriptions s
            WHERE r.subscription_id = s.id
              AND r.user_id = %s
              AND s.merchant ILIKE %s
              AND s.id <> %s
              AND r.state IN ('shown', 'pending', 'snoozed');
            """,
            (now, user_id, f"%{merchant_hint}%", primary_sub_id),
        )
    finally:
        cur.close()


def prepare_reminders_for_user(conn: PgConnection, user_id: int) -> None:
    """Promote due rows, enforce per-merchant showcase labels, dedupe duplicate subscription rows."""
    tick_due_reminders(conn, user_id)
    apply_reminder_showcase_variety(conn, user_id)
    _dedupe_shown_one_per_merchant(conn, user_id)
    _collapse_duplicate_shown_reminders(conn, user_id)


def apply_reminder_showcase_variety(conn: PgConnection, user_id: int) -> int:
    """
    Spread active renewal labels (T-15, T-10, T-3, Tier 1/2) across subscriptions
  for demo readability. Does not change billing dates or verdicts.
    """
    cur = conn.cursor()
    adjusted = 0
    try:
        now = datetime.utcnow()
        past_fire = now - timedelta(hours=2)
        for merchant_hint, rtype, tier in REMINDER_SHOWCASE_TARGETS:
            cur.execute(
                """
                SELECT id, user_id
                FROM subscriptions
                WHERE user_id = %s AND merchant ILIKE %s
                ORDER BY id
                LIMIT 1;
                """,
                (user_id, f"%{merchant_hint}%"),
            )
            row = cur.fetchone()
            if not row:
                continue
            sub_id, sub_user_id = int(row[0]), int(row[1])
            esc = 3 if tier >= 3 else (2 if tier >= 2 else 1)
            cur.execute(
                "UPDATE subscriptions SET reminder_escalation_tier = %s WHERE id = %s;",
                (tier, sub_id),
            )
            schedule_reminders_for_subscription(conn, sub_id, esc)
            cur.execute(
                """
                UPDATE scheduled_reminders
                SET state = 'pending', shown_at = NULL
                WHERE subscription_id = %s AND state = 'shown';
                """,
                (sub_id,),
            )
            cur.execute(
                """
                UPDATE scheduled_reminders
                SET state = 'shown', shown_at = %s, fire_at = %s
                WHERE subscription_id = %s AND reminder_type = %s;
                """,
                (now, past_fire, sub_id, rtype),
            )
            if cur.rowcount:
                adjusted += 1
            else:
                cur.execute(
                    """
                    INSERT INTO scheduled_reminders (
                      subscription_id, user_id, fire_at, reminder_type, state, escalation_level, shown_at
                    ) VALUES (%s, %s, %s, %s, 'shown', %s, %s);
                    """,
                    (sub_id, sub_user_id, past_fire, rtype, esc, now),
                )
                adjusted += 1
            _dismiss_active_reminders_on_duplicate_subs(conn, user_id, sub_id, merchant_hint)
        _collapse_duplicate_shown_reminders(conn, user_id)
        return adjusted
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
            SELECT r.id, r.subscription_id, r.state, r.reminder_type,
                   COALESCE(s.reminder_escalation_tier, 1)
            FROM scheduled_reminders r
            JOIN subscriptions s ON s.id = r.subscription_id
            WHERE r.id = %s AND r.user_id = %s;
            """,
            (reminder_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            return {"ok": False, "error": "Reminder not found"}
        _rid, sub_id, state, reminder_type, sub_escalation_tier = row
        now = datetime.utcnow()
        reason = (accountability_reason or "").strip()
        require_snooze_accountability = snooze_requires_accountability_reason(sub_escalation_tier)

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
            if require_snooze_accountability and not validate_snooze_reason(reason):
                return {
                    "ok": False,
                    "error": "accountability_reason_required",
                    "detail": "Escalated renewal cycle: explain why you are keeping this subscription (min 10 characters).",
                }
            reason_for_outcome = reason if require_snooze_accountability else (reason or None)
            cur.execute(
                """
                UPDATE scheduled_reminders
                SET state = 'snoozed', fire_at = %s, user_action = 'remind_later',
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
                (reminder_id, sub_id, user_id, reason_for_outcome),
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
        prepare_reminders_for_user(conn, user_id)
        return {
            "subscriptions_scheduled": len(rows),
            "reminder_rows_inserted": reminder_rows,
            "showcase_cadence_adjusted": 1,
        }
    finally:
        cur.close()


def fetch_pending_reminders(conn: PgConnection, user_id: int) -> list[dict[str, Any]]:
    prepare_reminders_for_user(conn, user_id)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT r.id, r.subscription_id, r.reminder_type, r.fire_at, r.state, r.escalation_level,
                   s.merchant, s.monthly_cost, s.next_billing_date, s.current_verdict, s.verdict_reason,
                   s.verdict_monthly_waste, s.intelligence_category, s.linked_app_package,
                   COALESCE(s.reminder_escalation_tier, 1)
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
                "next_billing_date": r[8].isoformat() if r[8] else None,
                "current_verdict": r[9],
                "verdict_reason": r[10],
                "verdict_monthly_waste": float(r[11] or 0),
                "intelligence_category": r[12],
                "linked_app_package": r[13],
                "reminder_escalation_tier": int(r[14] or 1),
            }
            for r in rows
        ]
    finally:
        cur.close()


def fetch_reminders_feed(conn: PgConnection, user_id: int, *, limit: int = 50) -> list[dict[str, Any]]:
    """Shown + pending + snoozed (excludes dismissed/acted) for full renewal list UI."""
    prepare_reminders_for_user(conn, user_id)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT r.id, r.subscription_id, r.reminder_type, r.fire_at, r.state, r.escalation_level,
                   s.merchant, s.monthly_cost, s.next_billing_date, s.current_verdict, s.verdict_reason,
                   s.verdict_monthly_waste, s.intelligence_category, s.linked_app_package,
                   COALESCE(s.reminder_escalation_tier, 1)
            FROM scheduled_reminders r
            JOIN subscriptions s ON s.id = r.subscription_id
            WHERE r.user_id = %s AND r.state IN ('pending', 'shown', 'snoozed')
            ORDER BY
              CASE r.state WHEN 'shown' THEN 0 WHEN 'snoozed' THEN 1 ELSE 2 END,
              r.fire_at ASC
            LIMIT %s;
            """,
            (user_id, int(limit)),
        )
        rows = cur.fetchall()
        # One card per merchant for "shown" (duplicate subscription rows are common after imports).
        seen_merchant_shown: set[str] = set()
        filtered: list[tuple] = []
        for row in rows:
            merchant = str(row[6] or "").strip().lower()
            state = str(row[4] or "")
            if state == "shown" and merchant:
                if merchant in seen_merchant_shown:
                    continue
                seen_merchant_shown.add(merchant)
            filtered.append(row)
        rows = filtered
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
                "next_billing_date": r[8].isoformat() if r[8] else None,
                "current_verdict": r[9],
                "verdict_reason": r[10],
                "verdict_monthly_waste": float(r[11] or 0),
                "intelligence_category": r[12],
                "linked_app_package": r[13],
                "reminder_escalation_tier": int(r[14] or 1),
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
