"""Quick schema inspection + bank linking test script."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

import psycopg2

DB = dict(
    host=os.getenv("DB_HOST", "127.0.0.1"),
    port=os.getenv("DB_PORT", "5432"),
    dbname=os.getenv("DB_NAME", "smartspend_db"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", ""),
)

conn = psycopg2.connect(**DB)
cur = conn.cursor()

print("=== users columns ===")
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='users' ORDER BY ordinal_position")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\n=== fraud_alerts columns ===")
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='fraud_alerts' ORDER BY ordinal_position")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\n=== bank_connections columns ===")
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='bank_connections' ORDER BY ordinal_position")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\n=== Current users ===")
cur.execute("SELECT id, name, email, onboarding_completed FROM users ORDER BY id")
for row in cur.fetchall():
    print(f"  id={row[0]}, name={row[1]}, email={row[2]}, onboarding={row[3]}")

print("\n=== Bank connections ===")
cur.execute("SELECT user_id, bank_name, connection_status FROM bank_connections ORDER BY user_id")
for row in cur.fetchall():
    print(f"  user_id={row[0]}, bank={row[1]}, status={row[2]}")

print("\n=== fraud_alerts count and severity check ===")
cur.execute("SELECT COUNT(*), MAX(user_action) FROM fraud_alerts WHERE user_id=1")
row = cur.fetchone()
print(f"  total alerts for user 1: {row[0]}, sample action: {row[1]}")

# Check if severity column exists
cur.execute("SELECT COUNT(*) FROM information_schema.columns WHERE table_name='fraud_alerts' AND column_name='severity'")
has_severity = cur.fetchone()[0] > 0
print(f"  severity column exists: {has_severity}")

cur.close()
conn.close()
print("\nDone.")
