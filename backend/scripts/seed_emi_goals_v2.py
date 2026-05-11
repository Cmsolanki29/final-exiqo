"""Seed EMI records and purchase goals with actual schema."""
import psycopg2
from datetime import datetime, timedelta
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

# EMI records schema:
# id, user_id, merchant, detected_amount, payment_date, category, emi_type, months_detected, is_active, first_detected, last_detected
emi_data = [
    ("HDFC Bank EMI", 13500, "Loan", "recurring", 12, datetime.now() - timedelta(days=240), datetime.now() - timedelta(days=30)),
    ("SBI Home Loan", 38000, "Home Loan", "recurring", 45, datetime.now() - timedelta(days=1350), datetime.now() - timedelta(days=30)),
    ("ICICI Car Loan", 15200, "Car Loan", "recurring", 22, datetime.now() - timedelta(days=660), datetime.now() - timedelta(days=30)),
    ("Bajaj Finance", 11200, "Electronics", "recurring", 3, datetime.now() - timedelta(days=90), datetime.now() - timedelta(days=30)),
    ("Axis Bank Personal", 9500, "Personal Loan", "recurring", 11, datetime.now() - timedelta(days=330), datetime.now() - timedelta(days=30)),
]
print("Seeding EMI records...")
for merchant, amount, category, emi_type, months, first_det, last_det in emi_data:
    try:
        cur.execute("""
            INSERT INTO emi_records (user_id, merchant, detected_amount, category, emi_type, months_detected, is_active, first_detected, last_detected, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,true,%s,%s,NOW()) ON CONFLICT DO NOTHING
        """, (USER_ID, merchant, amount, category, emi_type, months, first_det, last_det))
    except Exception as e:
        print(f"  EMI insert failed: {e}")
        conn.rollback()
        break
else:
    conn.commit()

cur.execute("SELECT COUNT(*) FROM emi_records WHERE user_id=%s", (USER_ID,))
print(f"EMI records after seed: {cur.fetchone()[0]}")

# Purchase goals schema:
# id, user_id, item_name, target_amount, saved_amount, target_date, monthly_target, category, priority, status, best_buy_month, emi_vs_cash, sacrifice_plan
goals_data = [
    ("New Smartphone (iPhone 16)", 85000, 18000, datetime.now() + timedelta(days=180), 12000, "Electronics", "HIGH", "active"),
    ("Europe Vacation", 200000, 35000, datetime.now() + timedelta(days=365), 15000, "Travel", "MEDIUM", "active"),
    ("MacBook Pro M4", 150000, 45000, datetime.now() + timedelta(days=240), 18000, "Electronics", "HIGH", "active"),
]
print("\nSeeding purchase goals...")
for item_name, target, saved, target_date, monthly, category, priority, status in goals_data:
    try:
        cur.execute("""
            INSERT INTO purchase_goals (user_id, item_name, target_amount, saved_amount, target_date, monthly_target, category, priority, status, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW()) ON CONFLICT DO NOTHING
        """, (USER_ID, item_name, target, saved, target_date, monthly, category, priority, status))
    except Exception as e:
        print(f"  Goal insert failed: {e}")
        conn.rollback()
        break
else:
    conn.commit()

cur.execute("SELECT COUNT(*) FROM purchase_goals WHERE user_id=%s", (USER_ID,))
print(f"Purchase goals after seed: {cur.fetchone()[0]}")

# Final check
print("\n=== FINAL STATE ===")
for table, label in [('transactions', 'Transactions'), ('fraud_alerts', 'Fraud alerts'), ('emi_records', 'EMI records'), ('subscriptions', 'Subscriptions'), ('purchase_goals', 'Purchase goals')]:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id=%s", (USER_ID,))
        print(f"  {label}: {cur.fetchone()[0]}")
    except Exception as e:
        print(f"  {label}: error ({e})")

conn.close()
print("[OK] Done")
