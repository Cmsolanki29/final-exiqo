"""Seed EMI records and purchase goals after inspecting actual schema."""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('../.env')
db_host = os.getenv('DB_HOST', '127.0.0.1')
db_port = os.getenv('DB_PORT', '5432')
db_name = os.getenv('DB_NAME', 'smartspend_db')
db_user = os.getenv('DB_USER', 'postgres')
db_pass = os.getenv('DB_PASSWORD', '').strip('"')
conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_pass)
cur = conn.cursor()
USER_ID = 5

# --- EMI records ---
cur.execute("""
    SELECT column_name, data_type FROM information_schema.columns
    WHERE table_name='emi_records' ORDER BY ordinal_position
""")
emi_cols = {r[0]: r[1] for r in cur.fetchall()}
print("EMI columns:", list(emi_cols.keys()))

cur.execute("SELECT COUNT(*) FROM emi_records WHERE user_id=%s", (USER_ID,))
emi_count = cur.fetchone()[0]
print(f"Existing EMIs: {emi_count}")

if emi_count < 5:
    emis = [
        ("iPhone 15 Pro", 150000, 12, 13500, "HDFC Bank", 8, 4),
        ("Home Loan", 4500000, 240, 38000, "SBI", 45, 195),
        ("Car Loan - Maruti Swift", 800000, 60, 15200, "ICICI Bank", 22, 38),
        ("Laptop - Lenovo", 95000, 9, 11200, "Bajaj Finance", 3, 6),
        ("Personal Loan", 200000, 24, 9500, "Axis Bank", 11, 13),
    ]
    col_names = list(emi_cols.keys())
    inserted = 0
    for item_name, principal, tenure, emi_amt, lender, months_paid, remaining in emis:
        try:
            if 'item_name' in col_names and 'months_remaining' in col_names:
                cur.execute("""
                    INSERT INTO emi_records
                    (user_id, item_name, principal_amount, tenure_months, emi_amount, lender, months_paid, months_remaining, start_date)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW()) ON CONFLICT DO NOTHING
                """, (USER_ID, item_name, principal, tenure, emi_amt, lender, months_paid, remaining))
            elif 'item_name' in col_names:
                cur.execute("""
                    INSERT INTO emi_records
                    (user_id, item_name, principal_amount, tenure_months, emi_amount, lender, months_paid, start_date)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,NOW()) ON CONFLICT DO NOTHING
                """, (USER_ID, item_name, principal, tenure, emi_amt, lender, months_paid))
            elif 'name' in col_names:
                cur.execute("""
                    INSERT INTO emi_records
                    (user_id, name, principal_amount, tenure_months, emi_amount, lender, months_paid, start_date)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,NOW()) ON CONFLICT DO NOTHING
                """, (USER_ID, item_name, principal, tenure, emi_amt, lender, months_paid))
            inserted += 1
        except Exception as e:
            print(f"  EMI failed: {e}")
            conn.rollback()
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM emi_records WHERE user_id=%s", (USER_ID,))
    print(f"EMIs after seed: {cur.fetchone()[0]}")

# --- Purchase goals ---
cur.execute("""
    SELECT column_name, data_type FROM information_schema.columns
    WHERE table_name='purchase_goals' ORDER BY ordinal_position
""")
pg_cols = {r[0]: r[1] for r in cur.fetchall()}
print("\nPurchase goal columns:", list(pg_cols.keys()))

cur.execute("SELECT COUNT(*) FROM purchase_goals WHERE user_id=%s", (USER_ID,))
pg_count = cur.fetchone()[0]
print(f"Existing purchase goals: {pg_count}")

if pg_count < 3:
    goals = [
        ("New Smartphone", 80000, 6, 15000),
        ("Europe Vacation", 200000, 12, 20000),
        ("MacBook Pro", 150000, 8, 25000),
    ]
    col_names = list(pg_cols.keys())
    for gname, target, months, saved in goals:
        try:
            if 'target_amount' in col_names and 'saved_amount' in col_names and 'target_months' in col_names:
                cur.execute("""
                    INSERT INTO purchase_goals (user_id, name, target_amount, saved_amount, target_months, created_at)
                    VALUES (%s,%s,%s,%s,%s,NOW()) ON CONFLICT DO NOTHING
                """, (USER_ID, gname, target, saved, months))
            elif 'target_amount' in col_names and 'target_months' in col_names:
                cur.execute("""
                    INSERT INTO purchase_goals (user_id, name, target_amount, target_months, created_at)
                    VALUES (%s,%s,%s,%s,NOW()) ON CONFLICT DO NOTHING
                """, (USER_ID, gname, target, months))
            elif 'goal_amount' in col_names:
                cur.execute("""
                    INSERT INTO purchase_goals (user_id, name, goal_amount, created_at)
                    VALUES (%s,%s,%s,NOW()) ON CONFLICT DO NOTHING
                """, (USER_ID, gname, target))
        except Exception as e:
            print(f"  Goal failed: {e}")
            conn.rollback()
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM purchase_goals WHERE user_id=%s", (USER_ID,))
    print(f"Purchase goals after seed: {cur.fetchone()[0]}")

# --- Verify final state ---
print("\n=== FINAL STATE ===")
cur.execute("SELECT COUNT(*) FROM transactions WHERE user_id=%s", (USER_ID,))
print(f"Transactions: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM fraud_alerts WHERE user_id=%s AND user_action='BLOCKED'", (USER_ID,))
print(f"Fraud alerts BLOCKED: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM emi_records WHERE user_id=%s", (USER_ID,))
print(f"EMI records: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM subscriptions WHERE user_id=%s", (USER_ID,))
print(f"Subscriptions: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM purchase_goals WHERE user_id=%s", (USER_ID,))
print(f"Purchase goals: {cur.fetchone()[0]}")
print("\n[OK] Done")
conn.close()
