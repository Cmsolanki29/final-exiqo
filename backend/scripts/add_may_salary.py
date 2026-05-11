import psycopg2, os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv('../.env')
conn = psycopg2.connect(
    host=os.getenv('DB_HOST','127.0.0.1'), port=os.getenv('DB_PORT','5432'),
    dbname=os.getenv('DB_NAME','smartspend_db'), user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','').strip('"')
)
cur = conn.cursor()
USER_ID = 5

cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='transactions' ORDER BY ordinal_position")
cols = [r[0] for r in cur.fetchall()]
print("Transaction columns:", cols)

may_1 = datetime(2026, 5, 1, 9, 0, 0)

# Build insert with only existing columns
available = []
values = []
if 'user_id' in cols: available.append('user_id'); values.append(USER_ID)
if 'amount' in cols: available.append('amount'); values.append(85000.00)
if 'merchant' in cols: available.append('merchant'); values.append('NEFT-SALARY-MAY2026')
if 'category' in cols: available.append('category'); values.append('Salary')
if 'type' in cols: available.append('type'); values.append('CREDIT')
if 'transaction_date' in cols: available.append('transaction_date'); values.append(may_1.date())
if 'transaction_time' in cols: available.append('transaction_time'); values.append(may_1)
if 'location' in cols: available.append('location'); values.append('Mumbai')
if 'is_fraud' in cols: available.append('is_fraud'); values.append(False)

cols_str = ', '.join(available)
placeholders = ', '.join(['%s'] * len(available))
cur.execute(f"INSERT INTO transactions ({cols_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING", values)
conn.commit()
print(f"Inserted May 2026 salary. Rows affected: {cur.rowcount}")

# Verify
cur.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=5 AND type='CREDIT' AND EXTRACT(YEAR FROM transaction_date) = 2026 AND EXTRACT(MONTH FROM transaction_date) = 5")
print(f"May 2026 income: Rs {cur.fetchone()[0]:,.0f}")
conn.close()
