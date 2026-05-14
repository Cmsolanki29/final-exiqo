"""
AI Context Service — assembles a compressed context packet for the AI chatbot.

Uses the existing psycopg2 sync DB layer (same as all other services in this project).
Never sends raw DB rows to the LLM — always compresses into a clean dict first.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from db import get_connection

_log = logging.getLogger(__name__)


def _rollback_conn(conn) -> None:
    try:
        conn.rollback()
    except Exception:
        pass


def build_context_packet(user_id: int, session_id: str | None = None) -> dict[str, Any]:
    """
    Fetch all relevant data for this user and return a clean context dict.
    This is the ONLY thing the AI sees — no raw SQL rows, no PII beyond what's needed.
    Robust: any missing column / table is caught and skipped; context is always returned.
    """
    conn = get_connection()
    cur = None
    try:
        cur = conn.cursor()

        # ── 1. User profile ────────────────────────────────────────────────
        user_data: dict[str, Any] = {}
        try:
            cur.execute(
                """
                SELECT id, name, email, monthly_income, savings_goal,
                       COALESCE(risk_tolerance, 'moderate') AS risk_tolerance
                FROM users WHERE id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
            if row:
                user_data = {
                    "name": row[1],
                    "monthly_income": float(row[3] or 0),
                    "savings_goal": float(row[4] or 0),
                    "risk_tolerance": row[5],
                }
        except Exception as e:
            _rollback_conn(conn)
            _log.warning("[ai_context] user fetch error: %s", e)

        # ── 2. Linked bank accounts ────────────────────────────────────────
        linked_accounts: list[dict] = []
        try:
            cur.execute(
                """
                SELECT bank_name, account_masked, connection_status,
                       last_synced
                FROM bank_connections WHERE user_id = %s
                """,
                (user_id,),
            )
            for r in cur.fetchall():
                linked_accounts.append({
                    "bank": r[0],
                    "masked": r[1],
                    "status": r[2],
                    "last_synced": str(r[3]) if r[3] else None,
                })
        except Exception as e:
            _rollback_conn(conn)
            _log.warning("[ai_context] bank_connections fetch error: %s", e)

        # ── 3. Recent transactions (last 30 days, max 50) ─────────────────
        recent_txns: list[dict] = []
        try:
            cur.execute(
                """
                SELECT merchant, category, amount, transaction_date, type,
                       COALESCE(document_origin, 'linked_bank') AS data_source
                FROM transactions
                WHERE user_id = %s
                  AND transaction_date >= (CURRENT_TIMESTAMP - INTERVAL '30 days')
                ORDER BY transaction_date DESC
                LIMIT 50
                """,
                (user_id,),
            )
            for r in cur.fetchall():
                recent_txns.append({
                    "merchant": r[0],
                    "category": r[1],
                    "amount": float(r[2] or 0),
                    "date": str(r[3]),
                    "type": r[4],
                    "is_emi": False,
                    "is_recurring": False,
                    "source": r[5] or "linked_bank",
                })
        except Exception as e:
            _rollback_conn(conn)
            _log.warning("[ai_context] transactions fetch error: %s", e)
            try:
                cur.execute(
                    """
                    SELECT merchant, category, amount, transaction_date, type
                    FROM transactions
                    WHERE user_id = %s
                      AND transaction_date >= (CURRENT_TIMESTAMP - INTERVAL '30 days')
                    ORDER BY transaction_date DESC
                    LIMIT 50
                    """,
                    (user_id,),
                )
                for r in cur.fetchall():
                    recent_txns.append({
                        "merchant": r[0],
                        "category": r[1],
                        "amount": float(r[2] or 0),
                        "date": str(r[3]),
                        "type": r[4],
                        "is_emi": False,
                        "is_recurring": False,
                        "source": "linked_bank",
                    })
            except Exception as e2:
                _rollback_conn(conn)
                _log.warning("[ai_context] transactions fallback fetch error: %s", e2)

        # ── 4. EMI records (schema matches emi_detector inserts) ─────────
        active_emis: list[dict] = []
        try:
            cur.execute(
                """
                SELECT
                    COALESCE(merchant, 'Unknown') AS lender,
                    COALESCE(detected_amount, 0) AS emi_amount,
                    payment_date,
                    COALESCE(months_detected, 0) AS months_remaining
                FROM emi_records
                WHERE user_id = %s
                  AND is_active IS TRUE
                ORDER BY payment_date ASC NULLS LAST
                LIMIT 10
                """,
                (user_id,),
            )
            for r in cur.fetchall():
                active_emis.append({
                    "lender": r[0],
                    "amount": float(r[1] or 0),
                    "next_due": str(r[2]) if r[2] else None,
                    "remaining_months": int(r[3] or 0),
                })
        except Exception as e:
            _rollback_conn(conn)
            _log.warning("[ai_context] emi_records fetch error: %s", e)

        # ── 5. Monthly summary (latest row) ───────────────────────────────
        monthly_summary: dict = {}
        try:
            cur.execute(
                """
                SELECT total_income, total_expense,
                       COALESCE(total_saved, total_income - total_expense, 0),
                       COALESCE(savings_rate, 0),
                       year, month
                FROM monthly_summary
                WHERE user_id = %s
                ORDER BY year DESC, month DESC
                LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()
            if row:
                monthly_summary = {
                    "income": float(row[0] or 0),
                    "expense": float(row[1] or 0),
                    "savings": float(row[2] or 0),
                    "savings_rate": float(row[3] or 0),
                    "categories": {},
                    "period": f"{int(row[4])}-{int(row[5]):02d}",
                }
        except Exception as e:
            _rollback_conn(conn)
            _log.warning("[ai_context] monthly_summary fetch error: %s", e)

        # ── 6. Active subscriptions ───────────────────────────────────────
        subscriptions: list[dict] = []
        try:
            cur.execute(
                """
                SELECT
                    COALESCE(merchant, 'Unknown') AS service,
                    COALESCE(NULLIF(monthly_cost, 0), amount, 0)::double precision AS amount,
                    COALESCE(last_charged, first_charged) AS billing_date,
                    COALESCE(status, 'active') AS status
                FROM subscriptions
                WHERE user_id = %s
                  AND (status IS NULL OR LOWER(status) NOT IN ('cancelled', 'pending_cancel'))
                ORDER BY 3 ASC NULLS LAST
                LIMIT 10
                """,
                (user_id,),
            )
            for r in cur.fetchall():
                subscriptions.append({
                    "service": r[0],
                    "amount": float(r[1] or 0),
                    "billing_date": str(r[2]) if r[2] else None,
                    "status": r[3],
                })
        except Exception as e:
            _rollback_conn(conn)
            _log.warning("[ai_context] subscriptions fetch error: %s", e)

        # ── 7. Uploaded documents for this session ─────────────────────────
        uploaded_docs: list[dict] = []
        if session_id:
            try:
                cur.execute(
                    """
                    SELECT file_name, document_type, institution,
                           is_linked_account, extracted_json
                    FROM document_uploads
                    WHERE user_id = %s AND session_id = %s::uuid
                      AND expires_at > NOW()
                    """,
                    (user_id, session_id),
                )
                for r in cur.fetchall():
                    try:
                        extracted = r[4] if isinstance(r[4], dict) else (
                            json.loads(r[4]) if r[4] else {}
                        )
                    except Exception:
                        extracted = {}
                    uploaded_docs.append({
                        "file": r[0],
                        "type": r[1],
                        "institution": r[2],
                        "is_linked": bool(r[3]),
                        "data": extracted,
                    })
            except Exception as e:
                _rollback_conn(conn)
                _log.warning("[ai_context] document_uploads fetch error: %s", e)

    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        conn.close()

    # ── Build the clean packet ─────────────────────────────────────────────
    return {
        "user": user_data,
        "linked_accounts": linked_accounts,
        "monthly_summary": monthly_summary,
        "recent_transactions": recent_txns,
        "active_emis": active_emis,
        "subscriptions": subscriptions,
        "uploaded_documents": uploaded_docs,
        "app_features": [
            {"name": "EMI Tracker", "route": "/emi",
             "description": "Track all EMIs, due dates, lenders"},
            {"name": "Subscriptions AI", "route": "/subscriptions",
             "description": "Manage recurring subscriptions, cancel unused ones"},
            {"name": "FraudShield", "route": "/fraud",
             "description": "Detect suspicious transactions"},
            {"name": "Dark Patterns", "route": "/dark-patterns",
             "description": "Identify manipulative charges"},
            {"name": "Transactions", "route": "/transactions",
             "description": "Full transaction history with filters"},
        ],
    }
