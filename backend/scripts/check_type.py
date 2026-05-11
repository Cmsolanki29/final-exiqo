import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")
import psycopg2

conn = psycopg2.connect(
    host=os.getenv("DB_HOST","127.0.0.1"),
    port=os.getenv("DB_PORT","5432"),
    dbname=os.getenv("DB_NAME","smartspend_db"),
    user=os.getenv("DB_USER","postgres"),
    password=os.getenv("DB_PASSWORD",""),
)
cur = conn.cursor()
cur.execute("""
    SELECT pg_get_constraintdef(c.oid)
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    WHERE t.relname = 'transactions' AND c.contype = 'c'
""")
for r in cur.fetchall():
    print(r[0])
# Also get a sample row to see actual type values
cur.execute("SELECT DISTINCT type FROM transactions WHERE user_id=5 LIMIT 10")
print("Existing type values:", [r[0] for r in cur.fetchall()])
cur.close(); conn.close()
