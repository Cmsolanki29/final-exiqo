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

# Get columns
cur.execute("""
    SELECT column_name, data_type FROM information_schema.columns
    WHERE table_name = 'risk_investigations'
    ORDER BY ordinal_position
""")
cols = cur.fetchall()
print("risk_investigations columns:")
for c in cols:
    print(f"  {c[0]}: {c[1]}")

# Sample rows
cur.execute("SELECT * FROM risk_investigations LIMIT 2")
rows = cur.fetchall()
if rows:
    print(f"\nSample row: {rows[0]}")

# Count by user_id
cur.execute("SELECT user_id, COUNT(*) FROM risk_investigations GROUP BY user_id")
for r in cur.fetchall():
    print(f"\nUser {r[0]}: {r[1]} investigations")

# How costs/today counts phase_9
cur.execute("""
    SELECT COUNT(*) FROM risk_investigations
    WHERE DATE(created_at) = CURRENT_DATE
""")
print(f"\nInvestigations today: {cur.fetchone()[0]}")

conn.close()
