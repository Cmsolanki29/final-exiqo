"""
SmartSpend › AI Actions › Trip Planner
──────────────────────────────────────
POST /api/ai-actions/trip-planner/chat   — stream the agent's reasoning + plan (SSE)
GET  /api/ai-actions/trip-planner/health — quick capability probe

Auth: JWT via the existing utils.auth.get_current_user_id dependency.
"""
from __future__ import annotations

import json
import logging
import os
import time
import traceback
from collections import defaultdict, deque
from typing import Any, Generator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.trip_planner.agent import run_trip_planner_agent
from services.trip_planner.mcp_client import get_travel_mcp_client
from utils.auth import get_current_user_id

router = APIRouter(prefix="/ai-actions/trip-planner", tags=["AI Actions › Trip Planner"])
_log = logging.getLogger(__name__)

# ── Simple in-memory rate limit: 10 messages / 60s / user ─────────────────
_RATE_WINDOW_SEC = 60.0
_RATE_MAX_MSGS = 10
_rate_log: dict[int, deque[float]] = defaultdict(deque)


def _check_rate_limit(user_id: int) -> None:
    now = time.time()
    window = _rate_log[user_id]
    while window and (now - window[0]) > _RATE_WINDOW_SEC:
        window.popleft()
    if len(window) >= _RATE_MAX_MSGS:
        raise HTTPException(429, "Too many trip planner messages. Please wait a minute.")
    window.append(now)


# ── Pydantic ──────────────────────────────────────────────────────────────
class _HistoryTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class TripPlannerChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[_HistoryTurn] = Field(default_factory=list)


# ── Capability probe ──────────────────────────────────────────────────────
@router.get("/health")
def trip_planner_health(_user_id: int = Depends(get_current_user_id)) -> dict[str, Any]:
    """Tells the frontend which providers are live so the UI can show small badges."""
    mcp_health = get_travel_mcp_client().health_snapshot()
    return {
        "ok": True,
        "providers": {
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "weather": bool(os.getenv("OPENWEATHERMAP_API_KEY")),
            "flights": bool(os.getenv("AMADEUS_API_KEY") and os.getenv("AMADEUS_API_SECRET")),
            "hotels": bool(os.getenv("RAPIDAPI_KEY")),
            "places": True,  # OpenStreetMap is free + always considered available
        },
        "model": os.getenv("OPENAI_TRIP_PLANNER_MODEL", os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")),
        **mcp_health,
    }


# ── Main streaming endpoint ───────────────────────────────────────────────
@router.post("/chat")
def trip_planner_chat(
    payload: TripPlannerChatRequest,
    user_id: int = Depends(get_current_user_id),
):
    _check_rate_limit(user_id)

    history_dicts = [{"role": h.role, "content": h.content} for h in payload.history]

    def _stream() -> Generator[str, None, None]:
        try:
            for event in run_trip_planner_agent(
                user_id=user_id,
                user_message=payload.message,
                conversation_history=history_dicts,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            _log.exception("[trip-planner] streaming failure: %s", exc)
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "message": f"Trip Planner crashed: {type(exc).__name__}. Please try again.",
                    }
                )
                + "\n\n"
            )

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
