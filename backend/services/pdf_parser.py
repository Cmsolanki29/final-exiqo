"""
PDFParserAgent — monster extraction pipeline for uploaded statements.

Stages: extract_with_retry → classify_and_extract_monster → validate → dedupe → insert.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any

from services.document_parser_service import classify_and_extract_monster
from services.monster_extraction import extract_with_retry, update_extraction_llm_result

logger = logging.getLogger(__name__)

_CREDIT_KEYWORDS = {"credit", "cr", "deposit", "salary", "refund", "cashback", "received", "reversal"}
_TRANSFER_KEYWORDS = {
    "credit card payment", "cc payment", "card payment", "payment received",
    "payment towards", "autopay", "inward transfer", "outward transfer",
}


def _normalise_type(raw: str | None) -> str:
    r = (raw or "").lower().strip()
    if any(k in r for k in _CREDIT_KEYWORDS):
        return "CREDIT"
    return "DEBIT"


def _is_internal_transfer(merchant: str, description: str) -> bool:
    combined = f"{merchant} {description}".lower()
    return any(k in combined for k in _TRANSFER_KEYWORDS)


class PDFParserAgent:
    """Extract, validate, deduplicate and insert transactions from uploaded files."""

    def extract_transactions(
        self,
        file_bytes: bytes,
        filename: str,
        user_id: int,
        document_id: int,
        connected_source_id: int | None,
        conn,
    ) -> dict[str, Any]:
        self._set_status(conn, document_id, "processing")
        conn.commit()

        extraction = extract_with_retry(
            content=file_bytes,
            filename=filename,
            user_id=user_id,
            doc_id=document_id,
            conn=conn,
        )

        quality_score = extraction.get("quality_score", 0)
        text = (extraction.get("text") or "").strip()

        if quality_score < 30 and not text:
            err = extraction.get("error", "Could not extract text from document")
            self._mark_failed(conn, document_id, err)
            conn.commit()
            update_extraction_llm_result(
                conn,
                document_id,
                user_id,
                llm_raw="",
                model="",
                extracted=0,
                after_validation=0,
                validation_issues=[err],
                stored=0,
                categorization_method="none",
                status="failed",
                error=err,
            )
            return {"success": False, "error": err, "quality_score": quality_score}

        if text.startswith("[") and "error" in text.lower():
            self._mark_failed(conn, document_id, text)
            conn.commit()
            return {"success": False, "error": text, "quality_score": quality_score}

        parsed = classify_and_extract_monster(
            text=text,
            filename=filename,
            tables=extraction.get("tables"),
        )
        transactions = parsed.get("transactions", [])
        validation_issues: list[str] = list(extraction.get("quality_issues") or [])
        if parsed.get("validation_issues"):
            validation_issues.extend(parsed["validation_issues"])

        imported = duplicates = invalid = internal = 0

        for txn in transactions:
            if not self._is_valid(txn):
                invalid += 1
                continue

            merchant = (txn.get("description") or "").strip()[:100] or "Unknown"
            desc = (txn.get("description") or "")[:200]
            try:
                amount = float(txn.get("amount", 0))
            except (TypeError, ValueError):
                invalid += 1
                continue
            if amount <= 0:
                invalid += 1
                continue

            raw_type = _normalise_type(txn.get("type"))
            txn_date = self._parse_date(txn.get("date", ""))
            if not txn_date:
                invalid += 1
                continue

            if _is_internal_transfer(merchant, desc):
                internal += 1
                continue

            if self._is_duplicate(conn, user_id, txn_date, merchant, amount):
                duplicates += 1
                continue

            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO transactions
                      (user_id, amount, type, category, merchant,
                       transaction_date, description,
                       uploaded_document_id, connected_source_id, data_origin)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'monster_upload')
                    """,
                    (
                        user_id,
                        amount,
                        raw_type,
                        txn.get("category", "other"),
                        merchant,
                        txn_date,
                        desc,
                        document_id,
                        connected_source_id,
                    ),
                )
            imported += 1

        self._mark_completed(conn, document_id, len(transactions), imported, duplicates)
        conn.commit()

        llm_raw = json.dumps({
            "institution": parsed.get("institution"),
            "document_type": parsed.get("document_type"),
            "transaction_count": len(transactions),
            "doc_info": parsed.get("doc_info"),
        })
        update_extraction_llm_result(
            conn,
            document_id,
            user_id,
            llm_raw=llm_raw,
            model=parsed.get("llm_model") or parsed.get("method") or "router",
            extracted=len(transactions),
            after_validation=len(transactions) - invalid,
            validation_issues=validation_issues,
            stored=imported,
            categorization_method=parsed.get("method", "chunked_llm"),
            status="completed",
        )

        return {
            "success": True,
            "institution": parsed.get("institution", "unknown"),
            "document_type": parsed.get("document_type", "other"),
            "date_range": parsed.get("date_range"),
            "extracted": len(transactions),
            "imported": imported,
            "duplicates": duplicates,
            "internal_transfers_skipped": internal,
            "invalid": invalid,
            "quality_score": quality_score,
            "extraction_method": extraction.get("method", "unknown"),
            "attempts": extraction.get("attempt_number", 1),
            "transactions_extracted": len(transactions),
            "transactions_stored": imported,
        }

    @staticmethod
    def _parse_date(raw: str) -> str | None:
        raw = (raw or "").strip()
        for fmt in (
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d %b %Y",
            "%d-%b-%Y",
            "%d-%b-%y",
            "%b %d, %Y",
            "%b %d %Y",
        ):
            try:
                return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
        m = re.search(r"(\d{4}-\d{2}-\d{2})", raw)
        return m.group(1) if m else None

    @staticmethod
    def _is_valid(txn: dict) -> bool:
        try:
            return bool(txn.get("date") and txn.get("description") and float(txn.get("amount", 0)) > 0)
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _is_duplicate(conn, user_id: int, date: str, merchant: str, amount: float) -> bool:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM transactions t
                WHERE t.user_id = %s
                  AND t.transaction_date::date = %s
                  AND LOWER(t.merchant) = LOWER(%s)
                  AND ABS(t.amount - %s) < 5
                  AND (
                    t.connected_source_id IS NULL
                    OR NOT EXISTS (
                      SELECT 1 FROM connected_sources cs
                      WHERE cs.id = t.connected_source_id
                        AND COALESCE(cs.is_visible_on_dashboard, false) = false
                    )
                  )
                """,
                (user_id, date, merchant, amount),
            )
            return (cur.fetchone()[0] or 0) > 0

    @staticmethod
    def _set_status(conn, document_id: int, status: str) -> None:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE uploaded_documents SET extraction_status = %s WHERE id = %s",
                (status, document_id),
            )

    @staticmethod
    def _mark_completed(conn, document_id: int, extracted: int, imported: int, duplicates: int) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE uploaded_documents
                SET extraction_status = 'completed',
                    rows_extracted = %s, rows_imported = %s,
                    rows_skipped_duplicates = %s, processed_at = NOW()
                WHERE id = %s
                """,
                (extracted, imported, duplicates, document_id),
            )

    @staticmethod
    def _mark_failed(conn, document_id: int, error: str) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE uploaded_documents
                SET extraction_status = 'failed',
                    metadata = jsonb_build_object('error', %s),
                    processed_at = NOW()
                WHERE id = %s
                """,
                (error[:400], document_id),
            )
