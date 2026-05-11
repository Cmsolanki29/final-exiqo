"""Fix user_action in seeded fraud_alerts to 'BLOCKED' so threats_blocked shows 47."""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")
import psycopg2

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "127.0.0.1"),
    port=os.getenv("DB_PORT", "5432"),
    dbname=os.getenv("DB_NAME", "smartspend_db"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", ""),
)
cur = conn.cursor()

# Check valid user_action values
cur.execute("SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid WHERE t.relname='fraud_alerts' AND c.contype='c'")
print("Constraints:", [r[0] for r in cur.fetchall()])

cur.execute("SELECT DISTINCT user_action FROM fraud_alerts WHERE user_id=5")
print("Current user_action values:", [r[0] for r in cur.fetchall()])

# Update all seeded fraud alerts (RESOLVED/PENDING) to BLOCKED
cur.execute("UPDATE fraud_alerts SET user_action='BLOCKED' WHERE user_id=5 AND user_action IN ('RESOLVED', 'PENDING')")
updated = cur.rowcount
conn.commit()
print(f"Updated {updated} alerts to BLOCKED")

# Verify
cur.execute("SELECT COUNT(*) FROM fraud_alerts WHERE user_id=5 AND user_action='BLOCKED'")
blocked = cur.fetchone()[0]
print(f"Threats blocked after fix: {blocked}")

cur.close(); conn.close()
print("Done.")
