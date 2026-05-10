"""Feedback flywheel routes — user reports, chargeback webhooks, analyst review queue.

Phase 8: Feedback Flywheel.
Dependencies: FeedbackService (Phase 8), asyncpg pool (Phase 1),
              admin auth via X-Admin-Token (Phase 4), JWT auth for user endpoints.
Performance budget:
  POST /report-fraud      < 100ms
  POST /webhooks/chargeback < 100ms
  GET  /admin/review-queue  < 50ms

Endpoints:
  POST /api/transactions/{id}/report-fraud    — user-facing fraud report.
  POST /api/webhooks/chargeback               — payment processor webhook.
  GET  /api/admin/review-queue                — paginated analyst queue.
  GET  /api/admin/review-queue/{id}           — detail with transaction context.
  POST /api/admin/review-queue/{id}/decide    — analyst resolution.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from schemas.feedback import (
    ChargebackIn,
    FeedbackIn,
    ReviewDecision,
    ReviewQueueDetail,
    ReviewQueueItem,
)

logger = logging.getLogger(__name__)

# Two sub-routers so we can apply different prefixes/auth
router = APIRouter(tags=["feedback"])


# ------------------------------------------------------------------ #
# Auth dependencies
# ------------------------------------------------------------------ #

async def _get_current_user_id(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> int:
    """Extract user ID from Bearer JWT token.

    Minimal implementation: decodes the JWT using the existing auth module.
    Returns 401 if token is missing or invalid.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization[7:]
    try:
        from db import get_db
        import psycopg2
        from jose import jwt, JWTError
        import os
        SECRET_KEY = os.getenv("SECRET_KEY", "smartspend-secret-key-2024")
        ALGORITHM = "HS256"
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return int(user_id)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Token validation failed: {exc}") from exc


