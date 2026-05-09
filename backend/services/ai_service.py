"""Groq (OpenAI-compatible) client for SmartSpend AI features."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

_groq_client: OpenAI | None = None
_groq_failed: bool = False

# Groq chat models (fast + cheap for hackathon demos)
DEFAULT_GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")


def _get_groq_client() -> OpenAI | None:
    global _groq_client, _groq_failed
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key or _groq_failed:
        return None
    if _groq_client is None:
        try:
            _groq_client = OpenAI(
                api_key=key,
                base_url="https://api.groq.com/openai/v1",
            )
        except Exception:
            _groq_failed = True
            return None
    return _groq_client


def call_groq(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 400,
    temperature: float = 0.6,
    model: str | None = None,
    json_mode: bool = False,
) -> str | dict[str, Any]:
    """
    Call Groq chat completion. Returns plain text, or {} if json_mode and unavailable/failed.
    Never returns configuration error strings — callers supply user-facing fallbacks.
    """
    client = _get_groq_client()
    if client is None:
        return {} if json_mode else ""
    try:
        kwargs: dict[str, Any] = {
            "model": model or DEFAULT_GROQ_MODEL,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        content = (resp.choices[0].message.content or "").strip()
        if json_mode:
            if not content:
                return {}
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {}
        return content
    except Exception as exc:
        print(f"[call_groq] Groq API error: {exc}")
        return {} if json_mode else ""
