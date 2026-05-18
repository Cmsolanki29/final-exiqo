"""
Full app API smoke test — Vikram Singh, Axis bank link ONLY (no PDF upload).

Run:
  cd backend
  $env:PYTHONPATH = "."
  $env:QA_API_BASE = "http://127.0.0.1:8810/api"
  python scripts/qa_vikram_bank_link_full.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta

import requests

BASE = os.getenv("QA_API_BASE", "http://127.0.0.1:8001/api")
issues: list[dict] = []
passed: list[str] = []


def ok(msg: str) -> None:
    passed.append(msg)
    print(f"  PASS  {msg}")


def fail(area: str, msg: str, detail: str = "") -> None:
    issues.append({"area": area, "msg": msg, "detail": detail})
    print(f"  FAIL  [{area}] {msg}" + (f" — {detail[:220]}" if detail else ""))


def hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def api_ready() -> bool:
    root = BASE.rstrip("/").removesuffix("/api")
    try:
        requests.get(f"{root}/health", timeout=15).raise_for_status()
        ok("backend health")
        spec = requests.get(f"{root}/openapi.json", timeout=15).json()
        params = spec.get("paths", {}).get("/api/transactions/{user_id}", {}).get("get", {}).get(
            "parameters", []
        )
        names = {p.get("name") for p in params}
        if "connected_source_id" not in names:
            print("  WARN  API may be older build (no source filters) — use port 8810 if counts look wrong")
        else:
            ok("API has latest transaction filters")
        return True
    except Exception as exc:
        fail("infra", "cannot reach API", str(exc))
        return False


def signup_vikram_axis() -> tuple[str, int]:
    email = f"vikram.bank.{int(time.time())}@example.com"
    r = requests.post(
        f"{BASE}/auth/signup",
        json={
            "name": "Vikram Singh",
            "email": email,
            "password": "TestPass123!",
            "signup_connection": "link_bank",
            "primary_bank": "axis",
        },
        timeout=60,
    )
    if r.status_code != 201:
        fail("auth", "signup (link_bank + axis)", r.text[:300])
        sys.exit(1)
    token = r.json()["access_token"]
    me = requests.get(f"{BASE}/auth/me", headers=hdr(token), timeout=30).json()
    uid = int(me["id"])
    ok(f"signup Vikram user_id={uid} email={email} dashboard_mode={me.get('dashboard_mode')}")
    return token, uid


def link_axis_bank(token: str, uid: int) -> int:
    mobile = "9876543210"
    send = requests.post(f"{BASE}/otp/send", json={"mobile_number": mobile}, timeout=15)
    if send.status_code != 200:
        fail("bank", "otp send", send.text[:200])
        return 0
    otp = send.json().get("otp_code")
    ver = requests.post(
        f"{BASE}/otp/verify",
        json={"mobile_number": mobile, "otp_code": str(otp)},
        timeout=15,
    )
    if ver.status_code != 200:
        fail("bank", "otp verify", ver.text[:200])
        return 0
    ok("OTP verified")

    r = requests.post(
        f"{BASE}/onboarding/link-bank",
        headers=hdr(token),
        json={"user_id": uid, "bank_slug": "axis", "mobile_number": mobile},
        timeout=90,
    )
    if r.status_code not in (200, 201):
        fail("bank", "link Axis bank", r.text[:300])
        return 0
    body = r.json()
    imported = int(body.get("transactions_imported") or 0)
    ok(f"Axis bank linked — pool transactions assigned={imported}")
    return imported


def check_onboarding(token: str, uid: int) -> None:
    r = requests.get(
        f"{BASE}/onboarding/status",
        headers=hdr(token),
        params={"user_id": uid},
        timeout=30,
    )
    if r.status_code != 200:
        fail("onboarding", "status", r.text[:200])
        return
    body = r.json()
    if body.get("onboarding_completed"):
        ok(f"onboarding complete banks={body.get('banks_linked')} txns={body.get('transactions_count')}")
    else:
        fail("onboarding", "not completed", json.dumps(body))


def check_transactions_and_dashboard(token: str, uid: int, pool_count: int) -> None:
    r = requests.get(
        f"{BASE}/transactions/{uid}",
        headers=hdr(token),
        params={"limit": 50},
        timeout=60,
    )
    if r.status_code != 200:
        fail("dashboard", "transaction list", r.text[:200])
        return
    rows = r.json()
    if isinstance(rows, dict):
        rows = rows.get("transactions") or rows.get("items") or []
    visible = len(rows)
    if visible > 0:
        ok(f"transaction list visible count={visible} (pool had {pool_count})")
    else:
        fail(
            "dashboard",
            "empty transaction list after bank link",
            "scoped dashboard may hide pool rows without connected_source_id",
        )

    summ = requests.get(
        f"{BASE}/transactions/{uid}/summary",
        headers=hdr(token),
        params={"month": date.today().month, "year": date.today().year},
        timeout=30,
    )
    if summ.status_code == 200:
        s = summ.json()
        inc = float(s.get("total_income") or 0)
        exp = float(s.get("total_expense") or 0)
        cnt = int(s.get("transaction_count") or 0)
        if cnt > 0 and (inc > 0 or exp > 0):
            ok(f"monthly summary income={inc:.0f} expense={exp:.0f} count={cnt}")
        elif pool_count > 0 and cnt == 0:
            fail("dashboard", "summary zero but pool assigned", json.dumps(s)[:200])
        else:
            ok(f"summary ok count={cnt} (no pool data)")
    else:
        fail("dashboard", "summary", summ.text[:200])

    for path in [f"/analysis/{uid}/trends", f"/financial-state/{uid}"]:
        tr = requests.get(f"{BASE}{path}", headers=hdr(token), timeout=60)
        if tr.status_code == 200:
            ok(f"GET {path}")
        else:
            fail("dashboard", path, tr.text[:200])

    src = requests.get(f"{BASE}/sources/connected", headers=hdr(token), params={"user_id": uid}, timeout=30)
    if src.status_code == 200:
        data = src.json()
        sources = data if isinstance(data, list) else data.get("sources") or []
        ok(f"connected sources count={len(sources)}")
    else:
        fail("dashboard", "connected sources", src.text[:200])


def check_features(token: str, uid: int) -> None:
    endpoints = [
        ("insights", f"/insights/{uid}", 90),
        ("fraud alerts", f"/fraud-shield/{uid}/alerts", 60),
        ("fraud stats", f"/fraud-shield/{uid}/stats", 60),
        ("dark patterns", f"/dark-patterns/{uid}", 90),
        ("festival", f"/festivals/{uid}", 60),
        ("emi", f"/emi/{uid}", 60),
        ("subscriptions", f"/subscriptions/{uid}", 60),
        ("pattern alerts", f"/pattern-alerts/{uid}/active", 60),
    ]
    for name, path, timeout in endpoints:
        r = requests.get(f"{BASE}{path}", headers=hdr(token), timeout=timeout)
        if r.status_code == 200:
            ok(name)
        else:
            fail(name, path, r.text[:200])

    goal = requests.post(
        f"{BASE}/purchases/{uid}/add-goal",
        headers=hdr(token),
        json={
            "item_name": "Vikram QA Phone",
            "target_amount": 45000,
            "target_date": (date.today() + timedelta(days=120)).isoformat(),
            "use_emi": True,
            "emi_tenure_months": 6,
            "interest_rate_annual": 12.0,
            "down_payment": 5000,
        },
        timeout=30,
    )
    if goal.status_code in (200, 201):
        ok("purchase planner add goal")
    else:
        fail("purchase", "add goal", goal.text[:200])


def main() -> int:
    print(f"\n=== Vikram Axis Bank-Link Full Smoke Test (no PDF) ===\nAPI: {BASE}\n")
    if not api_ready():
        return 1

    token, uid = signup_vikram_axis()
    pool = link_axis_bank(token, uid)
    check_onboarding(token, uid)
    check_transactions_and_dashboard(token, uid, pool)
    check_features(token, uid)

    print(f"\n=== SUMMARY ===")
    print(f"Passed: {len(passed)}")
    print(f"Failed: {len(issues)}")
    if issues:
        for i, x in enumerate(issues, 1):
            print(f"  {i}. [{x['area']}] {x['msg']}")
        return 1
    print("\nAll checks passed for Vikram bank-link flow.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
