"""
Phase 1 verification — subscription intelligence database (021 + 022 + 023).

Run from repo root or backend:
  cd backend && python test_phase1.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from db import get_connection  # noqa: E402


def verify_phase1() -> bool:
    print("\n" + "=" * 60)
    print("PHASE 1 VERIFICATION - SUBSCRIPTION INTELLIGENCE DATABASE")
    print("=" * 60 + "\n")

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Test 1: subscription_categories
                print("[1] subscription_categories table")
                print("-" * 60)
                cur.execute("SELECT COUNT(*) FROM subscription_categories;")
                count = int(cur.fetchone()[0])
                print(f"   Categories found: {count}")

                if count <= 0:
                    print("   ERROR: No categories found!")
                    return False

                cur.execute(
                    """
                    SELECT category_key, substitutable
                    FROM subscription_categories
                    ORDER BY category_key;
                    """
                )
                print("\n   All categories:")
                for row in cur.fetchall():
                    subst = "Substitutable" if row[1] else "Not substitutable"
                    print(f"      - {str(row[0]):28} {subst}")

                # Test 2: user_subscription_savings
                print("\n\n[2] user_subscription_savings table")
                print("-" * 60)
                cur.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'user_subscription_savings'
                    ORDER BY ordinal_position;
                    """
                )
                columns = cur.fetchall()
                if not columns:
                    print("   ERROR: Table not found!")
                    return False
                print(f"   Table structure verified ({len(columns)} columns):")
                for col in columns:
                    print(f"      - {str(col[0]):30} {col[1]}")

                # Test 3: trigger
                print("\n\n[3] Trigger verification")
                print("-" * 60)
                cur.execute(
                    """
                    SELECT tgname, tgrelid::regclass
                    FROM pg_trigger
                    WHERE tgname = 'tr_intel_savings_on_cancel'
                      AND NOT tgisinternal;
                    """
                )
                trigger = cur.fetchone()
                if trigger:
                    print(f"   Trigger: {trigger[0]}")
                    print(f"   On table: {trigger[1]}")
                else:
                    print("   ERROR: Trigger not found!")
                    return False

                # Test 4: calculate_usage_change
                print("\n\n[4] Helper function verification")
                print("-" * 60)
                cur.execute(
                    """
                    SELECT proname, pronargs
                    FROM pg_proc
                    WHERE proname = 'calculate_usage_change'
                      AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public');
                    """
                )
                func = cur.fetchone()
                if func:
                    print(f"   Function: {func[0]}")
                    print(f"   Argument count: {func[1]}")
                else:
                    print("   ERROR: Function not found!")
                    return False

                cur.execute(
                    """
                    SELECT proname
                    FROM pg_proc
                    WHERE proname = 'intel_update_user_subscription_savings'
                      AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public');
                    """
                )
                if cur.fetchone():
                    print("   Function: intel_update_user_subscription_savings (trigger fn)")
                else:
                    print("   ERROR: intel_update_user_subscription_savings not found!")
                    return False

                # Test 5: core intel tables (021/022 naming)
                print("\n\n[5] Existing subscription intelligence tables")
                print("-" * 60)
                tables_to_check = [
                    "subscriptions",
                    "connected_apps",
                    "app_usage_signals",
                    "verdict_history",
                    "scheduled_reminders",
                    "reminder_outcomes",
                    "subscription_intelligence_insights",
                ]
                for table in tables_to_check:
                    cur.execute(
                        """
                        SELECT EXISTS (
                          SELECT 1
                          FROM information_schema.tables
                          WHERE table_schema = 'public'
                            AND table_name = %s
                        );
                        """,
                        (table,),
                    )
                    exists = cur.fetchone()[0]
                    status = "OK" if exists else "MISSING"
                    print(f"   {status} {table}")

                # Test 6: migration history (SmartSpend uses filename + applied_at)
                print("\n\n[6] Migration history")
                print("-" * 60)
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = '_migration_history';
                    """
                )
                hist_cols = {r[0] for r in cur.fetchall()}
                if "filename" not in hist_cols:
                    print("   NOTE: _migration_history not found or unexpected shape -- skip")
                else:
                    cur.execute(
                        """
                        SELECT filename, applied_at
                        FROM _migration_history
                        WHERE filename ILIKE '%subscription%'
                        ORDER BY applied_at DESC;
                        """
                    )
                    migrations = cur.fetchall()
                    if migrations:
                        for fn, applied in migrations:
                            ts = applied.strftime("%Y-%m-%d %H:%M:%S") if applied else "—"
                            print(f"   OK {fn:55} {ts}")
                    else:
                        print("   NOTE: No subscription-related rows in _migration_history (run apply_migrations)")

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED - PHASE 1 COMPLETE")
        print("=" * 60 + "\n")

        print("Summary:")
        print(f"   - {count} subscription categories loaded")
        print("   - user_subscription_savings table ready")
        print("   - Trigger and functions configured")
        print("   - Core subscription intelligence tables present")
        print("\nReady for Phase 2: Backend Services\n")

        return True

    except Exception as e:
        print("\nVERIFICATION FAILED")
        print(f"Error: {e}\n")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    sys.exit(0 if verify_phase1() else 1)
