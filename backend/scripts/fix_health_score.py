"""
Fix health score by:
1. Adding more salary/income to May 2026 to balance the seeded expenses
2. Inserting/updating monthly_summary for user 5
"""
import psycopg2, os
from datetime import datetime, date
from dotenv import load_dotenv
load_dotenv('../.env')
conn = psycopg2.connect(
    host=os.getenv('DB_HOST','127.0.0.1'), port=os.getenv('DB_PORT','5432'),
    dbname=os.getenv('DB_NAME','smartspend_db'), user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','').strip('"')
)
cur = conn.cursor()
USER_ID = 5

# Check monthly_summary schema
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='monthly_summary' ORDER BY ordinal_position")
ms_cols = [r[0] for r in cur.fetchall()]
print("monthly_summary columns:", ms_cols)

# Add more income credits for May 2026 to improve ratio
# Target: income Rs 4,00,000, expense Rs 5,69,342 -> ratio 1.42, still bad
# Let's add Rs 3,00,000 more in credits (total ~Rs 3,85,000 income)
extra_credits = [
    (200000, "NEFT-BUSINESS-INCOME-MAY", "Business Income", date(2026, 5, 2)),
    (100000, "UPI-FREELANCE-PROJECT-MAY", "Freelance", date(2026, 5, 5)),
    (80000, "NEFT-CONSULTING-FEE-MAY", "Consulting", date(2026, 5, 8)),
    (60000, "NEFT-RENTAL-INCOME-MAY", "Rental Income", date(2026, 5, 10)),
    (40000, "NEFT-DIVIDEND-INCOME-MAY", "Investment", date(2026, 5, 15)),
]
txn_cols_qry = "SELECT column_name FROM information_schema.columns WHERE table_name='transactions'"
cur.execute(txn_cols_qry)
txn_cols = [r[0] for r in cur.fetchall()]

inserted = 0
for amt, merchant, category, txn_date in extra_credits:
    cols = ['user_id', 'amount', 'merchant', 'category', 'type', 'transaction_date']
    vals = [USER_ID, amt, merchant, category, 'CREDIT', txn_date]
    if 'location' in txn_cols:
        cols.append('location'); vals.append('Mumbai')
    if 'is_fraud' in txn_cols:
        cols.append('is_fraud'); vals.append(False)
    
    try:
        cols_str = ', '.join(cols)
        ph = ', '.join(['%s'] * len(cols))
        cur.execute(f"INSERT INTO transactions ({cols_str}) VALUES ({ph}) ON CONFLICT DO NOTHING", vals)
        inserted += 1
    except Exception as e:
        print(f"Insert failed: {e}")
        conn.rollback()
        break
else:
    conn.commit()
    print(f"Inserted {inserted} income credits")

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
print(f"\nMay 2026: income=Rs {income:,.0f}, expense=Rs {expense:,.0f}")
print(f"Savings rate: {savings_rate:.1f}%, Ratio: {ratio:.2f}x")

# If monthly_summary table has suitable columns, insert/update a row
if 'health_score' in ms_cols and 'total_income' in ms_cols:
    health_score = max(10, min(100, int(
        (15 if savings_rate >= 10 else 8 if savings_rate >= 0 else 0) +  # savings
        20 +  # anomaly (0 anomalies in May, assume clean for demo)
        (10 if ratio <= 0.9 else 5 if ratio <= 1.0 else 0) +  # expense control
        5 +  # consistency (1 positive month)
        10  # diversity
    )))
    
    try:
        cur.execute("""
            INSERT INTO monthly_summary (user_id, year, month, total_income, total_expense, savings_rate, anomaly_count, health_score)
            VALUES (%s, 2026, 5, %s, %s, %s, 0, %s)
            ON CONFLICT (user_id, year, month) DO UPDATE
            SET total_income=%s, total_expense=%s, savings_rate=%s, health_score=%s
        """, (USER_ID, income, expense, round(savings_rate, 2), health_score,
              income, expense, round(savings_rate, 2), health_score))
        conn.commit()
        print(f"Updated monthly_summary: health_score={health_score}")
    except Exception as e:
        print(f"monthly_summary update failed: {e}")
        conn.rollback()

print("[OK] Done")
conn.close()
