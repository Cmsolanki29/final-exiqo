"""
AI Context Service — assembles a compressed context packet for the AI chatbot.

Uses the existing psycopg2 sync DB layer (same as all other services in this project).
Never sends raw DB rows to the LLM — always compresses into a clean dict first.
"""
from __future__ import annotations

import calendar
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from db import get_connection
from services.dashboard_scope import normalize_dashboard_mode, transaction_scope_sql

_log = logging.getLogger(__name__)

_CACHE_TTL_MINUTES = 10


def _rollback_conn(conn) -> None:
    try:
        conn.rollback()
    except Exception:
        pass


def get_user_name(user_id: int) -> str:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(NULLIF(TRIM(name), ''), 'there') FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        return str(row[0]) if row else "there"
    except Exception:
        return "there"
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


def _fetch_connected_sources(cur, user_id: int) -> list[dict[str, Any]]:
    try:
        cur.execute(
            """
            SELECT institution_name, source_type,
                   COALESCE(status, 'active') AS status
            FROM connected_sources
            WHERE user_id = %s
              AND COALESCE(status, 'active') = 'active'
            ORDER BY is_primary DESC NULLS LAST, connected_at DESC NULLS LAST
            """,
            (user_id,),
        )
        return [
            {"institution_name": r[0] or "", "source_type": r[1] or ""}
            for r in cur.fetchall()
        ]
    except Exception as e:
        _rollback_conn(cur.connection)
        _log.warning("[ai_context] connected_sources fetch error: %s", e)
        return []


def resolve_identity_scope(
    user_id: int,
    uploaded_doc_metadata: dict | None,
    connected_sources: list[dict],
) -> dict[str, Any]:
    """
    Determines data scope and relationship of an uploaded document to this user.
    """
    user_name = get_user_name(user_id)
    linked_bank_names = [
        s["institution_name"]
        for s in connected_sources
        if s.get("institution_name")
    ]

    if not uploaded_doc_metadata:
        return {
            "scope": "no_upload",
            "warning_message": None,
            "nudge_message": None,
            "linked_bank_names": linked_bank_names,
            "user_name": user_name,
        }

    doc_bank = (uploaded_doc_metadata.get("institution_name") or "").lower()
    institution_label = uploaded_doc_metadata.get("institution_name") or "this bank"
    is_doc_linked = bool(uploaded_doc_metadata.get("is_linked_account"))

    bank_name_match = bool(
        doc_bank
        and any(
            doc_bank in (s.get("institution_name") or "").lower()
            or (s.get("institution_name") or "").lower() in doc_bank
            for s in connected_sources
        )
    )

    if is_doc_linked:
        return {
            "scope": "linked_full",
            "warning_message": None,
            "nudge_message": None,
            "linked_bank_names": linked_bank_names,
            "user_name": user_name,
        }

    if bank_name_match:
        warning = (
            f"Hi {user_name}! This looks like your {institution_label} statement, "
            "but it's not connected to your account. I can give you a summary — "
            "connect it in the Accounts section for full tracking."
        )
        nudge = (
            "Connect this account in Settings → Connected Accounts for permanent "
            "tracking and trends."
        )
        scope = "unlinked_same_bank"
    else:
        linked_str = ", ".join(linked_bank_names) if linked_bank_names else "none yet"
        warning = (
            f"Hi {user_name}! This appears to be a {institution_label} statement. "
            f"Your linked accounts are: {linked_str}. "
            "I'll share a health snapshot, but for full insights this account needs to be connected."
        )
        nudge = "To track this account permanently, go to Connect Account section."
        scope = "unlinked_foreign"

    return {
        "scope": scope,
        "warning_message": warning,
        "nudge_message": nudge,
        "linked_bank_names": linked_bank_names,
        "user_name": user_name,
    }


def extract_all_amounts_from_context(context_packet: dict) -> list[float]:
    amounts: list[float] = []

    def _add(v: Any) -> None:
        try:
            amounts.append(float(v))
        except (TypeError, ValueError):
            pass

    ms = context_packet.get("monthly_summary") or {}
    for k in ("income", "expense", "savings"):
        _add(ms.get(k))
    for cat_amt in (ms.get("categories") or {}).values():
        _add(cat_amt)

    for txn in context_packet.get("recent_transactions") or []:
        _add(txn.get("amount"))
    for emi in context_packet.get("active_emis") or []:
        _add(emi.get("amount"))
    for sub in context_packet.get("subscriptions") or []:
        _add(sub.get("amount"))

    return amounts


