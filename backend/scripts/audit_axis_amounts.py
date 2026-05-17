"""One-off audit: Axis card amounts in DB."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
import psycopg2

pw = os.getenv("DB_PASSWORD", "").strip().strip('"').strip("'")
conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=pw,
)
cur = conn.cursor()

print("=== connected_sources (axis) ===")
cur.execute(
    """
    SELECT id, user_id, institution_name, source_type, is_visible_on_dashboard, status
    FROM connected_sources
    WHERE institution_name ILIKE '%axis%'
    ORDER BY id DESC LIMIT 10
    """
)
sources = cur.fetchall()
for r in sources:
    print(r)

if not sources:
    print("No axis sources found")
    sys.exit(0)

source_id = sources[0][0]
print(f"\n=== transactions for source_id={source_id} ===")
cur.execute(
    """
    SELECT id, transaction_date, description, amount, type, category, data_origin
    FROM transactions
    WHERE connected_source_id = %s
    ORDER BY transaction_date, id
    """,
    (source_id,),
)
rows = cur.fetchall()
total = 0.0
for r in rows:
    print(r)
    total += float(r[3] or 0)
print(f"\nCOUNT={len(rows)} SUM(amount)={total:.2f}")

cur.execute(
    """
    SELECT COUNT(*), COALESCE(SUM(amount),0),
           COALESCE(SUM(CASE WHEN type='debit' THEN amount ELSE 0 END),0),
           COALESCE(SUM(CASE WHEN type='credit' THEN amount ELSE 0 END),0)
    FROM transactions WHERE connected_source_id = %s
    """,
    (source_id,),
)
print("AGG:", cur.fetchone())

cur.execute(
    """
    SELECT ud.id, er.extraction_method, er.quality_score, er.transactions_extracted,
           er.llm_model_used, LEFT(er.llm_raw_response, 1500)
    FROM uploaded_documents ud
    LEFT JOIN extraction_results er ON er.uploaded_document_id = ud.id
    WHERE ud.connected_source_id = %s
    ORDER BY ud.id DESC, er.id DESC LIMIT 3
    """,
    (source_id,),
)
print("\n=== extraction_results ===")
for r in cur.fetchall():
    print("---")
    print(r[0], r[1], r[2], r[3], r[4])
    if r[5]:
        print(r[5][:1200])

conn.close()
