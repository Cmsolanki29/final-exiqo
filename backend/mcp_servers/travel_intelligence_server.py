"""
Travel Intelligence MCP server (stdio).

Exposes weather, flights, hotels, and places tools to the Trip Planner agent via
real MCP list_tools / call_tool — implementations delegate to existing modules.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Ensure `backend/` is on sys.path when launched as a script.
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from services.trip_planner.flight_search import search_flights
from services.trip_planner.hotel_search import search_hotels
from services.trip_planner.places_explorer import explore_places
from services.trip_planner.weather_engine import get_weather_for_destination

_log = logging.getLogger("travel-intelligence-mcp")

server = Server("travel-intelligence")

_TOOLS: list[types.Tool] = [
    types.Tool(
        name="get_weather_for_destination",
        description=(
            "Returns current weather + 5-day forecast for the destination, plus India-specific "
            "seasonal hints. Use this to advise on timing and the best month."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "destination": {
                    "type": "string",
                    "description": "City or region name, e.g. 'Kashmir', 'Goa', 'Bangkok'.",
                },
                "month": {
                    "type": "string",
                    "description": "Optional month the user is considering, e.g. 'December'.",
                },
            },
            "required": ["destination"],
        },
    ),
    types.Tool(
        name="search_flights",
        description=(
            "Searches real flight options. Returns offer prices in INR. If credentials are "
            "missing the result has fallback: true — estimate from general market knowledge."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Origin city."},
                "destination": {"type": "string"},
                "departure_date": {"type": "string", "description": "YYYY-MM-DD"},
                "travelers": {"type": "integer", "minimum": 1, "default": 1},
            },
            "required": ["origin", "destination", "departure_date"],
        },
    ),
    types.Tool(
        name="search_hotels",
        description="Searches hotels for the destination. Returns budget / mid / luxury samples in INR per night.",
        inputSchema={
            "type": "object",
            "properties": {
                "destination": {"type": "string"},
                "check_in": {"type": "string", "description": "YYYY-MM-DD"},
                "nights": {"type": "integer", "minimum": 1},
                "guests": {"type": "integer", "minimum": 1, "default": 2},
            },
            "required": ["destination", "check_in", "nights"],
        },
    ),
    types.Tool(
        name="explore_places",
        description=(
            "Finds real attractions / food / activities at a destination, OR cheaper destinations "
            "near the user's home city when category = alternatives_nearby."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "location": {"type": "string"},
                "category": {
                    "type": "string",
                    "enum": ["attractions", "alternatives_nearby", "food", "activities"],
                },
                "user_city": {
                    "type": "string",
                    "description": "Required when category = alternatives_nearby.",
                },
            },
            "required": ["location", "category"],
        },
    ),
]


def _tag(payload: dict[str, Any], tool_name: str) -> dict[str, Any]:
    out = dict(payload)
    out["data_source"] = f"{tool_name}_via_mcp"
    return out


def _run_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    args = arguments or {}
    if name == "get_weather_for_destination":
        return _tag(
            get_weather_for_destination(
                destination=str(args.get("destination") or "").strip(),
                month=(str(args.get("month")).strip() if args.get("month") else None),
            ),
            name,
        )
    if name == "search_flights":
        return _tag(
            search_flights(
                origin=str(args.get("origin") or "").strip(),
                destination=str(args.get("destination") or "").strip(),
                departure_date=str(args.get("departure_date") or "").strip(),
                travelers=int(args.get("travelers") or 1),
            ),
            name,
        )
    if name == "search_hotels":
        return _tag(
            search_hotels(
                destination=str(args.get("destination") or "").strip(),
                check_in=str(args.get("check_in") or "").strip(),
                nights=int(args.get("nights") or 1),
                guests=int(args.get("guests") or 2),
            ),
            name,
        )
    if name == "explore_places":
        user_city = args.get("user_city")
        return _tag(
            explore_places(
                location=str(args.get("location") or "").strip(),
                category=str(args.get("category") or "attractions").strip(),
                user_city=str(user_city).strip() if user_city else None,
            ),
            name,
        )
    return {"error": f"unknown_tool:{name}", "fallback": True}


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return _TOOLS


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
    try:
        payload = _run_tool(name, arguments)
        return [types.TextContent(type="text", text=json.dumps(payload, default=str, ensure_ascii=False))]
    except Exception as exc:  # noqa: BLE001
        _log.exception("tool %s failed: %s", name, exc)
        err = {
            "tool": name,
            "error": f"{type(exc).__name__}: {exc}"[:200],
            "fallback": True,
            "data_source": f"{name}_via_mcp",
        }
        return [types.TextContent(type="text", text=json.dumps(err, ensure_ascii=False))]


async def _main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="travel-intelligence",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    asyncio.run(_main())
