import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('../.env')
db_url = os.getenv('DATABASE_URL', '').replace('postgresql+asyncpg', 'postgresql').replace('postgresql+psycopg2', 'postgresql')
conn = psycopg2.connect(db_url)
cur = conn.cursor()

# Check table structure
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name='orchestration_decisions' 
    ORDER BY ordinal_position
""")
rows = cur.fetchall()
print('orchestration_decisions columns:')
for r in rows:
    print(r)

cur.execute('SELECT COUNT(*) FROM orchestration_decisions')
print('Row count:', cur.fetchone())

cur.execute('SELECT id, tier, risk_score, created_at FROM orchestration_decisions ORDER BY created_at DESC LIMIT 5')
for r in cur.fetchall():
    print(r)

conn.close()
