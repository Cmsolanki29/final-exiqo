"""Add income credits to May 2026 and update monthly_summary for a better health score."""
import psycopg2, os
from datetime import datetime, date, time
from dotenv import load_dotenv
load_dotenv('../.env')
conn = psycopg2.connect(
    host=os.getenv('DB_HOST','127.0.0.1'), port=os.getenv('DB_PORT','5432'),
    dbname=os.getenv('DB_NAME','smartspend_db'), user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','').strip('"')
)
cur = conn.cursor()
USER_ID = 5

extra_credits = [
    (200000, "NEFT-BUSINESS-INCOME", "Business Income", date(2026, 5, 2)),
    (100000, "FREELANCE-PROJECT-MAY", "Freelance", date(2026, 5, 5)),
    (80000, "CONSULTING-FEE-MAY", "Consulting", date(2026, 5, 8)),
    (60000, "RENTAL-INCOME-MAY", "Rental Income", date(2026, 5, 10)),
    (40000, "DIVIDEND-INCOME-MAY", "Investment", date(2026, 5, 15)),
]

inserted = 0
for amt, merchant, category, txn_date in extra_credits:
    txn_time = datetime(txn_date.year, txn_date.month, txn_date.day, 9, 0, 0)
    try:
        cur.execute("""
            INSERT INTO transactions 
            (user_id, amount, merchant, category, type, transaction_date, transaction_time, location, is_fraud)
            VALUES (%s, %s, %s, %s, 'CREDIT', %s, %s, 'Mumbai', false)
            ON CONFLICT DO NOTHING
        """, (USER_ID, amt, merchant, category, txn_date, txn_time))
        inserted += 1
    except Exception as e:
        print(f"Insert failed: {e}")
        conn.rollback()
        break
else:
    conn.commit()
    print(f"Inserted {inserted} income credits for May 2026")

# Verify new totals
cur.execute("""
    SELECT 
        COALESCE(SUM(CASE WHEN type = 'CREDIT' THEN amount ELSE 0 END),0) AS income,
        COALESCE(SUM(CASE WHEN type = 'DEBIT' THEN amount ELSE 0 END),0) AS expense
    FROM transactions
    WHERE user_id=5 AND EXTRACT(MONTH FROM transaction_date)::int=5 AND EXTRACT(YEAR FROM transaction_date)::int=2026
""")
r = cur.fetchone()
income, expense = float(r[0]), float(r[1])
savings_rate = (income - expense) / income * 100 if income > 0 else 0
ratio = expense / income if income > 0 else 2.0
print(f"May 2026: income=Rs {income:,.0f}, expense=Rs {expense:,.0f}")
print(f"Savings rate: {savings_rate:.1f}%, Expense/Income ratio: {ratio:.2f}x")

# Update monthly_summary with pre-computed health score
# Scoring: savings(0-30), anomaly(20), expense(0-25), consistency(0-15), diversity(10)
if savings_rate >= 10:
    sp = 15
elif savings_rate >= 0:
    sp = 8
else:
    sp = 0
ap = 20  # assume 0 anomalies for this pre-computed row
if ratio <= 0.9: ep = 25
elif ratio <= 1.0: ep = 10
elif ratio <= 1.2: ep = 5
else: ep = 0
cp = 5  # 1 positive month
dp = 10
hs = min(100, sp + ap + ep + cp + dp)
print(f"Calculated health score: {hs} (sp={sp} ap={ap} ep={ep} cp={cp} dp={dp})")

try:
    cur.execute("""
        INSERT INTO monthly_summary (user_id, year, month, total_income, total_expense, total_saved, savings_rate, health_score, anomaly_count)
        VALUES (%s, 2026, 5, %s, %s, %s, %s, %s, 0)
        ON CONFLICT (user_id, year, month) DO UPDATE
        SET total_income=%s, total_expense=%s, total_saved=%s, savings_rate=%s, health_score=%s, anomaly_count=0
    """, (USER_ID, income, expense, income-expense, round(savings_rate,2), hs,
          income, expense, income-expense, round(savings_rate,2), hs))
    conn.commit()
    print(f"Updated monthly_summary with health_score={hs}")
except Exception as e:
    print(f"monthly_summary update failed: {e}")
    conn.rollback()

print("[OK] Done")
conn.close()
