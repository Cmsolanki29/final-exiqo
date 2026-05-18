"""LLM waterfall for dashboard insights: Groq → OpenAI → Gemini (15s each)."""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Callable

from openai import OpenAI

logger = logging.getLogger(__name__)

INSIGHTS_LLM_TIMEOUT_SEC = 15


def _run_with_timeout(fn: Callable[[], dict[str, Any]], timeout: int = INSIGHTS_LLM_TIMEOUT_SEC) -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn)
        try:
            return fut.result(timeout=timeout)
        except FuturesTimeout as exc:
            raise TimeoutError(f"LLM call exceeded {timeout}s") from exc


def _call_groq_json(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        return {}
    model = os.getenv("GROQ_CHAT_MODEL", os.getenv("PHASE_9_DEFAULT_MODEL", "llama-3.3-70b-versatile")).strip()
    client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1", timeout=float(INSIGHTS_LLM_TIMEOUT_SEC))
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    resp = client.chat.completions.create(**kwargs)
    content = (resp.choices[0].message.content or "").strip()
    if not content:
        return {}
    parsed = json.loads(content)
    return parsed if isinstance(parsed, dict) else {}


def _call_openai_json(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return {}
    model = os.getenv("OPENAI_INSIGHTS_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    client = OpenAI(api_key=key, timeout=float(INSIGHTS_LLM_TIMEOUT_SEC))
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )
    content = (resp.choices[0].message.content or "").strip()
    if not content:
        return {}
    parsed = json.loads(content)
    return parsed if isinstance(parsed, dict) else {}


def _call_gemini_json(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    key = os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip()
    if not key:
        return {}
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise RuntimeError("google-generativeai not installed") from exc

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
    genai.configure(api_key=key)
    model = genai.GenerativeModel(
        model_name,
        generation_config={
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "response_mime_type": "application/json",
        },
    )
    prompt = f"{system_prompt}\n\n{user_prompt}"
    resp = model.generate_content(prompt, request_options={"timeout": INSIGHTS_LLM_TIMEOUT_SEC})
    text = (getattr(resp, "text", None) or "").strip()
    if not text:
        return {}
    parsed = json.loads(text)
    return parsed if isinstance(parsed, dict) else {}


def call_insights_json_waterfall(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 800,
    temperature: float = 0.25,
) -> tuple[dict[str, Any], str]:
    """
    Try Groq → OpenAI → Gemini. Returns (parsed_json, provider_name).
    Empty dict + 'none' if all providers fail or return invalid JSON.
    """
    chain: list[tuple[str, Callable[[], dict[str, Any]]]] = [
        ("groq", lambda: _call_groq_json(system_prompt, user_prompt, max_tokens, temperature)),
        ("openai", lambda: _call_openai_json(system_prompt, user_prompt, max_tokens, temperature)),
        ("gemini", lambda: _call_gemini_json(system_prompt, user_prompt, max_tokens, temperature)),
    ]
    for name, fn in chain:
        try:
            result = _run_with_timeout(fn, INSIGHTS_LLM_TIMEOUT_SEC)
            if isinstance(result, dict) and result:
                logger.info("Insights generated via %s", name)
                return result, name
            logger.warning("Insights %s returned empty or malformed JSON", name)
        except Exception as exc:
            logger.warning("Insights %s failed: %s", name, exc)
    return {}, "none"
