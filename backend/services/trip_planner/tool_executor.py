"""
Trip Planner › Tool dispatcher.

Internal finance tools run in-process. Travel tools prefer the Travel Intelligence
MCP server; on subprocess failure they fall back to the same Python modules directly.
"""
from __future__ import annotations

import logging
from typing import Any

from .budget_optimizer import budget_optimizer
from .financial_context import get_user_financial_context
from .flight_search import search_flights
from .hotel_search import search_hotels
from .mcp_client import get_travel_mcp_client
from .places_explorer import explore_places
from .saving_projection import project_future_savings
from .tool_definitions import INTERNAL_TOOL_NAMES, TRAVEL_TOOL_NAMES
from .weather_engine import get_weather_for_destination

_log = logging.getLogger(__name__)


def _execute_travel_direct(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    args = args or {}
    if tool_name == "get_weather_for_destination":
        out = get_weather_for_destination(
            destination=str(args.get("destination") or "").strip(),
            month=(str(args.get("month")).strip() if args.get("month") else None),
        )
    elif tool_name == "search_flights":
        out = search_flights(
            origin=str(args.get("origin") or "").strip(),
            destination=str(args.get("destination") or "").strip(),
            departure_date=str(args.get("departure_date") or "").strip(),
            travelers=int(args.get("travelers") or 1),
        )
    elif tool_name == "search_hotels":
        out = search_hotels(
            destination=str(args.get("destination") or "").strip(),
            check_in=str(args.get("check_in") or "").strip(),
            nights=int(args.get("nights") or 1),
            guests=int(args.get("guests") or 2),
        )
    elif tool_name == "explore_places":
        user_city = args.get("user_city")
        out = explore_places(
            location=str(args.get("location") or "").strip(),
            category=str(args.get("category") or "attractions").strip(),
            user_city=str(user_city).strip() if user_city else None,
        )
    else:
        return {"error": f"unknown_tool:{tool_name}", "fallback": True}

    if isinstance(out, dict):
        tagged = dict(out)
        tagged.setdefault("data_source", f"{tool_name}_direct")
        return tagged
    return {"result": out, "data_source": f"{tool_name}_direct"}


def execute_tool_call(
    tool_name: str,
    args: dict[str, Any],
    user_id: int,
    *,
    mcp_active: bool = False,
) -> tuple[dict[str, Any], bool]:
    """
    Run a tool and return (result_dict, via_mcp).
    via_mcp is True only when the travel MCP subprocess handled the call.
    """
    args = args or {}
    try:
        if tool_name in INTERNAL_TOOL_NAMES:
            return _execute_internal(tool_name, args, user_id), False

        if tool_name in TRAVEL_TOOL_NAMES:
            if mcp_active:
                client = get_travel_mcp_client()
                if client.is_available() and tool_name in client.tool_names:
                    try:
                        return client.call_tool_sync(tool_name, args), True
                    except Exception as exc:  # noqa: BLE001
                        _log.warning(
                            "[trip-planner] MCP call '%s' failed (%s) — using direct module",
                            tool_name,
                            exc,
                        )
            return _execute_travel_direct(tool_name, args), False

        return {"error": f"unknown_tool:{tool_name}", "fallback": True}, False

    except Exception as exc:  # noqa: BLE001
        _log.exception("[trip-planner] tool '%s' raised: %s", tool_name, exc)
        return (
            {
                "tool": tool_name,
                "error": f"{type(exc).__name__}: {exc}"[:200],
                "fallback": True,
                "note": "Provider error — continue with general knowledge for this step.",
            },
            False,
        )


def _execute_internal(tool_name: str, args: dict[str, Any], user_id: int) -> dict[str, Any]:
    if tool_name == "get_user_financial_context":
        return get_user_financial_context(user_id)

    if tool_name == "budget_optimizer":
        return budget_optimizer(
            user_id=user_id,
            flight_cost=float(args.get("flight_cost") or 0),
            hotel_cost_per_night=float(args.get("hotel_cost_per_night") or 0),
            nights=int(args.get("nights") or 1),
            travelers=int(args.get("travelers") or 1),
            daily_food_budget=float(args.get("daily_food_budget") or 800),
            local_transport=float(args.get("local_transport") or 3000),
            activities_budget=float(args.get("activities_budget") or 5000),
            buffer_percentage=float(args.get("buffer_percentage") or 15),
        )

    if tool_name == "project_future_savings":
        return project_future_savings(
            user_id=user_id,
            months_ahead=int(args.get("months_ahead") or 0),
        )

    return {"error": f"unknown_tool:{tool_name}", "fallback": True}


__all__ = ["execute_tool_call"]
