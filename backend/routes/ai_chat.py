"""
SmartSpend AI Chatbot Routes
────────────────────────────
GET  /ai/session           — get active session or create one (+ online status)
POST /ai/chat              — send a message, stream back SSE chunks
POST /ai/upload            — upload PDF/CSV/TXT, parse & store
DELETE /ai/session/{id}    — reset a session (clear history)

Auth: all routes require Bearer JWT via existing get_current_user_id dependency.
DB:   psycopg2 sync (same as all other routes in this project).
AI:   OpenAI first when OPENAI_API_KEY is set, else Groq; Groq as automatic fallback on stream failure.
"""
from __future__ import annotations

import json
import logging
import os
import traceback
import uuid
from pathlib import Path
from typing import Generator, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from db import get_connection
from utils.auth import get_current_user_id
from services.ai_context_service import build_context_packet
from services.ai_llm_provider import (
    llm_session_meta,
    preferred_provider,
)
# `preferred_provider` is intentionally kept — used in the /chat route guard.
from services.document_parser_service import classify_and_extract, extract_text_from_bytes

router = APIRouter(prefix="/ai", tags=["AI Chatbot"])
_log = logging.getLogger(__name__)

# ── System prompt ─────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are SmartSpend's AI Financial Partner — a professional, friendly financial advisor grounded in the user's real transaction data.

Rules:
- Respond in the same language the user writes in
- Never invent numbers — only reference data provided in context
- Be concise and actionable
- Never mention OpenAI, Groq, GPT, or any model names
- Never say "as an AI language model"
- Keep responses under 150 words unless user asks for detail

Route navigation — ALWAYS include one ROUTE at the end when the user asks about a specific feature:
- EMI / loan / instalment questions  →  ROUTE:{"label":"EMI Tracker","path":"/emi-tracker"}
- Subscription questions             →  ROUTE:{"label":"Subscriptions AI","path":"/subscriptions"}
- Fraud / unusual transaction issues →  ROUTE:{"label":"FraudShield","path":"/fraud-shield"}
- Spending / transaction questions   →  ROUTE:{"label":"Transactions","path":"/transactions"}
- Savings / planning / health score  →  ROUTE:{"label":"Dashboard","path":"/dashboard"}
- Festival / event / gift spending   →  ROUTE:{"label":"Festivals","path":"/festivals"}
- Dark patterns / hidden charges     →  ROUTE:{"label":"Dark Patterns","path":"/dark-patterns"}

Context is provided as JSON with each request (profile, accounts, transactions, summaries).
End every response with CHIPS:q1|q2|q3 — three short follow-up questions the user might want to ask next."""


# ── Pydantic models ───────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    is_first_message: bool = False


# ── Helpers ───────────────────────────────────────────────────────────────
def _get_or_create_session(user_id: int) -> str:
    """Return an active session id (< 2h old) or create a fresh one."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id FROM ai_sessions
            WHERE user_id = %s
              AND last_active > NOW() - INTERVAL '2 hours'
            ORDER BY last_active DESC
            LIMIT 1
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if row:
            sid = str(row[0])
            cur.execute(
                "UPDATE ai_sessions SET last_active = NOW() WHERE id = %s::uuid",
                (sid,),
            )
        else:
            sid = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO ai_sessions (id, user_id) VALUES (%s::uuid, %s)",
                (sid, user_id),
            )
        conn.commit()
        return sid
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


def _load_history(session_id: str, limit: int = 20) -> list[dict]:
    """Load the last `limit` messages from the session."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT role, message FROM ai_messages
            WHERE session_id = %s::uuid
            ORDER BY created_at ASC
            OFFSET GREATEST(0, (
                SELECT COUNT(*) FROM ai_messages WHERE session_id = %s::uuid
            ) - %s)
            """,
            (session_id, session_id, limit),
        )
        return [{"role": r[0], "content": r[1]} for r in cur.fetchall()]
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


def _save_message(session_id: str, role: str, message: str) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO ai_messages (session_id, role, message) VALUES (%s::uuid, %s, %s)",
            (session_id, role, message),
        )
        conn.commit()
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


_ENV_FILE = Path(r"C:\Users\Chirag\Downloads\SMARTSPENDAPP\exiqo\.env")


