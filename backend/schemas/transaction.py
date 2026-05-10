"""Transaction Pydantic schemas for the Phase 1 inline-scoring endpoint.

Phase 1: Real-time event-driven scoring.
Dependencies: pydantic v2.

TransactionIn  — what the client POSTS to create a transaction.
TransactionOut — what the server returns, including ML risk fields.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class TransactionIn(BaseModel):
    """Input model for POST /api/transactions.

    All fields match the existing `transactions` table schema so there is no
    impedance mismatch at the DB write step.  Optional fields default to
    sensible values so the endpoint works without a fully-instrumented client.
    """

    user_id: Annotated[int, Field(gt=0, description="FK to users table")]

    transaction_date: date = Field(
        default_factory=lambda: datetime.now(timezone.utc).date(),
        description="ISO date YYYY-MM-DD",
    )
    transaction_time: Optional[time] = Field(
        default=None,
        description="HH:MM:SS — defaults to current UTC time if omitted",
    )

    amount: Annotated[float, Field(gt=0, description="Positive INR amount")]
    type: Literal["DEBIT", "CREDIT"] = "DEBIT"

    merchant: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=500)
    category: Optional[str] = Field(default=None, max_length=100)
    payment_method: Optional[str] = Field(default="UPI", max_length=50)
    location: Optional[str] = Field(default=None, max_length=255)

    balance_after: Optional[float] = Field(
        default=None,
        description="Account balance after this transaction (used in risk features)",
    )

    # Device / network signals — optional, used in later phases
    device_id: Optional[str] = Field(default=None, max_length=128)
    ip_address: Optional[str] = Field(default=None, max_length=45)

    @field_validator("type", mode="before")
    @classmethod
    def _uppercase_type(cls, v: str) -> str:
        return str(v).upper().strip()

    @model_validator(mode="after")
    def _set_time_default(self) -> "TransactionIn":
        if self.transaction_time is None:
            self.transaction_time = datetime.now(timezone.utc).time().replace(
                second=0, microsecond=0
            )
        return self

    def to_feature_dict(self) -> dict:
        """Flatten to a plain dict suitable for ML feature extraction."""
        dt_combined = datetime.combine(self.transaction_date, self.transaction_time)
        return {
            "amount": self.amount,
            "type": self.type,
            "category": self.category,
            "merchant": self.merchant or "",
            "hour_of_day": dt_combined.hour,
            "day_of_week": dt_combined.weekday(),
            "is_weekend": dt_combined.weekday() >= 5,
            "is_night_txn": dt_combined.hour >= 23 or dt_combined.hour <= 5,
            "transaction_date": self.transaction_date,
            "transaction_time": self.transaction_time,
            "balance_after": self.balance_after,
            "payment_method": self.payment_method,
            "location": self.location or "",
        }


class TransactionOut(BaseModel):
    """Response returned by POST /api/transactions after inline scoring.

    The risk fields are always populated (never null) because scoring happens
    synchronously before the DB write.  Downstream UI can rely on this.
    """

    id: int
    user_id: int
    transaction_date: date
    transaction_time: time
    amount: float
    type: str
    merchant: Optional[str] = None
    category: Optional[str] = None
    payment_method: Optional[str] = None

    # Risk fields — always populated
    risk_score: int = Field(ge=0, le=100)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    anomaly_flag: bool
    anomaly_reason: Optional[str] = None

    # Scoring metadata
    action: Literal["accepted", "review", "challenge", "blocked"] = "accepted"
    detector_version: str
    scoring_latency_ms: float

    # Explanation (populated in Phase 7; stub here)
    explanation: Optional[dict] = None
