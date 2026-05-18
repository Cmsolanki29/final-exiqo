"""Local parse test (no HTTP) for May 2026 Axis PDF."""
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from db import get_connection
from services.pdf_parser import PDFParserAgent

pdf = Path(__file__).resolve().parents[2] / "test samples" / "AXIS_BANK_STATEMENT_REALISTIC_FULL_MAY2026.pdf"
content = pdf.read_bytes()
conn = get_connection()
cur = conn.cursor()
import time

email = f"parse.local.{int(time.time())}@example.com"
from utils.auth import hash_password

cur.execute(
    "INSERT INTO users (name, email, password_hash, monthly_income, onboarding_completed) VALUES (%s,%s,%s,0,FALSE) RETURNING id",
    ("Parse Test", email, hash_password("TestPass123!")),
)
uid = int(cur.fetchone()[0])
cur.execute(
    """
    INSERT INTO connected_sources (user_id, source_type, institution_name, is_visible_on_dashboard, added_via, status)
    VALUES (%s, 'bank_statement_pdf', 'Axis Local Test', TRUE, 'settings_upload', 'active')
    RETURNING id
    """,
    (uid,),
)
sid = int(cur.fetchone()[0])
cur.execute(
    """
    INSERT INTO uploaded_documents (user_id, connected_source_id, file_name, file_type, file_size_kb)
    VALUES (%s, %s, %s, 'pdf', %s) RETURNING id
    """,
    (uid, sid, pdf.name, len(content) // 1024),
)
did = int(cur.fetchone()[0])
conn.commit()

res = PDFParserAgent().extract_transactions(content, pdf.name, uid, did, sid, conn)
conn.rollback()
print("result:", {k: res.get(k) for k in ("imported", "internal_transfers_skipped", "extracted", "success")})

cur.execute(
    "SELECT COUNT(*) FROM transactions WHERE user_id=%s AND transaction_date >= '2026-05-01'",
    (uid,),
)
print("may count", cur.fetchone()[0])
cur.execute(
    """
    SELECT transaction_date, type, amount, category, merchant, anomaly_flag
    FROM transactions WHERE user_id=%s AND merchant ILIKE '%%MSEDCL%%'
    """,
    (uid,),
)
print("msedcl rows", cur.fetchall())
cur.execute(
    """
    SELECT COALESCE(SUM(CASE WHEN type='CREDIT' THEN amount END),0),
           COALESCE(SUM(CASE WHEN type='DEBIT' THEN amount END),0)
    FROM transactions WHERE user_id=%s AND EXTRACT(MONTH FROM transaction_date)=5 AND EXTRACT(YEAR FROM transaction_date)=2026
    """,
    (uid,),
)
print("totals", cur.fetchone())
conn.close()
