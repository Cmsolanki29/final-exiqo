"""
Trip Planner › Agent orchestrator.

Drives the OpenAI function-calling loop. Streams a sequence of events back to
the API route as plain dicts; the route serialises them into SSE frames.

Event shapes (all dicts):
  {"type": "tool_start", "tool": str, "friendly": str, "args": dict, "source": "internal"|"mcp"|"direct"}
  {"type": "tool_end",   "tool": str, "friendly": str, "ok": bool, "summary": str, "source": str}
  {"type": "delta",      "text": str}                    # streamed answer tokens
  {"type": "final",      "text": str, "plan": dict|None} # complete response
  {"type": "error",      "message": str}

The orchestrator is deliberately self-contained: it reads keys from the .env
file with dotenv_values (same pattern as the existing /api/ai/chat route) so
empty Windows system env vars never shadow real values.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Generator, Iterable

import httpx
from openai import OpenAI

from .mcp_client import get_travel_mcp_client
from .system_prompt import build_system_prompt
from .tool_definitions import (
    TRAVEL_TOOL_NAMES,
    build_agent_tools,
    friendly_tool_name,
    tool_event_source,
)
from .tool_executor import execute_tool_call

_log = logging.getLogger(__name__)

# 12 iterations comfortably covers single-destination flows (≈6 tool calls) AND
# multi-city / YELLOW follow-up flows that need projections + alternatives.
_MAX_ITERATIONS = 12


def _read_openai_key_and_model() -> tuple[str, str]:
    """Mirror the resilient .env loader used by routes/ai_chat.py."""
    try:
        from dotenv import dotenv_values
    except Exception:
        dotenv_values = None  # type: ignore[assignment]

    file_env: dict[str, str | None] = {}
    if dotenv_values:
        candidates = [
            Path(r"C:\Users\Chirag\Downloads\SMARTSPENDAPP\exiqo\.env"),
            Path(__file__).resolve().parents[3] / ".env",
            Path(__file__).resolve().parents[2] / ".env",
        ]
        for cand in candidates:
            try:
                if cand.is_file():
                    file_env = dotenv_values(cand)
                    break
            except OSError:
                continue

    def pick(key: str, default: str = "") -> str:
        v = (file_env.get(key) or "").strip() if file_env else ""
        if v:
            return v
        return (os.getenv(key) or "").strip() or default

    api_key = pick("OPENAI_API_KEY")
    model = pick("OPENAI_TRIP_PLANNER_MODEL", pick("OPENAI_CHAT_MODEL", "gpt-4o-mini"))
    return api_key, model


def _summarise_tool_result(tool_name: str, result: dict[str, Any]) -> str:
    """One-line human summary for the live timeline event."""
    if not isinstance(result, dict):
        return "done"
    if result.get("error"):
        return "fallback (provider unavailable)"
    if result.get("fallback"):
        return "general-knowledge estimate"
    if tool_name == "get_user_financial_context":
        savings = result.get("total_savings_inr") or 0
        surplus = result.get("monthly_surplus_inr") or 0
        return f"₹{savings:,.0f} saved · ₹{surplus:,.0f} monthly surplus"
    if tool_name == "get_weather_for_destination":
        cur = (result.get("current") or {})
        temp = cur.get("temp_c")
        cond = cur.get("condition") or "—"
        return f"{temp}°C · {cond}" if temp is not None else cond
    if tool_name == "search_flights":
        cheapest = result.get("cheapest_inr")
        offers = result.get("offers") or []
        if cheapest:
            return f"{len(offers)} offers · from ₹{cheapest:,.0f}"
        return f"{len(offers)} offers"
    if tool_name == "search_hotels":
        hotels = result.get("hotels") or []
        return f"{len(hotels)} hotels priced"
    if tool_name == "explore_places":
        places = result.get("places") or []
        return f"{len(places)} places found"
    if tool_name == "budget_optimizer":
        verdict = result.get("verdict") or "—"
        total = (result.get("breakdown") or {}).get("total_inr") or 0
        return f"{verdict} · ₹{total:,.0f} total"
    if tool_name == "project_future_savings":
        proj = result.get("projected_total_inr") or 0
        date_str = result.get("projected_date") or ""
        return f"₹{proj:,.0f} by {date_str}"
    return "done"


_PLAN_RE = re.compile(r"PLAN_JSON\s*:\s*(\{.*\})\s*$", re.DOTALL | re.IGNORECASE)


def _extract_plan(final_text: str) -> tuple[str, dict[str, Any] | None]:
    """
    Pull the PLAN_JSON trailer out so the frontend can render it as a card.
    Returns (clean_text_without_plan_line, plan_dict_or_none).
    """
    match = _PLAN_RE.search(final_text or "")
    if not match:
        return (final_text or "").strip(), None
    raw = match.group(1).strip()
    try:
        plan = json.loads(raw)
    except Exception:
        # try greedy-trim to the last closing brace
        try:
            trimmed = raw[: raw.rfind("}") + 1]
            plan = json.loads(trimmed)
        except Exception:
            return (final_text or "").strip(), None
    clean = _PLAN_RE.sub("", final_text).strip()
    return clean, plan


def run_trip_planner_agent(
    *,
    user_id: int,
    user_message: str,
    conversation_history: Iterable[dict[str, str]] | None = None,
) -> Generator[dict[str, Any], None, None]:
    """
    Drives the OpenAI function-calling loop and yields structured events.
    """
    api_key, model = _read_openai_key_and_model()
    if not api_key:
        yield {
            "type": "error",
            "message": "AI service is not configured. Add OPENAI_API_KEY to your .env to use Trip Planner.",
        }
        return

    try:
        # NOTE: explicit http_client avoids the `proxies=` kwarg crash that occurs
        # when openai 1.51.x auto-builds an httpx.Client against httpx >= 0.28.
        client = OpenAI(
            api_key=api_key,
            timeout=60.0,
            http_client=httpx.Client(timeout=60.0),
        )
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": f"Could not initialise AI client: {exc}"}
        return

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": build_system_prompt()},
    ]
    # Truncate history to last 10 turns to keep token cost bounded.
    history = list(conversation_history or [])[-10:]
    for h in history:
        role = h.get("role")
        content = h.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    mcp_client = get_travel_mcp_client()
    mcp_tools = mcp_client.list_openai_tools_sync() if mcp_client.is_available() else []
    agent_tools, mcp_active = build_agent_tools(mcp_tools if mcp_tools else None)

    for iteration in range(_MAX_ITERATIONS):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=agent_tools,
                tool_choice="auto",
                temperature=0.6,
                max_tokens=1500,
            )
        except Exception as exc:  # noqa: BLE001
            _log.exception("[trip-planner.agent] LLM call failed on iteration %d", iteration)
            yield {
                "type": "error",
                "message": f"AI request failed: {type(exc).__name__}. Please try again.",
            }
            return

        choice = response.choices[0]
        assistant_message = choice.message
        tool_calls = assistant_message.tool_calls or []

        # Persist the assistant turn (even if it has no content) so subsequent
        # iterations see the same tool_call ids.
        messages.append(
            {
                "role": "assistant",
                "content": assistant_message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                    for tc in tool_calls
                ] if tool_calls else None,
            }
        )

        if tool_calls:
            for tc in tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    tool_args = {}

                likely_mcp = mcp_active and tool_name in TRAVEL_TOOL_NAMES
                yield {
                    "type": "tool_start",
                    "tool": tool_name,
                    "friendly": friendly_tool_name(tool_name),
                    "args": tool_args,
                    "source": tool_event_source(tool_name, via_mcp=likely_mcp),
                }

                result, via_mcp = execute_tool_call(
                    tool_name, tool_args, user_id, mcp_active=mcp_active
                )
                source = tool_event_source(tool_name, via_mcp=via_mcp)

                yield {
                    "type": "tool_end",
                    "tool": tool_name,
                    "friendly": friendly_tool_name(tool_name),
                    "ok": not bool(result.get("error")) if isinstance(result, dict) else True,
                    "summary": _summarise_tool_result(tool_name, result if isinstance(result, dict) else {}),
                    "source": source,
                }

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, default=str, ensure_ascii=False)[:14000],
                    }
                )
            continue

        # No more tool calls — this is the model's final answer.
        final_text = assistant_message.content or ""
        clean, plan = _extract_plan(final_text)

        # ── Structured-output fallback ──────────────────────────────────────
        # If the model forgot the PLAN_JSON trailer (common on long answers),
        # do ONE targeted extraction call using the same tool history so the
        # itinerary card always renders. We never invent numbers — the model
        # is told to only use values that already appear in the conversation.
        if plan is None and clean and len(clean) > 80:
            try:
                extraction = client.chat.completions.create(
                    model=model,
                    messages=messages
                    + [
                        {
                            "role": "user",
                            "content": (
                                "Output ONLY a single valid JSON object (no markdown, no prose) "
                                "that summarises the plan you just wrote, using the schema:\n"
                                "{verdict, destination, origin, best_month, nights, travelers, "
                                "total_cost_inr, user_savings_inr, monthly_surplus_inr, "
                                "shortfall_inr, months_to_save, weather_summary, "
                                "breakdown:{flights_inr,hotels_inr,food_inr,local_transport_inr,"
                                "activities_inr,buffer_inr}, "
                                "itinerary:[{day,title,activities:[]}], "
                                "alternatives:[{name,why,est_cost_inr}], save_until_date}\n"
                                "Use ONLY numbers that already appeared in the previous tool "
                                "results — never invent."
                            ),
                        }
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=900,
                )
                raw = (extraction.choices[0].message.content or "").strip()
                if raw:
                    plan = json.loads(raw)
            except Exception as exc:  # noqa: BLE001
                _log.warning("[trip-planner.agent] structured fallback failed: %s", exc)

        # Stream the clean text in small chunks so the UI can typewriter-render.
        if clean:
            CHUNK = 24
            for i in range(0, len(clean), CHUNK):
                yield {"type": "delta", "text": clean[i : i + CHUNK]}

        yield {"type": "final", "text": clean, "plan": plan}
        return

    # Safety net — loop exhausted.
    yield {
        "type": "final",
        "text": "I gathered the live data but couldn't finalise the plan in one pass. "
                "Could you tell me the destination and a rough date again?",
        "plan": None,
    }


__all__ = ["run_trip_planner_agent"]
