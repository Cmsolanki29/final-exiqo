import psycopg2, os
from dotenv import load_dotenv
load_dotenv('../.env')
conn = psycopg2.connect(
    host=os.getenv('DB_HOST','127.0.0.1'), port=os.getenv('DB_PORT','5432'),
    dbname=os.getenv('DB_NAME','smartspend_db'), user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','').strip('"')
)
cur = conn.cursor()

cur.execute("""
    SELECT type, COUNT(*), SUM(amount) FROM transactions
    WHERE user_id=5 AND EXTRACT(YEAR FROM transaction_date)=2026 AND EXTRACT(MONTH FROM transaction_date)=5
    GROUP BY type ORDER BY 2 DESC
""")
print("May 2026 transaction types:")
for r in cur.fetchall():
    print(f"  type={r[0]} count={r[1]} total=Rs {r[2]:,.0f}")

cur.execute("""
    SELECT 
        COALESCE(SUM(CASE WHEN type = 'CREDIT' THEN amount ELSE 0 END),0) AS income,
        COALESCE(SUM(CASE WHEN type = 'DEBIT' THEN amount ELSE 0 END),0) AS expense
    FROM transactions
    WHERE user_id=5 AND EXTRACT(MONTH FROM transaction_date)::int=5 AND EXTRACT(YEAR FROM transaction_date)::int=2026
""")
r = cur.fetchone()
print(f"\nScorer (CREDIT/DEBIT types): income=Rs {r[0]:,.0f}, expense=Rs {r[1]:,.0f}")

# Check transaction summary endpoint logic
cur.execute("""
    SELECT 
        COALESCE(SUM(CASE WHEN type = 'CREDIT' THEN amount ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN type != 'CREDIT' THEN amount ELSE 0 END),0)
    FROM transactions
    WHERE user_id=5 AND EXTRACT(MONTH FROM transaction_date)::int=5 AND EXTRACT(YEAR FROM transaction_date)::int=2026
""")
r = cur.fetchone()
print(f"Summary (CREDIT vs non-CREDIT): income=Rs {r[0]:,.0f}, expense=Rs {r[1]:,.0f}")

conn.close()
