"""GeoVelocityTool — heuristic 'impossible travel' check.

We don't have lat/lon coordinates per location, so this is a coarse
location-velocity tool: it reports how often the user transacts in
which locations and whether the latest location is a sudden departure
from their pattern (new city + short interval since last txn).
"""

from __future__ import annotations

import logging
from typing import Any

from core.db import get_pool
from services.phase_9_agent.tools.base_tool import BaseTool, ToolOutput

logger = logging.getLogger(__name__)


class GeoVelocityTool(BaseTool):
    name = "check_geo_velocity"
    description = (
        "Analyse the user's location history to flag sudden geographic "
        "departures.  Returns the user's most-frequent locations, the "
        "fraction of activity in each, whether the latest location is "
        "novel, and the time gap between the latest two transactions."
    )

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer"},
                "current_location": {
                    "type": "string",
                    "description": "The location string of the flagged transaction",
                },
                "lookback_days": {"type": "integer", "default": 60, "minimum": 7, "maximum": 365},
            },
            "required": ["user_id"],
        }

    async def execute(self, input_data: dict[str, Any]) -> ToolOutput:
        try:
            user_id = int(input_data.get("user_id"))
        except (TypeError, ValueError):
            return ToolOutput(success=False, error="user_id must be an integer")
        current_loc = (input_data.get("current_location") or "").strip()
        lookback = max(7, min(int(input_data.get("lookback_days", 60) or 60), 365))

        try:
            pool = get_pool()
        except RuntimeError as exc:
            return ToolOutput(success=False, error=f"db_unavailable: {exc}")

        try:
            async with pool.acquire() as conn:
                # Top locations
                rows = await conn.fetch(
                    """
                    SELECT location, COUNT(*) AS c
                    FROM transactions
                    WHERE user_id = $1
                      AND location IS NOT NULL
                      AND transaction_date >= CURRENT_DATE - ($2::int) * INTERVAL '1 day'
                    GROUP BY location
                    ORDER BY c DESC
                    LIMIT 10
                    """,
                    user_id, lookback,
                )
                # Last two transactions for velocity
                last_two = await conn.fetch(
                    """
                    SELECT location, transaction_date, transaction_time
                    FROM transactions
                    WHERE user_id = $1
                    ORDER BY transaction_date DESC, transaction_time DESC NULLS LAST
                    LIMIT 2
                    """,
                    user_id,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("geo_velocity_tool query failed: %s", exc)
            return ToolOutput(success=False, error=f"query_failed: {exc}")

        total = sum(int(r["c"]) for r in rows)
        location_freq = [
            {"location": r["location"], "count": int(r["c"]),
             "share": round(int(r["c"]) / total, 3) if total else 0.0}
            for r in rows
        ]
        known_locations = {r["location"] for r in rows}
        is_new_location = bool(current_loc) and current_loc not in known_locations

        time_gap_seconds: int | None = None
        if len(last_two) == 2:
            from datetime import datetime, time as dt_time
            def _stamp(r: Any) -> datetime | None:
                if not r["transaction_date"]:
                    return None
                t = r["transaction_time"] or dt_time(0, 0, 0)
                return datetime.combine(r["transaction_date"], t)
            a, b = _stamp(last_two[0]), _stamp(last_two[1])
            if a and b:
                time_gap_seconds = int((a - b).total_seconds())

        # Heuristic risk hint
        velocity_flag = "ok"
        if is_new_location and (time_gap_seconds is not None and time_gap_seconds < 3600):
            velocity_flag = "suspicious_new_location_short_interval"
        elif is_new_location:
            velocity_flag = "new_location"

        return ToolOutput(
            success=True,
            data={
                "user_id": user_id,
                "lookback_days": lookback,
                "total_txns_in_window": total,
                "current_location": current_loc or None,
                "is_new_location": is_new_location,
                "velocity_flag": velocity_flag,
                "time_gap_to_previous_seconds": time_gap_seconds,
                "top_locations": location_freq,
            },
        )
