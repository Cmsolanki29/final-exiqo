"""Seed income (CREDIT) transactions so financial health score is realistic."""
import psycopg2
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv('../.env')
conn = psycopg2.connect(
    host=os.getenv('DB_HOST','127.0.0.1'), port=os.getenv('DB_PORT','5432'),
    dbname=os.getenv('DB_NAME','smartspend_db'), user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','').strip('"')
)
cur = conn.cursor()
USER_ID = 5

# Check transaction table columns
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name='transactions' ORDER BY ordinal_position
""")
cols = [r[0] for r in cur.fetchall()]
print("Transaction columns:", cols[:10], "...")

# Check existing credits
cur.execute("SELECT COUNT(*) FROM transactions WHERE user_id=%s AND type='CREDIT'", (USER_ID,))
existing = cur.fetchone()[0]
print(f"Existing CREDIT transactions: {existing}")

if existing >= 3:
    print("Already have enough income transactions. Skipping.")
else:
    # Seed 3 months of salary credits (₹85,000/month)
    now = datetime.now()
    salary_dates = [
        now.replace(day=1) - timedelta(days=90),  # ~3 months ago
        now.replace(day=1) - timedelta(days=60),  # ~2 months ago
        now.replace(day=1) - timedelta(days=30),  # ~1 month ago
    ]
    
    inserted = 0
    for sal_date in salary_dates:
        sal_date = sal_date.replace(hour=9, minute=0, second=0)
        try:
            if 'type' in cols and 'transaction_time' in cols:
                cur.execute("""
                    INSERT INTO transactions (user_id, amount, merchant, category, type, transaction_time, location, is_fraud, anomaly_score)
                    VALUES (%s, %s, %s, %s, 'CREDIT', %s, %s, false, 0.01)
                    ON CONFLICT DO NOTHING
                """, (USER_ID, 85000.00, 'NEFT-SALARY-EMPLOYER', 'Salary', sal_date, 'Mumbai'))
            elif 'type' in cols and 'transaction_date' in cols:
                cur.execute("""
                    INSERT INTO transactions (user_id, amount, merchant, category, type, transaction_date, location, is_fraud, anomaly_score)
                    VALUES (%s, %s, %s, %s, 'CREDIT', %s, %s, false, 0.01)
                    ON CONFLICT DO NOTHING
                """, (USER_ID, 85000.00, 'NEFT-SALARY-EMPLOYER', 'Salary', sal_date, 'Mumbai'))
            inserted += 1
        except Exception as e:
            print(f"  Salary insert failed: {e}")
            conn.rollback()
            break
    
    # Also seed some freelance/other income
    freelance_dates = [
        now - timedelta(days=75),
        now - timedelta(days=45),
        now - timedelta(days=15),
    ]
    for fd in freelance_dates:
        fd = fd.replace(hour=14, minute=30)
        try:
            if 'type' in cols and 'transaction_time' in cols:
                cur.execute("""
                    INSERT INTO transactions (user_id, amount, merchant, category, type, transaction_time, location, is_fraud, anomaly_score)
                    VALUES (%s, %s, %s, %s, 'CREDIT', %s, %s, false, 0.01)
                    ON CONFLICT DO NOTHING
                """, (USER_ID, 25000.00, 'CLIENT-PAYMENT-FREELANCE', 'Freelance', fd, 'Mumbai'))
            elif 'type' in cols and 'transaction_date' in cols:
                cur.execute("""
                    INSERT INTO transactions (user_id, amount, merchant, category, type, transaction_date, location, is_fraud, anomaly_score)
                    VALUES (%s, %s, %s, %s, 'CREDIT', %s, %s, false, 0.01)
                    ON CONFLICT DO NOTHING
                """, (USER_ID, 25000.00, 'CLIENT-PAYMENT-FREELANCE', 'Freelance', fd, 'Mumbai'))
            inserted += 1
        except Exception as e:
            print(f"  Freelance insert failed: {e}")
            conn.rollback()
            break
    
    conn.commit()
    print(f"Inserted {inserted} income transactions")

# Verify
cur.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM transactions WHERE user_id=%s AND type='CREDIT'", (USER_ID,))
r = cur.fetchone()
print(f"Total CREDIT transactions: {r[0]} | Total income: Rs {r[1]:,.0f}")

# Current month credits
cur.execute("""
    SELECT COALESCE(SUM(amount),0) FROM transactions
    WHERE user_id=%s AND type='CREDIT'
    AND EXTRACT(YEAR FROM COALESCE(transaction_time, transaction_date)) = EXTRACT(YEAR FROM NOW())
    AND EXTRACT(MONTH FROM COALESCE(transaction_time, transaction_date)) = EXTRACT(MONTH FROM NOW())
""", (USER_ID,))
this_month = cur.fetchone()[0]
print(f"Current month income: Rs {this_month:,.0f}")
print("[OK] Done")
conn.close()
