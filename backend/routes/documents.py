"""
Document upload & connected-sources API.

Endpoints:
  POST /documents/upload       — upload PDF/CSV/XLSX, extract transactions
  GET  /documents/history      — list past uploads for a user
  GET  /sources/connected      — list connected_sources for a user
  POST /sources/connected      — add a connected source manually
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from db import get_db
from services.pdf_parser import PDFParserAgent

router = APIRouter(tags=["documents"])
_parser = PDFParserAgent()

_ALLOWED_EXTENSIONS = {"pdf", "csv", "xlsx", "xls", "txt"}
_MAX_FILE_MB = 20


# ──────────────────────────────────────────────────────────────────────────────
# POST /documents/upload
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/documents/upload")
async def upload_statement(
    file: UploadFile = File(...),
    user_id: int = Form(...),
    source_type: str = Form(...),          # 'bank' | 'credit_card' | 'upi' | 'other'
    institution_name: str = Form(...),
    account_number_masked: Optional[str] = Form(None),
    conn=Depends(get_db),
):
    """Upload bank/credit-card statement PDF or CSV and extract transactions."""

    # --- validate file type
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '.{ext}' not supported. Use PDF, CSV, or XLSX.",
        )

    file_bytes = await file.read()

    # --- guard file size
    size_kb = len(file_bytes) // 1024
    if size_kb > _MAX_FILE_MB * 1024:
        raise HTTPException(status_code=413, detail=f"File too large (max {_MAX_FILE_MB} MB).")

    # --- upsert connected_source
    source_id = _upsert_source(
        conn,
        user_id=user_id,
        source_type=source_type,
        institution_name=institution_name,
        account_number_masked=account_number_masked,
    )

    # --- create uploaded_documents record
    doc_id = _create_document_record(
        conn,
        user_id=user_id,
        source_id=source_id,
        filename=file.filename or "upload",
        file_type=ext,
        size_kb=size_kb,
    )
    conn.commit()

    # --- run AI extraction (parser handles its own commits)
    result = _parser.extract_transactions(
        file_bytes=file_bytes,
        filename=file.filename or "upload",
        user_id=user_id,
        document_id=doc_id,
        connected_source_id=source_id,
        conn=conn,
    )

    result["document_id"] = doc_id
    result["source_id"] = source_id
    return result


# ──────────────────────────────────────────────────────────────────────────────
# GET /documents/history
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/documents/history")
def get_upload_history(user_id: int = Query(...), conn=Depends(get_db)):
    """Return last 20 uploads for a user."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              ud.id, ud.file_name, ud.file_type, ud.file_size_kb,
              ud.extraction_status, ud.rows_extracted, ud.rows_imported,
              ud.rows_skipped_duplicates, ud.uploaded_at, ud.processed_at,
              cs.institution_name, cs.source_type
            FROM uploaded_documents ud
            LEFT JOIN connected_sources cs ON cs.id = ud.connected_source_id
            WHERE ud.user_id = %s
            ORDER BY ud.uploaded_at DESC
            LIMIT 20
            """,
            (user_id,),
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    for r in rows:
        if r.get("uploaded_at"):
            r["uploaded_at"] = r["uploaded_at"].isoformat()
        if r.get("processed_at"):
            r["processed_at"] = r["processed_at"].isoformat()

    return {"uploads": rows}


# ──────────────────────────────────────────────────────────────────────────────
# GET /sources/connected
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/sources/connected")
def get_connected_sources(user_id: int = Query(...), conn=Depends(get_db)):
    """Return all active connected sources with upload & transaction counts."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              cs.id,
              cs.source_type,
              cs.institution_name,
              cs.account_number_masked,
              cs.is_primary,
              cs.status,
              cs.connected_at,
              COUNT(DISTINCT ud.id)    AS uploads_count,
              COUNT(DISTINCT t.id)     AS transactions_count,
              MAX(ud.uploaded_at)      AS last_upload
            FROM connected_sources cs
            LEFT JOIN uploaded_documents ud ON ud.connected_source_id = cs.id
            LEFT JOIN transactions t ON t.connected_source_id = cs.id
            WHERE cs.user_id = %s AND cs.status = 'active'
            GROUP BY cs.id
            ORDER BY cs.is_primary DESC, cs.connected_at DESC
            """,
            (user_id,),
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    for r in rows:
        if r.get("connected_at"):
            r["connected_at"] = r["connected_at"].isoformat()
        if r.get("last_upload"):
            r["last_upload"] = r["last_upload"].isoformat()

    return {"sources": rows}


# ──────────────────────────────────────────────────────────────────────────────
# POST /sources/connected  (manual add without upload)
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/sources/connected")
def add_connected_source(
    user_id: int = Form(...),
    source_type: str = Form(...),
    institution_name: str = Form(...),
    account_number_masked: Optional[str] = Form(None),
    is_primary: bool = Form(False),
    conn=Depends(get_db),
):
    source_id = _upsert_source(
        conn,
        user_id=user_id,
        source_type=source_type,
        institution_name=institution_name,
        account_number_masked=account_number_masked,
        is_primary=is_primary,
    )
    conn.commit()
    return {"success": True, "source_id": source_id}


# ──────────────────────────────────────────────────────────────────────────────
# Private helpers
# ──────────────────────────────────────────────────────────────────────────────
def _upsert_source(
    conn,
    *,
    user_id: int,
    source_type: str,
    institution_name: str,
    account_number_masked: str | None = None,
    is_primary: bool = False,
) -> int:
    """Insert or return existing connected_source id."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO connected_sources
              (user_id, source_type, institution_name, account_number_masked, is_primary)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id, LOWER(institution_name)) DO UPDATE
              SET account_number_masked = COALESCE(EXCLUDED.account_number_masked, connected_sources.account_number_masked),
                  status = 'active'
            RETURNING id
            """,
            (user_id, source_type, institution_name, account_number_masked, is_primary),
        )
        return cur.fetchone()[0]


def _create_document_record(
    conn, *, user_id: int, source_id: int, filename: str, file_type: str, size_kb: int
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO uploaded_documents
              (user_id, connected_source_id, file_name, file_type, file_size_kb)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, source_id, filename, file_type, size_kb),
        )
        return cur.fetchone()[0]
