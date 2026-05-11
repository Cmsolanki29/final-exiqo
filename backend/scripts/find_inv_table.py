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

cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name
""")
tables = [r[0] for r in cur.fetchall()]
print("All tables:", tables)

# Find investigation-related tables
inv_tables = [t for t in tables if 'invest' in t or 'phase_9' in t or 'llm' in t or 'agent' in t or 'verdict' in t]
print("\nInvestigation-related:", inv_tables)

# Check counts in all relevant tables
for t in inv_tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    print(f"  {t}: {cur.fetchone()[0]} rows")

# Also check orchestration table
if 'orchestration_decisions' in tables:
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='orchestration_decisions' ORDER BY ordinal_position
    """)
    cols = [r[0] for r in cur.fetchall()]
    print("\norchestration_decisions columns:", cols)

conn.close()
