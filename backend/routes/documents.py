"""
Document upload & connected-sources API.

Endpoints:
  POST /documents/upload           — upload PDF/CSV/XLSX, extract transactions
  GET  /documents/history          — list past uploads for a user
  GET  /sources/connected           — list connected_sources for a user
  POST /sources/connected         — add a connected source manually
  POST /sources/toggle-visibility  — show/hide a source on the dashboard
  POST /user/update-dashboard-mode — set bank_only | credit_card_only | merged
"""
from __future__ import annotations

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
    source_type: str = Form(...),
    institution_name: str = Form(...),
    account_number_masked: Optional[str] = Form(None),
    conn=Depends(get_db),
):
    """Upload bank/credit-card statement PDF or CSV and extract transactions."""

    raw = (source_type or "").strip().lower()
    syn = {"bank_statement": "bank_statement_pdf", "bank_stmt": "bank_statement_pdf", "statement": "bank_statement_pdf"}
    raw = syn.get(raw, raw)
    allowed = {"bank", "credit_card", "upi", "other", "bank_statement_pdf"}
    if raw not in allowed:
        raise HTTPException(status_code=400, detail="Invalid source_type")

    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '.{ext}' not supported. Use PDF, CSV, or XLSX.",
        )

    file_bytes = await file.read()

    size_kb = len(file_bytes) // 1024
    if size_kb > _MAX_FILE_MB * 1024:
        raise HTTPException(status_code=413, detail=f"File too large (max {_MAX_FILE_MB} MB).")

    source_id = _upsert_source(
        conn,
        user_id=user_id,
        source_type=raw,
        institution_name=institution_name.strip()[:100],
        account_number_masked=account_number_masked,
    )

    doc_id = _create_document_record(
        conn,
        user_id=user_id,
        source_id=source_id,
        filename=file.filename or "upload",
        file_type=ext,
        size_kb=size_kb,
    )
    conn.commit()

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
              cs.is_visible_on_dashboard,
              cs.added_via,
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
# POST /sources/connected
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
        institution_name=institution_name.strip()[:100],
        account_number_masked=account_number_masked,
        is_primary=is_primary,
    )
    conn.commit()
    return {"success": True, "source_id": source_id}


# ──────────────────────────────────────────────────────────────────────────────
# POST /sources/toggle-visibility
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/sources/toggle-visibility")
def toggle_source_visibility(
    user_id: int = Form(...),
    source_id: int = Form(...),
    visible: bool = Form(...),
    conn=Depends(get_db),
):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE connected_sources
            SET is_visible_on_dashboard = %s
            WHERE id = %s AND user_id = %s
            RETURNING id
            """,
            (visible, source_id, user_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Source not found")
    conn.commit()
    return {"success": True, "source_id": source_id, "is_visible_on_dashboard": visible}


# ──────────────────────────────────────────────────────────────────────────────
# POST /user/update-dashboard-mode
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/user/update-dashboard-mode")
def update_dashboard_mode(
    user_id: int = Form(...),
    mode: str = Form(...),
    visible_source_ids: str = Form(""),  # comma-separated, empty = all active sources visible
    conn=Depends(get_db),
):
    raw = (mode or "").strip().lower()
    if raw not in ("bank_only", "credit_card_only", "merged"):
        raise HTTPException(status_code=400, detail="Invalid dashboard mode")
    mode_n = raw

    ids: list[int] = []
    for part in (visible_source_ids or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="visible_source_ids must be comma-separated integers") from exc

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET dashboard_mode = %s WHERE id = %s RETURNING id",
            (mode_n, user_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        if ids:
            cur.execute(
                "UPDATE connected_sources SET is_visible_on_dashboard = FALSE WHERE user_id = %s",
                (user_id,),
            )
            cur.execute(
                """
                UPDATE connected_sources
                SET is_visible_on_dashboard = TRUE
                WHERE user_id = %s AND id = ANY(%s::int[])
                """,
                (user_id, ids),
            )
        else:
            cur.execute(
                """
                UPDATE connected_sources
                SET is_visible_on_dashboard = TRUE
                WHERE user_id = %s AND status = 'active'
                """,
                (user_id,),
            )

    conn.commit()
    return {"success": True, "mode": mode_n, "visible_source_ids": ids}


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
              (user_id, source_type, institution_name, account_number_masked, is_primary,
               is_visible_on_dashboard, added_via, status)
            VALUES (%s, %s, %s, %s, %s, TRUE, 'settings_upload', 'active')
            ON CONFLICT ON CONSTRAINT connected_sources_user_inst_type_key DO UPDATE
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
