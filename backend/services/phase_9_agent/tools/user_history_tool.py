"""UserHistoryTool — fetch the user's recent transactions for context."""

from __future__ import annotations

import logging
from typing import Any

from core.db import get_pool
from services.phase_9_agent.tools.base_tool import BaseTool, ToolOutput

logger = logging.getLogger(__name__)


class UserHistoryTool(BaseTool):
    name = "get_user_history"
    description = (
        "Fetch the user's most recent transactions to understand their normal "
        "spending pattern.  Returns amount, merchant, category, timestamp, "
        "risk_score, and is_fraud flag for each.  Useful to compare the flagged "
        "transaction against the user's baseline."
    )

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Internal user ID (integer)",
                },
                "limit": {
                    "type": "integer",
                    "description": "How many recent transactions to return (1-50)",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": ["user_id"],
        }

    async def execute(self, input_data: dict[str, Any]) -> ToolOutput:
        try:
            user_id = int(input_data.get("user_id"))
        except (TypeError, ValueError):
            return ToolOutput(success=False, error="user_id must be an integer")
        limit = max(1, min(int(input_data.get("limit", 20) or 20), 50))

        try:
            pool = get_pool()
        except RuntimeError as exc:
            return ToolOutput(success=False, error=f"db_unavailable: {exc}")

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, amount, merchant, category, transaction_date,
                           transaction_time, location, risk_score, is_fraud,
                           type, payment_method, anomaly_flag
                    FROM transactions
                    WHERE user_id = $1
                    ORDER BY transaction_date DESC, transaction_time DESC NULLS LAST
                    LIMIT $2
                    """,
                    user_id,
                    limit,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("user_history_tool query failed: %s", exc)
            return ToolOutput(success=False, error=f"query_failed: {exc}")

        items = [
            {
                "id": int(r["id"]),
                "amount": float(r["amount"]) if r["amount"] is not None else None,
                "merchant": r["merchant"],
                "category": r["category"],
                "date": str(r["transaction_date"]) if r["transaction_date"] else None,
                "time": str(r["transaction_time"]) if r["transaction_time"] else None,
                "location": r["location"],
                "risk_score": int(r["risk_score"]) if r["risk_score"] is not None else None,
                "is_fraud": bool(r["is_fraud"]) if r["is_fraud"] is not None else None,
                "type": r["type"],
                "payment_method": r["payment_method"],
                "anomaly": bool(r["anomaly_flag"]) if r["anomaly_flag"] is not None else None,
            }
            for r in rows
        ]

        amounts = [it["amount"] for it in items if it["amount"] is not None]
        summary = {
            "count": len(items),
            "avg_amount": round(sum(amounts) / len(amounts), 2) if amounts else 0.0,
            "max_amount": max(amounts) if amounts else 0.0,
            "min_amount": min(amounts) if amounts else 0.0,
            "fraud_in_history": sum(1 for it in items if it["is_fraud"]),
        }

        return ToolOutput(success=True, data={"summary": summary, "transactions": items})
