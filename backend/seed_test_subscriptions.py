"""
Seed subscription + app_usage_signals for Phase 2 verification (real schema).

Reuses services.subscription_intelligence.seed_demo.run_seed_for_user (90-day signals,
subscriptions with merchant / linked_app_package / intelligence_category).

Then:
  - Adds YouTube Music row (usage for com.google.android.apps.youtube.music is already seeded).
  - Sets ChatGPT Plus to Rs 0 so batch upgrade detector can flag heavy free-tier usage.

Usage (from backend directory):
  python seed_test_subscriptions.py [user_id]

Example:
  python seed_test_subscriptions.py 1
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from db import get_connection  # noqa: E402
from services.subscription_intelligence.seed_demo import run_seed_for_user  # noqa: E402
from services.subscription_intelligence.verdict_engine import (  # noqa: E402
    evaluate_subscription,
    generate_all_verdict_reports,
    persist_verdict,
)
from services.subscription_intelligence import (  # noqa: E402
    detect_category_migrations,
    schedule_reminders_for_subscription,
)


def _ensure_youtube_music_subscription(conn, user_id: int) -> None:
    """Subscription row for YT Music; seed_demo already writes usage for this package."""
    cur = conn.cursor()
    try:
        today = date.today()
        nb = today + timedelta(days=12)
        cur.execute(
            """
            INSERT INTO subscriptions (
              user_id, merchant, amount, billing_cycle, category, status,
              usage_score, last_used_days, monthly_cost, times_charged, first_charged, last_charged,
              intelligence_category, linked_app_package, billing_day, next_billing_date, currency, sub_lifecycle, is_pro
            ) VALUES (
              %s, %s, %s, 'MONTHLY', 'Entertainment', 'ACTIVE',
              72, 3, %s, 10, %s, %s,
              'music', %s, %s, %s, 'INR', 'active', FALSE
            )
            ON CONFLICT (user_id, merchant) DO UPDATE SET
              amount = EXCLUDED.amount,
              monthly_cost = EXCLUDED.monthly_cost,
              intelligence_category = EXCLUDED.intelligence_category,
              linked_app_package = EXCLUDED.linked_app_package,
              billing_day = EXCLUDED.billing_day,
              next_billing_date = EXCLUDED.next_billing_date;
            """,
            (
                user_id,
                "YouTube Music",
                99.0,
                99.0,
                today - timedelta(days=200),
                today - timedelta(days=4),
                "com.google.android.apps.youtube.music",
                nb.day,
                nb,
            ),
        )
    finally:
        cur.close()


def _post_seed_tweaks(conn, user_id: int) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE subscriptions
            SET monthly_cost = 0, amount = 0, is_pro = FALSE
            WHERE user_id = %s AND merchant ILIKE '%%ChatGPT%%';
            """,
            (user_id,),
        )
    finally:
        cur.close()


def _refresh_verdicts_and_reminders(conn, user_id: int) -> None:
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM subscriptions WHERE user_id = %s ORDER BY id;", (user_id,))
        ids = [int(r[0]) for r in cur.fetchall()]
    finally:
        cur.close()
    for sid in ids:
        vr = evaluate_subscription(conn, sid)
        if vr is not None:
            persist_verdict(conn, sid, vr)
            schedule_reminders_for_subscription(conn, sid)


def main() -> int:
    print("=" * 60)
    print("SEED TEST SUBSCRIPTIONS (SmartSpend schema)")
    print("=" * 60)

    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    try:
        with get_connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT id, COALESCE(name, email, 'user') FROM users WHERE id = %s;", (user_id,))
                row = cur.fetchone()
            finally:
                cur.close()

            if not row:
                print(f"ERROR: user id {user_id} not found. Pass an existing user id.")
                return 1

            print(f"OK User {row[0]}: {row[1]}")

            print("\nRunning run_seed_for_user (wipes prior intel usage for this user)...")
            run_seed_for_user(conn, user_id, wipe_device=True)

            print("Adding YouTube Music subscription row + ChatGPT Rs0 tweak...")
            _ensure_youtube_music_subscription(conn, user_id)
            _post_seed_tweaks(conn, user_id)

            print("Re-evaluating verdicts + scheduling reminders...")
            _refresh_verdicts_and_reminders(conn, user_id)

            conn.commit()

            cur = conn.cursor()
            try:
                cur.execute("SELECT COUNT(*) FROM subscriptions WHERE user_id = %s;", (user_id,))
                n_sub = int(cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM app_usage_signals WHERE user_id = %s;", (user_id,))
                n_use = int(cur.fetchone()[0])
            finally:
                cur.close()

            print("\nVerification:")
            print(f"  subscriptions for user: {n_sub}")
            print(f"  app_usage_signals rows: {n_use}")

            print("\nBatch detectors (generate_all_verdict_reports):")
            verdicts = generate_all_verdict_reports(conn, user_id)
            for k in ("thriving", "declining", "dormant", "upgrade_recommended"):
                rows = verdicts.get(k) or []
                print(f"  {k}: {len(rows)}")
                for v in rows[:4]:
                    print(f"    - {v.get('subscription_name') or '?'}: {(v.get('reasoning') or '')[:64]}")

            mig = detect_category_migrations(conn, user_id)
            print(f"\n  category migrations: {len(mig)}")

            print("\n" + "=" * 60)
            print("DONE. Re-run:")
            print("  python services/subscription_intelligence/verdict_engine.py", user_id)
            print("  python services/subscription_intelligence/substitution_detector.py", user_id)
            print("  python services/subscription_intelligence/reminder_scheduler.py", user_id)
            print("=" * 60)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
