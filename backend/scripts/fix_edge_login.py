import psycopg2

conn = psycopg2.connect(
    host="127.0.0.1", port=5432,
    dbname="smartspend_db", user="postgres", password="root@4321@"
)
cur = conn.cursor()

# Fix is_verified for all users that have it as False
cur.execute("""
    UPDATE users
    SET is_verified = TRUE
    WHERE is_verified = FALSE
    RETURNING id, email
""")
print("Fixed is_verified:", cur.fetchall())

# Fix onboarding_completed for demo users that have data
cur.execute("""
    UPDATE users
    SET onboarding_completed = TRUE
    WHERE email IN ('priya@demo.com', 'arjun@demo.com', 'kavya@demo.com')
    AND onboarding_completed = FALSE
    RETURNING email
""")
print("Fixed onboarding:", cur.fetchall())

conn.commit()
cur.close()
conn.close()
print("Done - all users can now sign in")
