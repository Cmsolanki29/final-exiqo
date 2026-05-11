"""Set is_verified=true for relevant users and fix OTP flow."""
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

# Mark all real/test users as verified
cur.execute("""
    UPDATE users
    SET is_verified = true
    WHERE email IN (
        'abc@gmail.com',
        'abcd@gmail.com',
        'johncena@gmail.com',
        'tester@exiqo.com',
        'debuguser99@test.com',
        'wrongcredstest99@test.com'
    )
""")
print(f"Updated real users: {cur.rowcount} rows")

# Update all banktest/fraudshield users
cur.execute("""
    UPDATE users
    SET is_verified = true
    WHERE email LIKE '%fraudshield.dev%'
       OR email LIKE '%smartspend.dev%'
""")
print(f"Updated banktest users: {cur.rowcount} rows")

conn.commit()

# Verify
cur.execute("SELECT id, email, is_verified, onboarding_completed FROM users ORDER BY id")
print("\nAll users:")
for r in cur.fetchall():
    print(f"  id={r[0]:2d} | {r[1]:45s} | verified={r[2]} | onboarding={r[3]}")

conn.close()
print("\n[OK] Done.")
