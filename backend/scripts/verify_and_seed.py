"""
Phase 0: Verify current DB state and top-up any missing seed data.
Checks all tables needed for the full test mission.
"""
import psycopg2
import psycopg2.extras
import random
import os
import uuid
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv('../.env')
db_host = os.getenv('DB_HOST', '127.0.0.1')
db_port = os.getenv('DB_PORT', '5432')
db_name = os.getenv('DB_NAME', 'smartspend_db')
db_user = os.getenv('DB_USER', 'postgres')
db_pass = os.getenv('DB_PASSWORD', '').strip('"')

conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_pass)
cur = conn.cursor()

USER_ID = 5  # abc@gmail.com

print("=" * 60)
print("PHASE 0 — DB STATE CHECK")
print("=" * 60)

# Check primary user
cur.execute("SELECT id, email, is_verified, onboarding_completed FROM users WHERE id=%s", (USER_ID,))
u = cur.fetchone()
print(f"\nPrimary user: id={u[0]} email={u[1]} verified={u[2]} onboarding={u[3]}")

# Transactions
cur.execute("SELECT COUNT(*), COUNT(CASE WHEN is_fraud=true THEN 1 END) FROM transactions WHERE user_id=%s", (USER_ID,))
r = cur.fetchone()
total_txns, fraud_txns = r[0], r[1]
print(f"\nTransactions: total={total_txns} fraud={fraud_txns}")

# Fraud alerts
cur.execute("SELECT COUNT(*), COALESCE(SUM(money_saved),0) FROM fraud_alerts WHERE user_id=%s", (USER_ID,))
r = cur.fetchone()
print(f"Fraud alerts: count={r[0]} money_saved=Rs {r[1]:,.0f}")

cur.execute("SELECT user_action, COUNT(*) FROM fraud_alerts WHERE user_id=%s GROUP BY user_action", (USER_ID,))
for row in cur.fetchall():
    print(f"  user_action={row[0]}: {row[1]}")

# Bank connections
cur.execute("SELECT bank_name FROM bank_connections WHERE user_id=%s", (USER_ID,))
banks = cur.fetchall()
print(f"\nBank connections for user 5: {[b[0] for b in banks]}")

# EMI records
cur.execute("""
    SELECT COUNT(*) FROM information_schema.tables WHERE table_name='emi_records'
""")
emi_exists = cur.fetchone()[0]
if emi_exists:
    cur.execute("SELECT COUNT(*) FROM emi_records WHERE user_id=%s", (USER_ID,))
    print(f"\nEMI records: {cur.fetchone()[0]}")
else:
    print("\nEMI records table: NOT FOUND")

# Subscriptions
cur.execute("""
    SELECT COUNT(*) FROM information_schema.tables WHERE table_name='subscriptions'
""")
subs_exists = cur.fetchone()[0]
if subs_exists:
    cur.execute("SELECT COUNT(*) FROM subscriptions WHERE user_id=%s", (USER_ID,))
    print(f"Subscriptions: {cur.fetchone()[0]}")
else:
    print("Subscriptions table: NOT FOUND")

# Purchase goals
cur.execute("""
    SELECT COUNT(*) FROM information_schema.tables WHERE table_name='purchase_goals'
""")
pg_exists = cur.fetchone()[0]
if pg_exists:
    cur.execute("SELECT COUNT(*) FROM purchase_goals WHERE user_id=%s", (USER_ID,))
    print(f"Purchase goals: {cur.fetchone()[0]}")

# Investigations
cur.execute("SELECT COUNT(*) FROM risk_investigations WHERE user_id=%s", (USER_ID,))
print(f"Investigations (all time): {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM risk_investigations WHERE started_at::date=CURRENT_DATE")
print(f"Investigations (today): {cur.fetchone()[0]}")

# Orchestration
cur.execute("SELECT COUNT(*) FROM orchestration_decisions WHERE created_at::date=CURRENT_DATE AND judge_invoked=true")
print(f"Phase 12 judge calls today: {cur.fetchone()[0]}")

print("\n" + "=" * 60)
print("SEEDING MISSING DATA")
print("=" * 60)

# 1. Seed EMIs if missing or count < 5
if emi_exists:
    cur.execute("SELECT COUNT(*) FROM emi_records WHERE user_id=%s AND status='active'", (USER_ID,))
    emi_count = cur.fetchone()[0]
else:
    emi_count = 0

