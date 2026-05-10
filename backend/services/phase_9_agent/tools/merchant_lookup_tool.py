"""MerchantLookupTool — derive merchant reputation from our own transaction
history.  We don't have a dedicated `merchants` table populated with rich
metadata, so the merchant 'reputation' is computed on demand: how many
users have used it, fraud rate, typical amount, location spread.
"""

from __future__ import annotations

import logging
from typing import Any

from core.db import get_pool
from services.phase_9_agent.tools.base_tool import BaseTool, ToolOutput

logger = logging.getLogger(__name__)


class MerchantLookupTool(BaseTool):
    name = "search_merchant_db"
    description = (
        "Look up reputation stats for a merchant by name.  Returns total "
        "transactions, distinct users who have transacted, fraud rate, "
        "average amount, and a short list of locations the merchant operates in. "
        "Use this to decide if a merchant is established / new / suspicious."
    )

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "merchant_name": {
                    "type": "string",
                    "description": "Exact merchant string (case-insensitive match)",
                },
            },
            "required": ["merchant_name"],
        }

    async def execute(self, input_data: dict[str, Any]) -> ToolOutput:
        merchant = (input_data.get("merchant_name") or "").strip()
        if not merchant:
            return ToolOutput(success=False, error="merchant_name is required")

        try:
            pool = get_pool()
        except RuntimeError as exc:
            return ToolOutput(success=False, error=f"db_unavailable: {exc}")

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*)                                           AS total_txns,
                        COUNT(DISTINCT user_id)                            AS unique_users,
                        AVG(amount)::float                                 AS avg_amount,
                        MIN(amount)::float                                 AS min_amount,
                        MAX(amount)::float                                 AS max_amount,
                        SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END)          AS fraud_count,
                        AVG(risk_score)::float                             AS avg_risk_score,
                        MIN(transaction_date)                              AS first_seen,
                        MAX(transaction_date)                              AS last_seen
                    FROM transactions
                    WHERE LOWER(merchant) = LOWER($1)
                    """,
                    merchant,
                )
                locations = await conn.fetch(
                    """
                    SELECT location, COUNT(*) AS c
                    FROM transactions
                    WHERE LOWER(merchant) = LOWER($1) AND location IS NOT NULL
                    GROUP BY location
                    ORDER BY c DESC
                    LIMIT 5
                    """,
                    merchant,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("merchant_lookup_tool query failed: %s", exc)
            return ToolOutput(success=False, error=f"query_failed: {exc}")

        total = int(row["total_txns"] or 0)
        if total == 0:
            return ToolOutput(
                success=True,
                data={
                    "merchant": merchant,
                    "known": False,
                    "reputation": "unknown",
                    "note": "no_prior_history",
                },
            )

        fraud_rate = (int(row["fraud_count"] or 0) / total) if total else 0.0
        if fraud_rate >= 0.10 or (row["avg_risk_score"] or 0) >= 70:
            reputation = "suspicious"
        elif fraud_rate >= 0.02 or (row["avg_risk_score"] or 0) >= 50:
            reputation = "watch"
        else:
            reputation = "established"

        return ToolOutput(
            success=True,
            data={
                "merchant": merchant,
                "known": True,
                "reputation": reputation,
                "total_txns": total,
                "unique_users": int(row["unique_users"] or 0),
                "avg_amount": round(float(row["avg_amount"] or 0.0), 2),
                "min_amount": round(float(row["min_amount"] or 0.0), 2),
                "max_amount": round(float(row["max_amount"] or 0.0), 2),
                "fraud_count": int(row["fraud_count"] or 0),
                "fraud_rate": round(fraud_rate, 4),
                "avg_risk_score": round(float(row["avg_risk_score"] or 0.0), 1),
                "first_seen": str(row["first_seen"]) if row["first_seen"] else None,
                "last_seen": str(row["last_seen"]) if row["last_seen"] else None,
                "top_locations": [
                    {"location": r["location"], "count": int(r["c"])} for r in locations
                ],
            },
        )
