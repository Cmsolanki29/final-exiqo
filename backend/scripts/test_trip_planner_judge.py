"""
Hackathon judge test suite — Trip Planner + MCP verification.

Usage (from backend/):
  python -m scripts.test_trip_planner_judge

Requires: backend on :8001, OPENAI_API_KEY, Postgres with seed users.
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

API = "http://127.0.0.1:8001"
TIMEOUT = 180.0

USERS = {
    "vikram": ("vikram@smartspend.in", "Demo@1234", "GREEN-ish (high savings)"),
    "priya": ("priya@smartspend.in", "Demo@1234", "RED-ish (tight finances)"),
    "rahul": ("rahul@smartspend.in", "Demo@1234", "YELLOW-ish (moderate income)"),
}

SCENARIOS = [
    {
        "id": "green_kashmir",
        "user": "vikram",
        "message": "Plan a 5-night Kashmir trip from Pune in December for 2 people. Is it affordable for me?",
        "expect_verdict": {"GREEN", "YELLOW"},
    },
    {
        "id": "red_luxury",
        "user": "priya",
        "message": "I want a 10-night Europe honeymoon next month, budget around 8 lakh. Can I afford it?",
        "expect_verdict": {"RED", "YELLOW"},
    },
    {
        "id": "yellow_wait",
        "user": "rahul",
        "message": "Goa trip 4 nights in March from Bengaluru for 1 person — should I book now or wait and save?",
        "expect_verdict": {"GREEN", "YELLOW", "RED"},
    },
    {
        "id": "hinglish",
        "user": "vikram",
        "message": "Bhai Manali jana hai 3 din ke liye, paise theek hain kya mere? December mein.",
        "expect_verdict": {"GREEN", "YELLOW", "RED"},
    },
]


@dataclass
class RunResult:
    scenario_id: str
    user: str
    ok: bool = False
    verdict: str | None = None
    tool_events: list[dict[str, Any]] = field(default_factory=list)
    sources: dict[str, int] = field(default_factory=dict)
    mcp_tags: int = 0
    internal_tools: int = 0
    error: str | None = None
    final_preview: str = ""


def signin(email: str, password: str) -> str:
    r = httpx.post(
        f"{API}/api/auth/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def parse_sse_events(raw: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if not block.startswith("data: "):
            continue
        try:
            events.append(json.loads(block[6:].strip()))
        except json.JSONDecodeError:
            pass
    return events


def run_chat(token: str, message: str) -> list[dict[str, Any]]:
    with httpx.stream(
        "POST",
        f"{API}/api/ai-actions/trip-planner/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": message, "history": []},
        timeout=TIMEOUT,
    ) as resp:
        resp.raise_for_status()
        buf = ""
        for chunk in resp.iter_text():
            buf += chunk
    return parse_sse_events(buf)


def analyze(events: list[dict[str, Any]]) -> tuple[str | None, list[dict], dict[str, int], int, int, str]:
    tools: list[dict] = []
    sources: dict[str, int] = {}
    mcp_tags = 0
    internal = 0
    verdict = None
    final_text = ""

    for ev in events:
        t = ev.get("type")
        if t == "tool_start":
            tools.append(ev)
            src = ev.get("source") or "unknown"
            sources[src] = sources.get(src, 0) + 1
            if src == "internal":
                internal += 1
        if t == "tool_end":
            pass
        if t == "final":
            final_text = (ev.get("text") or "")[:400]
            plan = ev.get("plan")
            if isinstance(plan, dict):
                verdict = str(plan.get("verdict") or "").upper() or None
        if t == "error":
            return None, tools, sources, mcp_tags, internal, ev.get("message", "error")

    return verdict, tools, sources, mcp_tags, internal, final_text


def test_mcp_layer() -> dict[str, Any]:
    from services.trip_planner.mcp_client import get_travel_mcp_client

    c = get_travel_mcp_client()
    out: dict[str, Any] = {
        "mcp_available": c.is_available(),
        "tool_count": len(c.tool_names),
        "tools": sorted(c.tool_names),
        **c.health_snapshot(),
    }
    if c.is_available():
        r = c.call_tool_sync("get_weather_for_destination", {"destination": "Goa"})
        out["sample_data_source"] = r.get("data_source")
        out["sample_has_weather"] = "current" in r or r.get("fallback")
    return out


def test_health(token: str) -> dict[str, Any]:
    r = httpx.get(
        f"{API}/api/ai-actions/trip-planner/health",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def main() -> int:
    print("=" * 60)
    print("SmartSpend Trip Planner — Judge Test Suite")
    print("=" * 60)

    # 1) MCP layer
    print("\n[1] MCP Travel Intelligence (stdio)")
    try:
        mcp = test_mcp_layer()
        for k, v in mcp.items():
            print(f"    {k}: {v}")
        if not mcp.get("mcp_available"):
            print("    FAIL: MCP not connected")
        elif mcp.get("sample_data_source", "").endswith("_via_mcp"):
            print("    PASS: Real MCP call_tool returned *_via_mcp tag")
        else:
            print("    WARN: MCP connected but data_source tag unexpected")
    except Exception as exc:
        print(f"    FAIL: {exc}")
        mcp = {"mcp_available": False}

    # 2) Health API
    print("\n[2] Trip Planner health API")
    try:
        tok = signin(*USERS["vikram"][:2])
        health = test_health(tok)
        print(f"    mcp_connected: {health.get('mcp_connected')}")
        print(f"    mcp_tools: {health.get('mcp_tools')}")
        print(f"    providers: {health.get('providers')}")
    except Exception as exc:
        print(f"    FAIL: {exc}")
        return 1

    if not health.get("mcp_connected"):
        print("    WARN: Health reports MCP disconnected — travel may use direct fallback")

    # 3) Chat scenarios
    print("\n[3] End-to-end chat scenarios (SSE)")
    results: list[RunResult] = []
    for sc in SCENARIOS:
        email, pw, note = USERS[sc["user"]]
        print(f"\n  --- {sc['id']} ({sc['user']}: {note}) ---")
        rr = RunResult(scenario_id=sc["id"], user=sc["user"])
        try:
            token = signin(email, pw)
            t0 = time.time()
            events = run_chat(token, sc["message"])
            elapsed = time.time() - t0
            verdict, tools, sources, _, internal, preview = analyze(events)
            rr.verdict = verdict
            rr.tool_events = tools
            rr.sources = sources
            rr.internal_tools = internal
            rr.final_preview = preview
            rr.ok = verdict is not None and verdict in sc["expect_verdict"]
            print(f"    time: {elapsed:.1f}s | verdict: {verdict} | tools: {len(tools)}")
            print(f"    sources: {sources}")
            print(f"    internal (SmartSpend Engine): {sources.get('internal', 0)}")
            print(f"    mcp (Live Intelligence): {sources.get('mcp', 0)}")
            print(f"    direct fallback: {sources.get('direct', 0)}")
            if verdict:
                match = "PASS" if rr.ok else "WARN"
                print(f"    {match}: verdict in {sc['expect_verdict']}")
            else:
                print("    FAIL: no PLAN_JSON verdict")
                rr.error = "no verdict"
        except Exception as exc:
            rr.error = str(exc)[:200]
            print(f"    FAIL: {exc}")
        results.append(rr)

    # 4) MCP vs direct isolation (executor)
    print("\n[4] Executor routing check")
    from services.trip_planner.tool_executor import execute_tool_call
    from services.trip_planner.tool_definitions import build_agent_tools
    from services.trip_planner.mcp_client import get_travel_mcp_client

    client = get_travel_mcp_client()
    tools, mcp_active = build_agent_tools(
        client.list_openai_tools_sync() if client.is_available() else None
    )
    print(f"    agent_tools_count: {len(tools)} | mcp_active: {mcp_active}")
    r_mcp, via_mcp = execute_tool_call(
        "get_weather_for_destination",
        {"destination": "Jaipur"},
        user_id=1,
        mcp_active=mcp_active,
    )
    print(f"    weather via_mcp={via_mcp} data_source={r_mcp.get('data_source')}")
    r_int, via_int = execute_tool_call("get_user_financial_context", {}, user_id=1, mcp_active=mcp_active)
    print(f"    finance via_mcp={via_int} (expect False) keys={list(r_int.keys())[:4]}")

    # Summary
    print("\n" + "=" * 60)
    print("JUDGE SUMMARY")
    print("=" * 60)
    mcp_ok = bool(mcp.get("mcp_available")) and health.get("mcp_connected")
    travel_mcp_used = sum(r.sources.get("mcp", 0) for r in results)
    internal_used = sum(r.sources.get("internal", 0) for r in results)
    passed = sum(1 for r in results if r.ok)
    print(f"  MCP subprocess:     {'YES' if mcp_ok else 'NO / fallback'}")
    print(f"  Live Intelligence:  {travel_mcp_used} tool steps via MCP")
    print(f"  SmartSpend Engine:  {internal_used} tool steps (DB finance)")
    print(f"  Scenarios w/verdict: {passed}/{len(results)}")
    for r in results:
        st = "OK" if r.ok else ("ERR" if r.error else "WARN")
        print(f"    [{st}] {r.scenario_id}: {r.verdict or r.error} sources={r.sources}")
    print("\n  Demo login: vikram@smartspend.in / Demo@1234")
    print("  UI: AI Actions → Trip Planner → watch SmartSpend Engine + Live Intelligence panels")
    return 0 if mcp_ok and passed >= 2 else 1


if __name__ == "__main__":
    sys.exit(main())
