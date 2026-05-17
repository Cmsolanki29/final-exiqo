"""One-shot E2E test for monster upload pipeline (rolls back)."""
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

from services.pdf_parser import PDFParserAgent

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
)
uid = 1
csv_path = Path(__file__).resolve().parent.parent / "data" / "sample_csvs" / "hdfc_statement.csv"
content = csv_path.read_bytes()

with conn.cursor() as cur:
    cur.execute(
        """
        INSERT INTO connected_sources
          (user_id, source_type, institution_name, is_visible_on_dashboard, added_via, status)
        VALUES (%s, 'bank_statement_pdf', 'HDFC Test Pipeline', TRUE, 'settings_upload', 'active')
        RETURNING id
        """,
        (uid,),
    )
    sid = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO uploaded_documents
          (user_id, connected_source_id, file_name, file_type, file_size_kb)
        VALUES (%s, %s, %s, 'csv', %s)
        RETURNING id
        """,
        (uid, sid, csv_path.name, len(content) // 1024),
    )
    did = cur.fetchone()[0]
conn.commit()

result = PDFParserAgent().extract_transactions(content, csv_path.name, uid, did, sid, conn)

with conn.cursor() as cur:
    cur.execute(
        """
        SELECT COUNT(*), MAX(quality_score), STRING_AGG(DISTINCT extraction_method, ',')
        FROM extraction_results WHERE uploaded_document_id = %s
        """,
        (did,),
    )
    er = cur.fetchone()

print("pipeline result:", {k: result.get(k) for k in ("success", "imported", "extracted", "quality_score", "extraction_method", "attempts")})
print("extraction_results:", {"count": er[0], "max_score": er[1], "methods": er[2]})

conn.rollback()
print("rolled back test transaction")
