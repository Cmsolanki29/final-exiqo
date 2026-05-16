"""OpenAI function-calling schemas for the Trip Planner agent."""
from __future__ import annotations

from typing import Any

INTERNAL_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "get_user_financial_context",
        "budget_optimizer",
        "project_future_savings",
    }
)

TRAVEL_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "get_weather_for_destination",
        "search_flights",
        "search_hotels",
        "explore_places",
    }
)

INTERNAL_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_user_financial_context",
            "description": (
                "Fetches the user's complete real financial snapshot from SmartSpend: savings, "
                "monthly income, active EMIs, average monthly surplus, subscriptions, and top "
                "spending categories. ALWAYS call this FIRST before any other tool."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "budget_optimizer",
            "description": (
                "Computes total trip cost from the priced components, compares against the user's real "
                "savings + surplus, and returns a GREEN / YELLOW / RED verdict."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_cost": {"type": "number", "description": "Per-person flight cost in INR."},
                    "hotel_cost_per_night": {"type": "number"},
                    "nights": {"type": "integer", "minimum": 1},
                    "travelers": {"type": "integer", "minimum": 1, "default": 1},
                    "daily_food_budget": {"type": "number", "default": 800},
                    "local_transport": {"type": "number", "default": 3000},
                    "activities_budget": {"type": "number", "default": 5000},
                    "buffer_percentage": {"type": "number", "default": 15, "minimum": 0, "maximum": 50},
                },
                "required": ["flight_cost", "hotel_cost_per_night", "nights"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "project_future_savings",
            "description": (
                "Projects total savings N months out at the user's current saving rate. Use for YELLOW "
                "verdicts to suggest a concrete 'wait until <date>' plan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "months_ahead": {"type": "integer", "minimum": 1, "maximum": 60},
                },
                "required": ["months_ahead"],
            },
        },
    },
]

# Used when the MCP subprocess is unavailable (direct Python fallback).
TRAVEL_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_weather_for_destination",
            "description": (
                "Returns current weather + 5-day forecast for the destination, plus India-specific "
                "seasonal hints. Use this to advise on timing and the best month."
            ),
            "parameters": {
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
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": (
                "Searches real flight options. Returns offer prices in INR. If credentials are "
                "missing the result has fallback: true — in that case estimate from general "
                "market knowledge."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "Origin city — use user's home city when known."},
                    "destination": {"type": "string"},
                    "departure_date": {
                        "type": "string",
                        "description": "Approximate departure date in YYYY-MM-DD format.",
                    },
                    "travelers": {"type": "integer", "minimum": 1, "default": 1},
                },
                "required": ["origin", "destination", "departure_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_hotels",
            "description": "Searches hotels for the destination. Returns budget / mid / luxury tier samples in INR per night.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string"},
                    "check_in": {"type": "string", "description": "YYYY-MM-DD"},
                    "nights": {"type": "integer", "minimum": 1},
                    "guests": {"type": "integer", "minimum": 1, "default": 2},
                },
                "required": ["destination", "check_in", "nights"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explore_places",
            "description": (
                "Finds real attractions / food / activities at a destination, OR cheaper destinations "
                "near the user's home city when category = alternatives_nearby."
            ),
            "parameters": {
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
        },
    },
]

# Back-compat alias for imports that still expect the full 7-tool list.
TRIP_PLANNER_TOOLS: list[dict[str, Any]] = INTERNAL_TOOL_SCHEMAS + TRAVEL_TOOL_SCHEMAS


FRIENDLY_TOOL_NAMES: dict[str, str] = {
    "get_user_financial_context": "Checking your finances",
    "get_weather_for_destination": "Reading weather patterns",
    "search_flights": "Searching flights",
    "search_hotels": "Finding hotels",
    "explore_places": "Exploring destinations",
    "budget_optimizer": "Calculating your trip budget",
    "project_future_savings": "Projecting your savings",
}


def friendly_tool_name(name: str) -> str:
    return FRIENDLY_TOOL_NAMES.get(name, "Working on it")


def tool_event_source(tool_name: str, *, via_mcp: bool) -> str:
    """SSE/UI source: internal (SmartSpend) vs mcp/direct (Live Intelligence)."""
    if tool_name in INTERNAL_TOOL_NAMES:
        return "internal"
    if via_mcp:
        return "mcp"
    return "direct"


def build_agent_tools(mcp_openai_tools: list[dict[str, Any]] | None) -> tuple[list[dict[str, Any]], bool]:
    """
    Returns (tools_for_openai, mcp_active).
    When MCP is connected, travel schemas come from list_tools; otherwise TRAVEL_TOOL_SCHEMAS.
    """
    if mcp_openai_tools:
        return list(INTERNAL_TOOL_SCHEMAS) + list(mcp_openai_tools), True
    return list(INTERNAL_TOOL_SCHEMAS) + list(TRAVEL_TOOL_SCHEMAS), False


__all__ = [
    "INTERNAL_TOOL_NAMES",
    "TRAVEL_TOOL_NAMES",
    "INTERNAL_TOOL_SCHEMAS",
    "TRAVEL_TOOL_SCHEMAS",
    "TRIP_PLANNER_TOOLS",
    "FRIENDLY_TOOL_NAMES",
    "friendly_tool_name",
    "tool_event_source",
    "build_agent_tools",
]