if emi_count < 5:
    print(f"\nSeeding EMI records (have {emi_count}, need 5)...")
    # Check actual columns
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='emi_records' ORDER BY ordinal_position
    """)
    emi_cols = [r[0] for r in cur.fetchall()]
    print(f"  EMI columns: {emi_cols}")

    emis = [
        ("iPhone 15 Pro", 150000, 12, 13500, "HDFC Bank", 8),
        ("Home Loan EMI", 4500000, 240, 38000, "SBI", 45),
        ("Car Loan - Maruti Swift", 800000, 60, 15200, "ICICI Bank", 22),
        ("Laptop - Lenovo ThinkPad", 95000, 9, 11200, "Bajaj Finance", 3),
        ("Personal Loan", 200000, 24, 9500, "Axis Bank", 11),
    ]
    for item_name, principal, tenure, emi_amt, lender, months_paid in emis:
        try:
            if 'item_name' in emi_cols:
                cur.execute("""
                    INSERT INTO emi_records
                    (user_id, item_name, principal_amount, tenure_months, emi_amount, lender, months_paid, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', NOW())
                    ON CONFLICT DO NOTHING
                """, (USER_ID, item_name, principal, tenure, emi_amt, lender, months_paid))
            elif 'name' in emi_cols:
                cur.execute("""
                    INSERT INTO emi_records
                    (user_id, name, amount, tenure_months, monthly_amount, lender, months_paid, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', NOW())
                    ON CONFLICT DO NOTHING
                """, (USER_ID, item_name, principal, tenure, emi_amt, lender, months_paid))
        except Exception as e:
            print(f"  EMI insert failed: {e}")
            conn.rollback()
            break
    else:
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM emi_records WHERE user_id=%s", (USER_ID,))
        print(f"  EMI records after seed: {cur.fetchone()[0]}")

# 2. Seed subscriptions if missing
if subs_exists:
    cur.execute("SELECT COUNT(*) FROM subscriptions WHERE user_id=%s AND status='active'", (USER_ID,))
    subs_count = cur.fetchone()[0]
else:
    subs_count = 0

if subs_count < 5:
    print(f"\nSeeding subscriptions (have {subs_count}, need 7)...")
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='subscriptions' ORDER BY ordinal_position
    """)
    sub_cols = [r[0] for r in cur.fetchall()]
    print(f"  Sub columns: {sub_cols}")

    subs = [
        ("Netflix", 649, "monthly", "Entertainment", "2024-01-15"),
        ("Spotify", 119, "monthly", "Music", "2024-03-01"),
        ("Amazon Prime", 1499, "yearly", "Shopping", "2024-06-20"),
        ("Disney+ Hotstar", 899, "yearly", "Entertainment", "2024-02-10"),
        ("Gym Membership", 2500, "monthly", "Health", "2024-04-05"),
        ("iCloud 50GB", 75, "monthly", "Storage", "2023-12-01"),
        ("LinkedIn Premium", 2600, "monthly", "Professional", "2024-05-15"),
    ]
    name_col = 'service_name' if 'service_name' in sub_cols else 'name'
    for sname, amt, freq, cat, start in subs:
        try:
            cur.execute(f"""
                INSERT INTO subscriptions
                (user_id, {name_col}, amount, frequency, category, start_date, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'active', NOW())
                ON CONFLICT DO NOTHING
            """, (USER_ID, sname, amt, freq, cat, start))
        except Exception as e:
            print(f"  Sub insert failed: {e}")
            conn.rollback()
            break
    else:
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM subscriptions WHERE user_id=%s", (USER_ID,))
        print(f"  Subscriptions after seed: {cur.fetchone()[0]}")

# 3. Seed purchase goals if table exists and empty
if pg_exists:
    cur.execute("SELECT COUNT(*) FROM purchase_goals WHERE user_id=%s", (USER_ID,))
    pg_count = cur.fetchone()[0]
    if pg_count < 2:
        print(f"\nSeeding purchase goals...")
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='purchase_goals' ORDER BY ordinal_position
        """)
        pg_cols = [r[0] for r in cur.fetchall()]
        print(f"  Goal columns: {pg_cols}")
        goals = [
            ("New Smartphone", 80000, 6),
            ("Europe Vacation", 200000, 12),
            ("MacBook Pro", 150000, 8),
        ]
        for gname, target, months in goals:
            try:
                if 'target_amount' in pg_cols:
                    cur.execute("""
                        INSERT INTO purchase_goals (user_id, name, target_amount, target_months, created_at)
                        VALUES (%s, %s, %s, %s, NOW()) ON CONFLICT DO NOTHING
                    """, (USER_ID, gname, target, months))
                elif 'goal_amount' in pg_cols:
                    cur.execute("""
                        INSERT INTO purchase_goals (user_id, name, goal_amount, months, created_at)
                        VALUES (%s, %s, %s, %s, NOW()) ON CONFLICT DO NOTHING
                    """, (USER_ID, gname, target, months))
            except Exception as e:
                print(f"  Goal insert failed: {e}")
                conn.rollback()
                break
        else:
            conn.commit()
            cur.execute("SELECT COUNT(*) FROM purchase_goals WHERE user_id=%s", (USER_ID,))
            print(f"  Purchase goals after seed: {cur.fetchone()[0]}")

# 4. Ensure all fraud alerts have BLOCKED action and severity
cur.execute("""
    UPDATE fraud_alerts
    SET user_action = 'BLOCKED'
    WHERE user_id = %s AND user_action != 'BLOCKED'
""", (USER_ID,))
updated = cur.rowcount
if updated > 0:
    print(f"\nFixed {updated} alerts: set user_action='BLOCKED'")
    conn.commit()

# Final summary
print("\n" + "=" * 60)
print("FINAL STATE SUMMARY")
print("=" * 60)
cur.execute("SELECT COUNT(*), COUNT(CASE WHEN is_fraud=true THEN 1 END) FROM transactions WHERE user_id=%s", (USER_ID,))
r = cur.fetchone()
print(f"Transactions: {r[0]} total, {r[1]} fraud")

cur.execute("SELECT COUNT(*), COALESCE(SUM(money_saved),0) FROM fraud_alerts WHERE user_id=%s AND user_action='BLOCKED'", (USER_ID,))
r = cur.fetchone()
print(f"Fraud alerts BLOCKED: {r[0]}, Money saved: Rs {r[1]:,.0f}")

if emi_exists:
    cur.execute("SELECT COUNT(*) FROM emi_records WHERE user_id=%s", (USER_ID,))
    print(f"EMI records: {cur.fetchone()[0]}")

if subs_exists:
    cur.execute("SELECT COUNT(*) FROM subscriptions WHERE user_id=%s", (USER_ID,))
    print(f"Subscriptions: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM risk_investigations WHERE started_at::date=CURRENT_DATE")
print(f"Investigations today: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM orchestration_decisions WHERE created_at::date=CURRENT_DATE AND judge_invoked=true")
print(f"Phase 12 judge calls today: {cur.fetchone()[0]}")

print("\n[OK] Phase 0 complete")
conn.close()