def _read_api_keys() -> tuple[str, str, str, str]:
    """
    Read API keys directly from the .env file using dotenv_values(), then fall
    back to os.getenv().  This completely bypasses any stale / empty Windows
    system environment variables that would shadow the .env values.
    """
    from dotenv import dotenv_values

    file_env: dict[str, str | None] = {}
    for candidate in (
        _ENV_FILE,
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ):
        if candidate.is_file():
            file_env = dotenv_values(candidate)  # reads file WITHOUT touching os.environ
            break

    def _pick(key: str, default: str = "") -> str:
        v = (file_env.get(key) or "").strip() or (os.getenv(key) or "").strip()
        return v or default

    return (
        _pick("OPENAI_API_KEY"),
        _pick("GROQ_API_KEY"),
        _pick("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
        _pick("GROQ_CHAT_MODEL", "llama-3.3-70b-versatile"),
    )


def _stream_llm(messages: list[dict]) -> Generator[str, None, None]:
    """
    SSE chunks.  Reads keys directly from .env file at call-time via
    dotenv_values() so Windows system env vars can never shadow them.
    Provider order: OpenAI first, Groq fallback.
    """
    from openai import OpenAI

    offline = "I'm having trouble connecting right now. Please try again in a moment."
    interrupt = "\n\n— Connection interrupted, please retry.\n"

    openai_key, groq_key, chat_model, groq_model = _read_api_keys()

    print(
        f"[chat _stream_llm] OPENAI_API_KEY={'SET: ' + openai_key[:12] + '...' if openai_key else 'MISSING'} | "
        f"GROQ_API_KEY={'SET' if groq_key else 'MISSING'}",
        flush=True,
    )

    attempts: list[tuple[str, object, str]] = []
    if openai_key:
        attempts.append(("openai", OpenAI(api_key=openai_key, timeout=30.0), chat_model))
    if groq_key:
        attempts.append(("groq", OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1", timeout=30.0), groq_model))

    if not attempts:
        _log.error("_stream_llm: no API keys found in .env or environment")
        print("[chat] ERROR: No API keys found — neither OPENAI_API_KEY nor GROQ_API_KEY set", flush=True)
        yield f"data: {json.dumps({'chunk': offline + chr(10)})}\n\n"
        yield f"data: {json.dumps({'done': True, 'full': offline})}\n\n"
        return

    for idx, (provider, client, model) in enumerate(attempts):
        full_text = ""
        streamed_any = False
        try:
            print(f"[chat] attempt {idx}: {provider} / {model}", flush=True)
            _log.info("chat stream attempt=%s provider=%s model=%s", idx, provider, model)
            stream = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": _SYSTEM_PROMPT}] + messages,
                max_tokens=800,
                temperature=0.5,
                stream=True,
            )
            for chunk in stream:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                piece = (getattr(delta, "content", None) or "") if delta else ""
                if piece:
                    streamed_any = True
                    full_text += piece
                    yield f"data: {json.dumps({'chunk': piece})}\n\n"
        except Exception:
            print(f"[chat] {provider} FAILED:", flush=True)
            traceback.print_exc()
            if streamed_any:
                full_text += interrupt
                yield f"data: {json.dumps({'chunk': interrupt})}\n\n"
                yield f"data: {json.dumps({'done': True, 'full': full_text})}\n\n"
                return
            continue

        if full_text.strip():
            _log.info("chat stream success provider=%s", provider)
            yield f"data: {json.dumps({'done': True, 'full': full_text})}\n\n"
            return

    _log.warning("chat all providers exhausted with no text; offline fallback")
    print("[chat] All providers returned empty stream — offline fallback", flush=True)
    yield f"data: {json.dumps({'chunk': offline + chr(10)})}\n\n"
    yield f"data: {json.dumps({'done': True, 'full': offline})}\n\n"


# ── Routes ────────────────────────────────────────────────────────────────
@router.get("/session")
def get_session(user_id: int = Depends(get_current_user_id)):
    """Return an active session id, creating one if none exists, plus active LLM label."""
    sid = _get_or_create_session(user_id)
    return {"session_id": sid, "llm": llm_session_meta()}


@router.post("/chat")
def chat(
    request: ChatRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Send a message and stream back an SSE response.

    SSE format:
        data: {"chunk": "partial text"}\\n\\n  — streamed tokens
        data: {"done": true, "full": "..."}\\n\\n  — end-of-stream signal
    """
    if preferred_provider() == "none":
        raise HTTPException(
            503,
            "No AI service is configured for chat.",
        )
    sid = request.session_id or _get_or_create_session(user_id)

    _log.info("chat request user_id=%s first=%s", user_id, request.is_first_message)

    # Build context packet (sync psycopg2)
    context = build_context_packet(user_id, sid)
    context_json = json.dumps(context, default=str, ensure_ascii=False)

    # Load conversation history (last 20 turns)
    history = _load_history(sid)

    # Compose the user message
    if request.is_first_message:
        user_content = (
            f"CONTEXT PACKET (always use this for all responses — never invent numbers):\n"
            f"{context_json}\n\n"
            f"---\n\n"
            f"is_first_message: true\n"
            f"User's first message / greeting trigger: {request.message}\n\n"
            f"Follow the system prompt for first messages: greet by name, note linked institution and last sync if present, "
            f"three one-line factual teasers from this data only, optional ROUTE line, then CHIPS line."
        )
    else:
        user_content = (
            f"CONTEXT PACKET:\n{context_json}\n\n---\n\nUser: {request.message}"
        )

    messages = history + [{"role": "user", "content": user_content}]

    # Persist user message (raw text, not the context-stuffed version)
    _save_message(sid, "user", request.message)

    # Wrap the generator so we can persist the full assistant reply after streaming
    def _streaming_with_persist() -> Generator[str, None, None]:
        full_text = ""
        try:
            for chunk_line in _stream_llm(messages):
                if chunk_line.startswith("data: "):
                    try:
                        evt = json.loads(chunk_line[6:])
                        if "chunk" in evt:
                            full_text += evt["chunk"]
                    except Exception:
                        pass
                yield chunk_line
        except Exception:
            traceback.print_exc()
            _log.exception("chat streaming_with_persist outer failure")
            fallback_msg = (
                "I'm having trouble connecting right now. Please try again in a moment.\n"
            )
            yield f"data: {json.dumps({'chunk': fallback_msg})}\n\n"
            yield f"data: {json.dumps({'done': True, 'full': full_text + chr(10) + fallback_msg})}\n\n"
            return

        if full_text:
            _save_message(sid, "assistant", full_text)

    return StreamingResponse(
        _streaming_with_persist(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(default=None),
    user_id: int = Depends(get_current_user_id),
):
    """
    Upload a financial document (PDF/CSV/TXT).
    Returns extracted metadata so the frontend can trigger a follow-up chat message.
    """
    content = await file.read()
    text = extract_text_from_bytes(content, file.filename or "upload")
    extracted = classify_and_extract(text)

    # Check if this institution is already linked
    conn = get_connection()
    linked_banks: list[str] = []
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT LOWER(bank_name) FROM bank_connections WHERE user_id = %s",
            (user_id,),
        )
        linked_banks = [r[0] for r in cur.fetchall()]
    except Exception:
        pass
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()

    institution_lower = (extracted.get("institution") or "").lower()
    is_linked = bool(
        institution_lower and any(
            lb in institution_lower or institution_lower in lb
            for lb in linked_banks
        )
    )

    # Persist to document_uploads
    doc_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO document_uploads
              (id, user_id, session_id, file_name, document_type,
               institution, is_linked_account, parsed_text, extracted_json)
            VALUES (
              %s::uuid, %s,
              CASE WHEN %s IS NULL THEN NULL ELSE %s::uuid END,
              %s, %s, %s, %s, %s, %s
            )
            """,
            (
                doc_id, user_id,
                session_id, session_id,
                file.filename,
                extracted.get("document_type"),
                extracted.get("institution"),
                is_linked,
                text[:4000],
                json.dumps(extracted),
            ),
        )
        conn.commit()
    except Exception as e:
        raise HTTPException(500, f"Could not save document: {e}") from e
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()

    return {
        "doc_id": doc_id,
        "institution": extracted.get("institution"),
        "document_type": extracted.get("document_type"),
        "is_linked_account": is_linked,
        "summary": extracted.get("summary"),
        "transaction_count": len(extracted.get("transactions") or []),
        "date_range": extracted.get("date_range"),
        "account_masked": extracted.get("account_number_masked"),
    }


@router.delete("/session/{session_id}")
def reset_session(
    session_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """Delete all messages for a session (the user can start fresh)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM ai_messages WHERE session_id IN (
                SELECT id FROM ai_sessions WHERE id = %s::uuid AND user_id = %s
            )
            """,
            (session_id, user_id),
        )
        cur.execute(
            "UPDATE ai_sessions SET last_active = NOW() WHERE id = %s::uuid AND user_id = %s",
            (session_id, user_id),
        )
        conn.commit()
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()
    return {"ok": True, "session_id": session_id}