def invalidate_session_context_cache(session_id: str) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE ai_sessions
            SET cached_context = NULL,
                context_built_at = NULL,
                cache_dashboard_scope = NULL,
                cache_context_month = NULL,
                cache_context_year = NULL
            WHERE id = %s::uuid
            """,
            (session_id,),
        )
        conn.commit()
    except Exception as e:
        _log.warning("[ai_context] cache invalidate failed: %s", e)
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


def calculate_quick_health(transactions: list[dict]) -> dict[str, Any]:
    """Quick health snapshot from session-only uploaded transactions."""
    debits = 0.0
    credits = 0.0
    categories: dict[str, float] = {}
    for txn in transactions:
        try:
            amount = float(txn.get("amount") or 0)
        except (TypeError, ValueError):
            continue
        if str(txn.get("type", "debit")).lower() == "credit":
            credits += amount
        else:
            debits += amount
            cat = str(txn.get("category") or "other")
            categories[cat] = categories.get(cat, 0.0) + amount

    net = credits - debits
    savings_rate = round(net / credits * 100, 1) if credits > 0 else 0.0
    top_cat: tuple[str, float] | None = None
    if categories:
        top_cat = max(categories.items(), key=lambda x: x[1])

    return {
        "total_debits": round(debits, 2),
        "total_credits": round(credits, 2),
        "net": round(net, 2),
        "savings_rate_pct": savings_rate,
        "transaction_count": len(transactions),
        "top_spending_category": top_cat[0] if top_cat else None,
        "top_spending_amount": round(top_cat[1], 2) if top_cat else 0.0,
    }


def update_session_upload_context(session_id: str, payload: dict[str, Any]) -> None:
    """Persist doc_info, identity_scope, and session-only transactions on ai_sessions."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE ai_sessions
            SET upload_scope_context = %s::jsonb,
                cached_context = NULL,
                context_built_at = NULL
            WHERE id = %s::uuid
            """,
            (json.dumps(payload, default=str), session_id),
        )
        conn.commit()
    except Exception as e:
        _log.warning("[ai_context] update_session_upload_context failed: %s", e)
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


def save_upload_scope_context(session_id: str, identity_scope: dict) -> None:
    """Backward-compatible wrapper — prefer update_session_upload_context."""
    update_session_upload_context(session_id, {"identity_scope": identity_scope})


def load_upload_scope_context(session_id: str) -> dict | None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT upload_scope_context FROM ai_sessions WHERE id = %s::uuid",
            (session_id,),
        )
        row = cur.fetchone()
        if not row or not row[0]:
            return None
        val = row[0]
        return val if isinstance(val, dict) else json.loads(val)
    except Exception:
        return None
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


def merge_session_upload_into_packet(packet: dict[str, Any], session_id: str | None) -> dict[str, Any]:
    """Inject session-only upload data from ai_sessions.upload_scope_context."""
    if not session_id:
        return packet
    ctx = load_upload_scope_context(session_id)
    if not ctx:
        return packet

    txns = ctx.get("transactions") or []
    identity = ctx.get("identity_scope") or {}
    scope = identity.get("scope", "no_upload")
    doc_info = ctx.get("doc_info") or {}

    packet["session_upload"] = {
        "doc_info": doc_info,
        "identity_scope": scope,
        "transaction_count": len(txns),
        "health_preview": ctx.get("health_preview"),
        "extracted_at": ctx.get("extracted_at"),
        "transactions": txns[:100],
    }

    if txns:
        session_txn_view = [
            {
                "merchant": t.get("description", "")[:80],
                "category": t.get("category", "other"),
                "amount": t.get("amount", 0),
                "date": t.get("date"),
                "type": t.get("type", "debit"),
                "source": "session_upload",
            }
            for t in txns[:50]
        ]
        if scope == "unlinked_foreign":
            packet["recent_transactions"] = session_txn_view
        else:
            packet["recent_transactions"] = session_txn_view + (packet.get("recent_transactions") or [])
            packet["recent_transactions"] = packet["recent_transactions"][:50]

        hp = ctx.get("health_preview") or {}
        if hp and scope in ("unlinked_foreign", "unlinked_same_bank"):
            packet["monthly_summary"] = {
                **(packet.get("monthly_summary") or {}),
                "expense": hp.get("total_debits", 0),
                "income": hp.get("total_credits", 0),
                "savings": hp.get("net", 0),
                "savings_rate": hp.get("savings_rate_pct", 0),
                "period_label": doc_info.get("statement_period") or packet.get("period_label"),
                "source": "session_upload",
            }

    return packet


def get_or_build_context_packet(
    user_id: int,
    session_id: str | None,
    dashboard_scope: str = "merged",
    context_month: int | None = None,
    context_year: int | None = None,
    force_rebuild: bool = False,
) -> dict[str, Any]:
    """Return cached context when fresh; otherwise build and persist to ai_sessions."""
    mode = normalize_dashboard_mode(dashboard_scope)
    now = datetime.now()
    month = int(context_month or now.month)
    year = int(context_year or now.year)

    if session_id and not force_rebuild:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT cached_context, context_built_at,
                       cache_dashboard_scope, cache_context_month, cache_context_year
                FROM ai_sessions
                WHERE id = %s::uuid AND user_id = %s
                """,
                (session_id, user_id),
            )
            row = cur.fetchone()
            if row and row[0] and row[1]:
                built_at = row[1]
                if built_at.tzinfo is None:
                    built_at = built_at.replace(tzinfo=timezone.utc)
                age = datetime.now(timezone.utc) - built_at.astimezone(timezone.utc)
                scope_ok = (row[2] or "merged") == mode
                month_ok = int(row[3] or 0) == month
                year_ok = int(row[4] or 0) == year
                if age < timedelta(minutes=_CACHE_TTL_MINUTES) and scope_ok and month_ok and year_ok:
                    cached = row[0]
                    packet = cached if isinstance(cached, dict) else json.loads(cached)
                    packet["user_id"] = user_id
                    return merge_session_upload_into_packet(packet, session_id)
        except Exception as e:
            _log.warning("[ai_context] cache read failed: %s", e)
        finally:
            try:
                cur.close()
            except Exception:
                pass
            conn.close()

    packet = build_context_packet(
        user_id,
        session_id=session_id,
        dashboard_scope=mode,
        context_month=month,
        context_year=year,
    )

    if session_id:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE ai_sessions
                SET cached_context = %s::jsonb,
                    context_built_at = NOW(),
                    cache_dashboard_scope = %s,
                    cache_context_month = %s,
                    cache_context_year = %s
                WHERE id = %s::uuid AND user_id = %s
                """,
                (
                    json.dumps(packet, default=str),
                    mode,
                    month,
                    year,
                    session_id,
                    user_id,
                ),
            )
            conn.commit()
        except Exception as e:
            _log.warning("[ai_context] cache write failed: %s", e)
        finally:
            try:
                cur.close()
            except Exception:
                pass
            conn.close()

    return merge_session_upload_into_packet(packet, session_id)


def build_context_packet(
    user_id: int,
    session_id: str | None = None,
    dashboard_scope: str = "merged",
    context_month: int | None = None,
    context_year: int | None = None,
) -> dict[str, Any]:
    """
    Fetch scoped, month-aware data for the AI chatbot.

    dashboard_scope: bank_only | credit_card_only | merged
    context_month/year: month being viewed on dashboard (defaults to current)
    """
    now = datetime.now()
    month = int(context_month or now.month)
    year = int(context_year or now.year)
    mode = normalize_dashboard_mode(dashboard_scope)
    scope = transaction_scope_sql("t", mode)
    last_day = calendar.monthrange(year, month)[1]
    period_label = f"{calendar.month_name[month]} {year}"

    conn = get_connection()
    cur = None
    try:
        cur = conn.cursor()

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

        connected_sources = _fetch_connected_sources(cur, user_id)
        linked_accounts: list[dict] = [
            {
                "bank": s["institution_name"],
                "source_type": s.get("source_type"),
                "status": s.get("status", "active"),
            }
            for s in connected_sources
        ]

        recent_txns: list[dict] = []
        try:
            cur.execute(
                f"""
                SELECT merchant, category, amount, transaction_date, type,
                       COALESCE(document_origin, 'linked_bank') AS data_source
                FROM transactions t
                WHERE t.user_id = %s
                  AND EXTRACT(MONTH FROM t.transaction_date)::int = %s
                  AND EXTRACT(YEAR FROM t.transaction_date)::int = %s
                  AND ({scope})
                ORDER BY transaction_date DESC
                LIMIT 50
                """,
                (user_id, month, year),
            )
            for r in cur.fetchall():
                recent_txns.append({
                    "merchant": r[0],
                    "category": r[1],
                    "amount": float(r[2] or 0),
                    "date": str(r[3]),
                    "type": r[4],
                    "source": r[5] or "linked_bank",
                })
        except Exception as e:
            _rollback_conn(conn)
            _log.warning("[ai_context] transactions fetch error: %s", e)

        monthly_summary: dict = {}
        try:
            cur.execute(
                f"""
                SELECT
                    COALESCE(SUM(CASE WHEN t.type = 'CREDIT' THEN t.amount ELSE 0 END), 0)::float,
                    COALESCE(SUM(CASE WHEN t.type = 'DEBIT' THEN t.amount ELSE 0 END), 0)::float
                FROM transactions t
                WHERE t.user_id = %s
                  AND EXTRACT(MONTH FROM t.transaction_date)::int = %s
                  AND EXTRACT(YEAR FROM t.transaction_date)::int = %s
                  AND ({scope})
                """,
                (user_id, month, year),
            )
            inc, exp = cur.fetchone() or (0, 0)
            total_income = float(inc or 0)
            total_expense = float(exp or 0)
            savings = total_income - total_expense
            savings_rate = (
                round(savings / total_income * 100, 2) if total_income > 0 else 0.0
            )

            categories: dict[str, float] = {}
            cur.execute(
                f"""
                SELECT COALESCE(category, 'Other') AS cat,
                       COALESCE(SUM(t.amount), 0)::float
                FROM transactions t
                WHERE t.user_id = %s
                  AND t.type = 'DEBIT'
                  AND EXTRACT(MONTH FROM t.transaction_date)::int = %s
                  AND EXTRACT(YEAR FROM t.transaction_date)::int = %s
                  AND ({scope})
                GROUP BY COALESCE(category, 'Other')
                ORDER BY 2 DESC
                LIMIT 12
                """,
                (user_id, month, year),
            )
            for r in cur.fetchall():
                categories[str(r[0])] = float(r[1] or 0)

            monthly_summary = {
                "income": total_income,
                "expense": total_expense,
                "savings": savings,
                "savings_rate": savings_rate,
                "categories": categories,
                "period": f"{year}-{month:02d}",
                "period_label": period_label,
            }
        except Exception as e:
            _rollback_conn(conn)
            _log.warning("[ai_context] monthly_summary compute error: %s", e)

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
                WHERE user_id = %s AND is_active IS TRUE
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

    return {
        "user_id": user_id,
        "user": user_data,
        "linked_accounts": linked_accounts,
        "monthly_summary": monthly_summary,
        "recent_transactions": recent_txns,
        "active_emis": active_emis,
        "subscriptions": subscriptions,
        "uploaded_documents": uploaded_docs,
        "dashboard_scope": mode,
        "context_month": month,
        "context_year": year,
        "period_label": period_label,
        "app_features": [
            {"name": "EMI Tracker", "route": "/emi-tracker", "tab": "emi",
             "description": "Track all EMIs, due dates, lenders"},
            {"name": "Subscriptions AI", "route": "/subscriptions-ai", "tab": "subscriptions",
             "description": "Manage recurring subscriptions"},
            {"name": "FraudShield", "route": "/fraud-shield", "tab": "fraud",
             "description": "Detect suspicious transactions"},
            {"name": "Transactions", "route": "/transactions", "tab": "transactions",
             "description": "Full transaction history"},
            {"name": "Trip Planner", "route": "/trip-planner", "tab": "trip-planner",
             "description": "Plan trips within your budget"},
            {"name": "AI Insights", "route": "/insights", "tab": "insights",
             "description": "Full financial analysis"},
        ],
    }
