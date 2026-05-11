"""Final report compilation for Session 2."""
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

print("=" * 70)
print("SESSION 2 COMPLETION REPORT")
print("=" * 70)

print("\n--- BANK LINKING (test_bank_user_001 = banktest@fraudshield.dev) ---")
cur.execute("""
    SELECT bc.bank_name, bc.account_masked, bc.created_at
    FROM bank_connections bc
    JOIN users u ON u.id = bc.user_id
    WHERE u.email = 'banktest@fraudshield.dev'
    ORDER BY bc.created_at
""")
rows = cur.fetchall()
print(f"Banks linked: {len(rows)}")
for r in rows:
    print(f"  - {r[0]}: {r[1]} (linked at {r[2]})")

print("\n--- DEMO NUMBERS ---")
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(money_saved), 0)
    FROM fraud_alerts
    WHERE user_id = 5 AND user_action = 'BLOCKED'
""")
r = cur.fetchone()
print(f"  Threats Blocked: {r[0]}")
print(f"  Money Saved (from alerts): Rs {r[1]:,.2f}")

cur.execute("SELECT COUNT(*) FROM transactions WHERE user_id=5 AND is_fraud=true")
fraud_txns = cur.fetchone()[0]
print(f"  Confirmed Fraud Transactions: {fraud_txns}")

cur.execute("SELECT COUNT(*) FROM transactions WHERE user_id=5")
total_txns = cur.fetchone()[0]
print(f"  Total Transactions: {total_txns}")

print("\n--- MODEL STATUS ---")
cur.execute("""
    SELECT EXISTS(
        SELECT 1 FROM information_schema.tables
        WHERE table_name='orchestration_decisions'
    )
""")
print(f"  orchestration_decisions table exists: {cur.fetchone()[0]}")

cur.execute("""
    SELECT COUNT(*) FROM orchestration_decisions
    WHERE tier = 'tier_4_llm_agent'
    AND created_at >= CURRENT_DATE
""")
tier4_today = cur.fetchone()[0]
print(f"  Tier-4 decisions today: {tier4_today}")

cur.execute("""
    SELECT COUNT(*) FROM orchestration_decisions
    WHERE judge_invoked = true
    AND created_at >= CURRENT_DATE
""")
judge_today = cur.fetchone()[0]
print(f"  Phase 12 Judge calls today: {judge_today}")

print("\n--- SEVERITY FILTER ---")
cur.execute("""
    SELECT severity, COUNT(*)
    FROM fraud_alerts
    WHERE user_id = 5
    GROUP BY severity
    ORDER BY COUNT(*) DESC
""")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]} alerts")

print("\n--- USERS ---")
cur.execute("SELECT id, email, is_verified, onboarding_completed FROM users ORDER BY id")
for r in cur.fetchall():
    print(f"  id={r[0]} email={r[1]} verified={r[2]} onboarding={r[3]}")

conn.close()
print("\n" + "=" * 70)