def _require_admin(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> None:
    """Verify the X-Admin-Token header.  Raises 403 if invalid."""
    import os
    expected = os.getenv("ADMIN_TOKEN", "dev-admin-secret")
    if x_admin_token != expected:
        raise HTTPException(
            status_code=403, detail="Invalid or missing X-Admin-Token header"
        )


def _require_webhook_auth(
    x_webhook_secret: Optional[str] = Header(default=None, alias="X-Webhook-Secret"),
) -> None:
    """Verify the X-Webhook-Secret header for payment processor webhooks."""
    import os
    expected = os.getenv("WEBHOOK_SECRET", "dev-webhook-secret")
    if x_webhook_secret != expected:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")


# ------------------------------------------------------------------ #
# User-facing: fraud report
# ------------------------------------------------------------------ #

@router.post("/transactions/{txn_id}/report-fraud")
async def report_fraud(
    txn_id: int,
    body: FeedbackIn,
    user_id: int = Depends(_get_current_user_id),
) -> dict[str, Any]:
    """Report a transaction as fraudulent (or dispute a fraud flag).

    Called by the end-user from the SmartSpend mobile/web app.
    - If label=True:  marks the transaction as fraud, triggers auto-remediation.
    - If label=False: clears the fraud flag (user disputing an ML decision).

    Authentication: Bearer JWT token (standard user session).

    Args:
        txn_id: Transaction primary key (path param).
        body:   FeedbackIn with label and optional notes.

    Returns:
        Acknowledgement with txn_id and label recorded.
    """
    from services.feedback.feedback_service import feedback_service

    body.transaction_id = txn_id
    await feedback_service.record_user_report(
        user_id=user_id,
        txn_id=txn_id,
        label=body.label,
        notes=body.notes,
    )
    return {
        "acknowledged": True,
        "transaction_id": txn_id,
        "label_recorded": body.label,
        "message": (
            "Transaction flagged as fraud. Thank you for reporting."
            if body.label
            else "Flag removed. Transaction marked as legitimate."
        ),
    }


# ------------------------------------------------------------------ #
# Webhook: chargeback ingestion
# ------------------------------------------------------------------ #

@router.post("/webhooks/chargeback", dependencies=[Depends(_require_webhook_auth)])
async def chargeback_webhook(body: ChargebackIn) -> dict[str, Any]:
    """Receive a chargeback notification from a payment processor.

    Auth: X-Webhook-Secret header (shared secret from payment processor config).
    In production, validate HMAC-SHA256 signature provided by the processor.

    Args:
        body: ChargebackIn with transaction_id and dispute_id.

    Returns:
        Acknowledgement dict.
    """
    from services.feedback.feedback_service import feedback_service

    await feedback_service.record_chargeback(
        txn_id=body.transaction_id,
        dispute_id=body.dispute_id,
        reason_code=body.reason_code,
    )
    return {
        "acknowledged": True,
        "transaction_id": body.transaction_id,
        "dispute_id": body.dispute_id,
    }


# ------------------------------------------------------------------ #
# Admin: review queue
# ------------------------------------------------------------------ #

@router.get("/admin/review-queue", dependencies=[Depends(_require_admin)])
async def list_review_queue(
    status: Optional[str] = Query(default=None, description="Filter by status"),
    priority: Optional[str] = Query(default=None, description="Filter by priority"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """Paginated list of review queue items for the analyst dashboard.

    Sorted by priority (high → normal → low) then by created_at DESC.

    Args:
        status:    Optional filter: 'pending' | 'in_review' | 'resolved'.
        priority:  Optional filter: 'low' | 'normal' | 'high'.
        page:      1-based page number.
        page_size: Items per page (1–100, default 20).

    Returns:
        Paginated response with items, total, page, page_size.
    """
    from core.db import get_pool

    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    offset = (page - 1) * page_size
    conditions: list[str] = []
    params: list[Any] = []
    idx = 1

    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    if priority:
        conditions.append(f"priority = ${idx}")
        params.append(priority)
        idx += 1

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    async with pool.acquire() as conn:
        total_row = await conn.fetchrow(
            f"SELECT COUNT(*) AS cnt FROM review_queue {where_clause}", *params
        )
        total = int(total_row["cnt"]) if total_row else 0

        rows = await conn.fetch(
            f"""
            SELECT id, transaction_id, score, status, priority,
                   assigned_to, resolution, created_at, resolved_at
            FROM   review_queue
            {where_clause}
            ORDER  BY
                CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,
                created_at DESC
            LIMIT  ${idx} OFFSET ${idx + 1}
            """,
            *params, page_size, offset,
        )

    items = [dict(r) for r in rows]
    return {
        "total":     total,
        "page":      page,
        "page_size": page_size,
        "items":     items,
    }


@router.get(
    "/admin/review-queue/{queue_id}",
    dependencies=[Depends(_require_admin)],
)
async def get_review_queue_item(queue_id: UUID) -> dict[str, Any]:
    """Full detail for a single review queue item.

    Includes:
      - The queue item itself (all columns)
      - The full transaction record
      - Last 5 transactions by this user (context)
      - The decision snapshot (SHAP explanation if available)

    Args:
        queue_id: review_queue.id UUID.

    Returns:
        Detail dict with queue_item, transaction, user_history, decision.
    """
    from core.db import get_pool

    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        rq = await conn.fetchrow(
            """
            SELECT id, transaction_id, score, decision, status, priority,
                   assigned_to, assigned_at, resolved_at, resolution, notes, created_at
            FROM   review_queue
            WHERE  id = $1
            """,
            queue_id,
        )
        if rq is None:
            raise HTTPException(status_code=404, detail=f"Queue item {queue_id} not found")

        txn_id = int(rq["transaction_id"])

        txn = await conn.fetchrow(
            """
            SELECT id, user_id, amount, merchant, category, payment_method,
                   risk_score, risk_level, anomaly_reason, is_fraud,
                   transaction_date, transaction_time, device_id, ip_address
            FROM   transactions
            WHERE  id = $1
            """,
            txn_id,
        )

        user_history: list[dict] = []
        if txn:
            history_rows = await conn.fetch(
                """
                SELECT id, amount, merchant, category, risk_score, risk_level,
                       is_fraud, transaction_date
                FROM   transactions
                WHERE  user_id = $1 AND id != $2
                ORDER  BY transaction_date DESC
                LIMIT  5
                """,
                int(txn["user_id"]), txn_id,
            )
            user_history = [dict(r) for r in history_rows]

    return {
        "queue_item":   dict(rq),
        "transaction":  dict(txn) if txn else None,
        "user_history": user_history,
    }


@router.post(
    "/admin/review-queue/{queue_id}/decide",
    dependencies=[Depends(_require_admin)],
)
async def decide_review_queue_item(
    queue_id: UUID,
    body: ReviewDecision,
    x_reviewer_id: Optional[str] = Header(
        default=None, alias="X-Reviewer-Id",
        description="Analyst UUID for audit trail",
    ),
) -> dict[str, Any]:
    """Record an analyst's resolution for a review queue item.

    Sets status='resolved', writes fraud_feedback, and updates
    transactions.is_fraud.  If resolution='fraud', triggers auto-remediation.

    Args:
        queue_id:      review_queue.id UUID.
        body:          ReviewDecision with resolution and optional notes.
        x_reviewer_id: Analyst UUID header for audit trail.

    Returns:
        Acknowledgement with resolution recorded.
    """
    from services.feedback.feedback_service import feedback_service

    reviewer_id: Optional[UUID] = None
    if x_reviewer_id:
        try:
            reviewer_id = UUID(x_reviewer_id)
        except ValueError:
            pass

    body.queue_id = queue_id
    await feedback_service.record_analyst_decision(
        queue_id=queue_id,
        resolution=body.resolution,
        reviewer_id=reviewer_id,
        notes=body.notes,
    )
    return {
        "acknowledged": True,
        "queue_id":     str(queue_id),
        "resolution":   body.resolution,
    }
