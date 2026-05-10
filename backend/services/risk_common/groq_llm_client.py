"""Thin wrapper around the OpenAI Python SDK pointed at Groq's endpoint.

Why a wrapper
-------------
Phase 9 (investigation agent) and Phase 12 (LLM-as-judge) both need:

* The same auth / base URL / default model resolution.
* Tool-calling in OpenAI-compatible format.
* Optional ``response_format={"type": "json_object"}`` for structured output.
* A "retry once with stricter prompt" path on JSON parse failures.
* Graceful degradation if ``GROQ_API_KEY`` is unset (returns ``None`` instead
  of raising at import time, so the FastAPI app can still boot for the
  rest of the surface area).

What this is NOT
----------------
This is the *only* module that touches the LLM SDK.  The agent must not
import openai directly — that way swapping providers (OpenAI, Anthropic,
self-hosted vLLM) means changing one file.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

# OpenAI SDK is imported lazily so test runs / boot don't fail when the
# package is missing for whatever reason.
try:
    from openai import AsyncOpenAI, OpenAIError  # type: ignore
except ImportError:  # pragma: no cover
    AsyncOpenAI = None  # type: ignore[assignment]
    OpenAIError = Exception  # type: ignore[assignment, misc]


GROQ_BASE_URL = "https://api.groq.com/openai/v1"


# ---------------------------------------------------------------------------- #
# Client factory
# ---------------------------------------------------------------------------- #
_client: Any | None = None
_client_init_failed: bool = False


def get_client() -> Any | None:
    """Return a cached AsyncOpenAI client pointed at Groq, or None if unavailable."""
    global _client, _client_init_failed
    if _client is not None:
        return _client
    if _client_init_failed:
        return None

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        logger.warning("GROQ_API_KEY is not set — Phase 9 LLM features disabled")
        _client_init_failed = True
        return None
    if AsyncOpenAI is None:
        logger.warning("openai SDK not installed — Phase 9 LLM features disabled")
        _client_init_failed = True
        return None

    _client = AsyncOpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
    return _client


def is_available() -> bool:
    """True iff the LLM client can be used right now."""
    return get_client() is not None


# ---------------------------------------------------------------------------- #
# High-level chat helper used by the agent
# ---------------------------------------------------------------------------- #
class LLMCallResult:
    """Lightweight result wrapper — keeps tool calls / tokens / message together."""

    __slots__ = (
        "message",
        "input_tokens",
        "output_tokens",
        "model",
        "finish_reason",
        "latency_ms",
    )

    def __init__(
        self,
        message: Any,
        input_tokens: int,
        output_tokens: int,
        model: str,
        finish_reason: str,
        latency_ms: int,
    ) -> None:
        self.message = message
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.model = model
        self.finish_reason = finish_reason
        self.latency_ms = latency_ms

    @property
    def text_content(self) -> str:
        """Best-effort text extraction from the message."""
        return getattr(self.message, "content", None) or ""

    @property
    def tool_calls(self) -> list[Any]:
        return getattr(self.message, "tool_calls", None) or []


async def chat(
    messages: list[dict[str, Any]],
    *,
    model: str,
    tools: list[dict[str, Any]] | None = None,
    response_format: dict[str, str] | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    fallback_model: str | None = "llama-3.1-70b-versatile",
) -> LLMCallResult:
    """Call Groq's chat completions endpoint.  Falls back to ``fallback_model``
    once on a 4xx/5xx that mentions the primary model being unavailable.

    Tool schemas use OpenAI's ``[{"type": "function", "function": {...}}]`` shape.
    """
    client = get_client()
    if client is None:
        raise RuntimeError("Groq LLM client unavailable (missing GROQ_API_KEY?)")

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    if response_format is not None:
        kwargs["response_format"] = response_format

    started = time.perf_counter()
    try:
        resp = await client.chat.completions.create(**kwargs)
    except OpenAIError as exc:  # noqa: BLE001
        msg = str(exc).lower()
        is_model_issue = any(t in msg for t in (
            "model_not_found", "model not found", "decommissioned", "unsupported",
        ))
        if fallback_model and fallback_model != model and is_model_issue:
            logger.warning(
                "groq_chat: primary model %s failed (%s) — retrying on %s",
                model, exc, fallback_model,
            )
            kwargs["model"] = fallback_model
            resp = await client.chat.completions.create(**kwargs)
            model = fallback_model
        else:
            raise
    latency_ms = int((time.perf_counter() - started) * 1000)

    choice = resp.choices[0]
    usage = resp.usage
    return LLMCallResult(
        message=choice.message,
        input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        model=model,
        finish_reason=choice.finish_reason or "stop",
        latency_ms=latency_ms,
    )


# ---------------------------------------------------------------------------- #
# JSON parsing helpers (stricter retry pattern)
# ---------------------------------------------------------------------------- #
def parse_json_response(text: str) -> dict[str, Any] | None:
    """Best-effort JSON extraction from an LLM response.

    Handles the three common formats the model emits:
      1. Pure JSON.
      2. JSON inside a ```json fenced block.
      3. JSON wrapped in prose — fall back to first ``{`` ... last ``}``.
    """
    if not text:
        return None
    raw = text.strip()
    if raw.startswith("```"):
        # Strip fenced code block.
        raw = raw.lstrip("`").lstrip("json").lstrip("JSON").lstrip()
        if "```" in raw:
            raw = raw.split("```", 1)[0].rstrip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Last-ditch: extract { ... }
    first = raw.find("{")
    last = raw.rfind("}")
    if first != -1 and last > first:
        try:
            return json.loads(raw[first : last + 1])
        except json.JSONDecodeError:
            return None
    return None
