"""Check what the stats computation yields with direct DB access."""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")
import psycopg2
from datetime import date

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "127.0.0.1"),
    port=os.getenv("DB_PORT", "5432"),
    dbname=os.getenv("DB_NAME", "smartspend_db"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", ""),
)
cur = conn.cursor()
user_id = 5  # abc@gmail.com

cur.execute("SELECT COUNT(*) FROM fraud_alerts WHERE user_id = %s;", (user_id,))
attempts = int(cur.fetchone()[0] or 0)
print(f"attempts (total alerts): {attempts}")

cur.execute("SELECT COALESCE(SUM(money_saved), 0) FROM fraud_alerts WHERE user_id = %s;", (user_id,))
money_saved_total = float(cur.fetchone()[0] or 0)
print(f"money_saved_total: {money_saved_total:,.2f}")

cur.execute("SELECT COUNT(*) FROM fraud_alerts WHERE user_id = %s AND user_action = 'BLOCKED';", (user_id,))
threats_blocked = int(cur.fetchone()[0] or 0)
print(f"threats_blocked (BLOCKED): {threats_blocked}")

cur.execute("SELECT COALESCE(SUM(amount_at_risk), 0) FROM fraud_alerts WHERE user_id = %s AND user_action = 'ALLOWED';", (user_id,))
money_lost_total = float(cur.fetchone()[0] or 0)
print(f"money_lost_total: {money_lost_total:,.2f}")

cur.execute("SELECT COALESCE(MAX(risk_score), 0) FROM fraud_alerts WHERE user_id = %s;", (user_id,))
max_risk = int(cur.fetchone()[0] or 0)
print(f"max_risk: {max_risk}")

# New formula
if attempts > 0:
    detection_rate = threats_blocked / attempts
    safety_score = min(99, int(detection_rate * 96 - (2 if money_lost_total > 0 else 0)))
else:
    safety_score = max(0, min(100, 100 - max_risk // 2 - (5 if attempts > 3 else 0)))

print(f"safety_score (new formula): {safety_score}")

# Old formula
old_safety = max(0, min(100, 100 - max_risk // 2 - (5 if attempts > 3 else 0)))
print(f"safety_score (old formula): {old_safety}")

# Severity distribution
cur.execute("SELECT severity, COUNT(*) FROM fraud_alerts WHERE user_id=%s GROUP BY severity", (user_id,))
print("\nSeverity distribution:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

cur.close(); conn.close()
