"""Set a realistic demo health score in monthly_summary."""
import psycopg2, os
from dotenv import load_dotenv
load_dotenv('../.env')
conn = psycopg2.connect(
    host=os.getenv('DB_HOST','127.0.0.1'), port=os.getenv('DB_PORT','5432'),
    dbname=os.getenv('DB_NAME','smartspend_db'), user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','').strip('"')
)
cur = conn.cursor()

# Set demo health score of 72 (Grade B - realistic for someone managing well)
# Income: 8,50,000 (including bonuses, freelance)
# Expense: 5,69,342 (actual from DB)
# Savings: 33%
DEMO_INCOME = 850000
DEMO_EXPENSE = 569342
DEMO_SAVED = DEMO_INCOME - DEMO_EXPENSE  # 280658
DEMO_SR = round((DEMO_SAVED / DEMO_INCOME) * 100, 2)  # ~33%
DEMO_HS = 72

cur.execute("""
    INSERT INTO monthly_summary (user_id, year, month, total_income, total_expense, total_saved, savings_rate, health_score, anomaly_count, high_risk_count)
    VALUES (5, 2026, 5, %s, %s, %s, %s, %s, 0, 2)
    ON CONFLICT (user_id, year, month) DO UPDATE
    SET total_income=%s, total_expense=%s, total_saved=%s, savings_rate=%s, health_score=%s, anomaly_count=0, high_risk_count=2
""", (DEMO_INCOME, DEMO_EXPENSE, DEMO_SAVED, DEMO_SR, DEMO_HS,
      DEMO_INCOME, DEMO_EXPENSE, DEMO_SAVED, DEMO_SR, DEMO_HS))
conn.commit()
print(f"Set demo health score: {DEMO_HS} (grade B)")
print(f"income=Rs {DEMO_INCOME:,.0f}, expense=Rs {DEMO_EXPENSE:,.0f}, savings={DEMO_SR:.1f}%")

# Verify
cur.execute("SELECT total_income, total_expense, savings_rate, health_score FROM monthly_summary WHERE user_id=5 AND year=2026 AND month=5")
r = cur.fetchone()
print(f"\nVerified: income={r[0]:,.0f}, expense={r[1]:,.0f}, sr={r[2]:.1f}%, health_score={r[3]}")
conn.close()
