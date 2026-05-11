import psycopg2, os
from dotenv import load_dotenv
load_dotenv('../.env')
conn = psycopg2.connect(
    host=os.getenv('DB_HOST','127.0.0.1'), port=os.getenv('DB_PORT','5432'),
    dbname=os.getenv('DB_NAME','smartspend_db'), user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','').strip('"')
)
cur = conn.cursor()

cur.execute("SELECT type, transaction_date, amount, merchant FROM transactions WHERE user_id=5 AND type='CREDIT' ORDER BY transaction_date DESC LIMIT 10")
print("CREDIT transactions:")
for r in cur.fetchall():
    print(f"  type={r[0]} date={r[1]} amt={r[2]:.0f} merchant={r[3]}")

cur.execute("""
    SELECT COALESCE(SUM(amount),0) FROM transactions
    WHERE user_id=5 AND type='CREDIT'
    AND EXTRACT(YEAR FROM transaction_date) = EXTRACT(YEAR FROM NOW())
    AND EXTRACT(MONTH FROM transaction_date) = EXTRACT(MONTH FROM NOW())
""")
print(f"\nCurrent month CREDIT total: {cur.fetchone()[0]}")

cur.execute("SELECT EXTRACT(YEAR FROM transaction_date), EXTRACT(MONTH FROM transaction_date), COUNT(*), SUM(amount) FROM transactions WHERE user_id=5 AND type='CREDIT' GROUP BY 1,2 ORDER BY 1,2 DESC LIMIT 6")
print("\nMonthly CREDIT breakdown:")
for r in cur.fetchall():
    print(f"  {int(r[0])}-{int(r[1]):02d}: {int(r[2])} transactions, Rs {r[3]:,.0f}")
conn.close()
