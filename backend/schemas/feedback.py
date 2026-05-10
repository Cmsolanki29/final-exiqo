"""Pydantic schemas for the Phase 8 feedback flywheel.

Phase 8: Feedback Flywheel.
Dependencies: pydantic v2.

Models:
  FeedbackIn        — user-facing fraud report body.
  ChargebackIn      — chargeback webhook payload.
  ReviewDecision    — analyst resolution body.
  ReviewQueueItem   — response model for review queue entries.
  ReviewQueueDetail — response model for detailed queue item view (admin).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class FeedbackIn(BaseModel):
    """User-facing fraud report.

    Used by POST /api/transactions/{id}/report-fraud.
    The transaction_id is taken from the path param, so it is optional
    here (populated by the route handler before passing to FeedbackService).
    """

    transaction_id: Optional[int] = Field(
        default=None,
        description="Transaction primary key.  Set from path param by route handler.",
    )
    label: bool = Field(
        description="True = user believes this is fraud; False = user disputes a fraud flag.",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional user-provided context (e.g. 'I did not make this purchase').",
    )


class ChargebackIn(BaseModel):
    """Chargeback webhook payload from payment processor.

    The shape is intentionally generic; real processors (Visa, Mastercard,
    Razorpay) have proprietary formats.  Map their fields here before calling
    FeedbackService.record_chargeback().
    """

    transaction_id: int = Field(description="Internal transaction PK that was charged back.")
    dispute_id: str = Field(description="External processor dispute/chargeback ID.")
    reason_code: Optional[str] = Field(
        default=None,
        description="Processor reason code (e.g. 'UA02', '4853').",
    )
    amount: Optional[float] = Field(default=None, description="Disputed amount.")
    currency: Optional[str] = Field(default="INR")


class ReviewDecision(BaseModel):
    """Analyst resolution of a review queue item.

    Used by POST /api/admin/review-queue/{id}/decide.
    """

    queue_id: Optional[UUID] = Field(
        default=None,
        description="Set from path param by route handler.",
    )
    resolution: Literal["fraud", "legitimate", "inconclusive"] = Field(
        description="Analyst determination.",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Analyst notes; required when resolution='inconclusive'.",
    )


class ReviewQueueItem(BaseModel):
    """Summary of a review queue entry (used in paginated list response)."""

    id: UUID
    transaction_id: int
    score: int
    status: Literal["pending", "in_review", "resolved"]
    priority: Literal["low", "normal", "high"]
    assigned_to: Optional[UUID]
    resolution: Optional[Literal["fraud", "legitimate", "inconclusive"]]
    created_at: datetime
    resolved_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ReviewQueueDetail(ReviewQueueItem):
    """Full detail of a review queue entry (admin detail view)."""

    decision: dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    assigned_at: Optional[datetime] = None
