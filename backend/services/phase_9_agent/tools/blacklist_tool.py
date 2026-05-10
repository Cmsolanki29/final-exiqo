"""BlacklistTool — entity blacklist lookup.

Two layers:
  1. **Static seed list** — small in-memory set of known scam vendors / VPAs
     for cold-start.  Hand-curated; expand as we learn.
  2. **Dynamic table** — if a `risk_blacklist` table exists, we use it.
     Otherwise we silently fall through.

We deliberately *don't* hard-fail on a missing dynamic table: the tool
must keep working even before a security analyst has populated one.
"""

from __future__ import annotations

import logging
from typing import Any

from core.db import get_pool
from services.phase_9_agent.tools.base_tool import BaseTool, ToolOutput

logger = logging.getLogger(__name__)


_STATIC_BLACKLIST: dict[str, dict[str, str]] = {
    # merchant string  ->  metadata
    "fake-kyc-update":            {"reason": "kyc_update_scam",      "severity": "high"},
    "winner-claim-prize":         {"reason": "lottery_prize_scam",   "severity": "high"},
    "instant-loan-app-anonymous": {"reason": "loan_app_extortion",   "severity": "medium"},
    "anydesk-support":            {"reason": "fake_refund_scam",     "severity": "high"},
    "crypto-doubler":             {"reason": "investment_scam",      "severity": "high"},
}


class BlacklistTool(BaseTool):
    name = "lookup_blacklist"
    description = (
        "Check whether a merchant or VPA appears on either our hand-curated "
        "static blacklist or the dynamic risk_blacklist table.  Returns "
        "blacklist hits with reason and severity."
    )

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "entity": {
                    "type": "string",
                    "description": "Merchant name, VPA, or any string identifier to check",
                },
            },
            "required": ["entity"],
        }

    async def execute(self, input_data: dict[str, Any]) -> ToolOutput:
        entity = (input_data.get("entity") or "").strip()
        if not entity:
            return ToolOutput(success=False, error="entity is required")

        normalised = entity.lower()
        hits: list[dict[str, Any]] = []

        # Static layer — substring match so we catch decorated variants.
        for key, meta in _STATIC_BLACKLIST.items():
            if key in normalised or normalised in key:
                hits.append({
                    "source": "static",
                    "match": key,
                    "reason": meta["reason"],
                    "severity": meta["severity"],
                })

        # Dynamic layer — best-effort.
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                # Probe table existence so we don't error when it isn't there.
                exists = await conn.fetchval(
                    "SELECT to_regclass('public.risk_blacklist')",
                )
                if exists:
                    rows = await conn.fetch(
                        """
                        SELECT entity, reason, severity
                        FROM risk_blacklist
                        WHERE LOWER(entity) = LOWER($1)
                        """,
                        entity,
                    )
                    for r in rows:
                        hits.append({
                            "source": "dynamic",
                            "match": r["entity"],
                            "reason": r["reason"],
                            "severity": r["severity"],
                        })
        except Exception as exc:  # noqa: BLE001
            logger.debug("blacklist dynamic layer skipped: %s", exc)

        return ToolOutput(
            success=True,
            data={
                "entity": entity,
                "blacklisted": bool(hits),
                "hits": hits,
                "static_size": len(_STATIC_BLACKLIST),
            },
        )
