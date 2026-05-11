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

print("All bank connections:")
cur.execute("""
    SELECT u.email, bc.bank_name, bc.account_masked, bc.created_at
    FROM bank_connections bc
    JOIN users u ON u.id = bc.user_id
    ORDER BY u.email, bc.created_at
""")
for r in cur.fetchall():
    print(f"  {r[0]:40s} | {r[1]:15s} | {r[2]} | {r[3]}")

print("\nTotal bank connections by user:")
cur.execute("""
    SELECT u.email, COUNT(bc.id) as cnt
    FROM users u
    LEFT JOIN bank_connections bc ON bc.user_id = u.id
    GROUP BY u.email
    HAVING COUNT(bc.id) > 0
    ORDER BY cnt DESC
""")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]} banks")

conn.close()
