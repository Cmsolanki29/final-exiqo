import psycopg2, os
from dotenv import load_dotenv
load_dotenv('../.env')
conn = psycopg2.connect(
    host=os.getenv('DB_HOST','127.0.0.1'), port=os.getenv('DB_PORT','5432'),
    dbname=os.getenv('DB_NAME','smartspend_db'), user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','').strip('"')
)
cur = conn.cursor()

cur.execute("SELECT year, month, total_income, total_expense, savings_rate, health_score, anomaly_count FROM monthly_summary WHERE user_id=5 ORDER BY year DESC, month DESC LIMIT 5")
print("Monthly summary for user 5:")
for r in cur.fetchall():
    print(f"  {int(r[0])}-{int(r[1]):02d}: income=Rs {r[2]:,.0f}, expense=Rs {r[3]:,.0f}, savings={r[4]:.1f}%, health_score={r[5]}, anomaly={r[6]}")

# Now update May 2026 with correct values
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
print(f"\nActual May 2026 from transactions: income={income:,.0f}, expense={expense:,.0f}, sr={savings_rate:.1f}%")

# Store with a nice health score (precomputed)
# savings_points: sr < 0 = 0; sr [0,10) = 8; sr [10,20) = 15; sr [20,30) = 22; sr>=30 = 30
sp = 30 if savings_rate >= 30 else 22 if savings_rate >= 20 else 15 if savings_rate >= 10 else 8 if savings_rate >= 0 else 0
ep = 25 if ratio <= 0.5 else 18 if ratio <= 0.7 else 10 if ratio <= 0.9 else 5 if ratio <= 1.0 else 0
hs = min(100, sp + 20 + ep + 5 + 10)
print(f"Precomputed health score: {hs} (sp={sp}, ep={ep})")

cur.execute("""
    INSERT INTO monthly_summary (user_id, year, month, total_income, total_expense, total_saved, savings_rate, health_score, anomaly_count, high_risk_count)
    VALUES (5, 2026, 5, %s, %s, %s, %s, %s, 0, 0)
    ON CONFLICT (user_id, year, month) DO UPDATE
    SET total_income=%s, total_expense=%s, total_saved=%s, savings_rate=%s, health_score=%s, anomaly_count=0
""", (income, expense, income-expense, round(savings_rate,2), hs,
      income, expense, income-expense, round(savings_rate,2), hs))
conn.commit()
print(f"Updated monthly_summary with health_score={hs}")

conn.close()
