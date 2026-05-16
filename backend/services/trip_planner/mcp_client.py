"""
Sync-safe MCP stdio client for the Travel Intelligence server.

A dedicated background thread owns the asyncio event loop and persistent
ClientSession so FastAPI's sync generator can call list_tools / call_tool safely.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import threading
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client

_log = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_SERVER_SCRIPT = _BACKEND_DIR / "mcp_servers" / "travel_intelligence_server.py"

_CONNECT_TIMEOUT_SEC = 25.0
_CALL_TIMEOUT_SEC = 90.0


def _mcp_tool_to_openai(tool: Any) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema or {"type": "object", "properties": {}},
        },
    }


def _parse_call_tool_result(result: Any) -> dict[str, Any]:
    if getattr(result, "structuredContent", None) is not None:
        sc = result.structuredContent
        if isinstance(sc, dict):
            return sc
    chunks: list[str] = []
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            chunks.append(text)
    if not chunks:
        return {"error": "empty_mcp_response", "fallback": True}
    raw = "".join(chunks).strip()
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"result": parsed}
    except json.JSONDecodeError:
        return {"result": raw}


class TravelMcpClient:
    """Persistent stdio MCP session; sync entrypoints for the trip planner agent."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._available = False
        self._tool_names: set[str] = set()
        self._openai_tools: list[dict[str, Any]] = []
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._start_error: str | None = None

    def is_available(self) -> bool:
        self._ensure_started()
        return self._available

    @property
    def tool_names(self) -> set[str]:
        return set(self._tool_names)

    def list_openai_tools_sync(self) -> list[dict[str, Any]]:
        self._ensure_started()
        return list(self._openai_tools)

    def call_tool_sync(self, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
        self._ensure_started()
        if not self._available or not self._session or not self._loop:
            raise RuntimeError("MCP travel server is not connected")
        coro = self._session.call_tool(name, arguments or {})
        result = asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=_CALL_TIMEOUT_SEC)
        return _parse_call_tool_result(result)

    def health_snapshot(self) -> dict[str, Any]:
        self._ensure_started()
        return {
            "mcp_connected": self._available,
            "mcp_tools": len(self._tool_names),
            "mcp_error": self._start_error,
        }

    def _ensure_started(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._ready.clear()
            self._thread = threading.Thread(target=self._thread_main, name="travel-mcp", daemon=True)
            self._thread.start()
        if not self._ready.wait(timeout=_CONNECT_TIMEOUT_SEC + 5):
            _log.warning("[trip-planner.mcp] background thread did not become ready in time")

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._async_connect())
            self._ready.set()
            loop.run_forever()
        except Exception as exc:  # noqa: BLE001
            self._start_error = f"{type(exc).__name__}: {exc}"[:200]
            _log.exception("[trip-planner.mcp] thread failed during connect")
            self._available = False
            self._ready.set()
        finally:
            try:
                loop.run_until_complete(self._async_disconnect())
            except Exception:  # noqa: BLE001
                pass
            loop.close()

    async def _async_connect(self) -> None:
        if not _SERVER_SCRIPT.is_file():
            self._start_error = f"server script missing: {_SERVER_SCRIPT}"
            _log.error("[trip-planner.mcp] %s", self._start_error)
            return

        env = dict(get_default_environment())
        sep = ";" if sys.platform == "win32" else ":"
        prev = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(_BACKEND_DIR) if not prev else f"{_BACKEND_DIR}{sep}{prev}"

        params = StdioServerParameters(
            command=sys.executable,
            args=[str(_SERVER_SCRIPT)],
            env=env,
            cwd=str(_BACKEND_DIR),
        )

        self._stack = AsyncExitStack()
        read_stream, write_stream = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(read_stream, write_stream))
        await self._session.initialize()

        listed = await self._session.list_tools()
        tools = listed.tools or []
        self._tool_names = {t.name for t in tools}
        self._openai_tools = [_mcp_tool_to_openai(t) for t in tools]
        self._available = bool(self._openai_tools)
        self._start_error = None
        _log.info("[trip-planner.mcp] connected — %d tools", len(self._openai_tools))

    async def _async_disconnect(self) -> None:
        if self._stack:
            await self._stack.aclose()
        self._stack = None
        self._session = None
        self._available = False


_client: TravelMcpClient | None = None
_client_lock = threading.Lock()


def get_travel_mcp_client() -> TravelMcpClient:
    global _client
    with _client_lock:
        if _client is None:
            _client = TravelMcpClient()
        return _client


__all__ = ["TravelMcpClient", "get_travel_mcp_client"]
