"""
Full app smoke test — existing demo user Karan (bank-linked persona, NO PDF).

  Email:    karan@smartspend.in
  Password: Demo@1234
  Income:   INR 60,000/month (seed)

Run:
  cd backend
  $env:PYTHONPATH = "."
  $env:QA_API_BASE = "http://127.0.0.1:8810/api"
  python scripts/qa_karan_full_app_test.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta

import requests

BASE = os.getenv("QA_API_BASE", "http://127.0.0.1:8810/api")
EMAIL = os.getenv("QA_KARAN_EMAIL", "karan@smartspend.in")
PASSWORD = os.getenv("QA_KARAN_PASSWORD", "Demo@1234")
EXPECTED_INCOME = float(os.getenv("QA_KARAN_INCOME", "60000"))

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


def signin() -> tuple[str, dict]:
    r = requests.post(
        f"{BASE}/auth/signin",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=30,
    )
    if r.status_code != 200:
        fail("auth", "signin", r.text[:300])
        sys.exit(1)
    token = r.json()["access_token"]
    me = requests.get(f"{BASE}/auth/me", headers=hdr(token), timeout=30).json()
    ok(f"signin {EMAIL} user_id={me.get('id')} name={me.get('name')}")
    return token, me


def check_profile(me: dict) -> int:
    uid = int(me["id"])
    inc = float(me.get("monthly_income") or 0)
    if abs(inc - EXPECTED_INCOME) < 1:
        ok(f"monthly_income INR {inc:,.0f} (expected {EXPECTED_INCOME:,.0f})")
    elif inc > 0:
        ok(f"monthly_income INR {inc:,.0f} (seed may differ from {EXPECTED_INCOME:,.0f})")
    else:
        fail("profile", "monthly_income missing or zero", json.dumps(me)[:200])
    if me.get("onboarding_completed") in (True, "true", 1):
        ok("onboarding_completed=true")
    else:
        fail("profile", "onboarding not completed", "")
    return uid


def check_bank_and_data(token: str, uid: int) -> None:
    st = requests.get(
        f"{BASE}/onboarding/status",
        headers=hdr(token),
        params={"user_id": uid},
        timeout=30,
    )
    if st.status_code == 200:
        b = st.json()
        ok(
            f"banks_linked={b.get('banks_linked')} "
            f"transactions_count={b.get('transactions_count')}"
        )
        if int(b.get("transactions_count") or 0) < 10:
            fail("data", "very few transactions for Karan demo user", json.dumps(b))
    else:
        fail("bank", "onboarding status", st.text[:200])

    banks = requests.get(f"{BASE}/onboarding/banks", timeout=15)
    if banks.status_code == 200:
        ok("bank list available")

    src = requests.get(f"{BASE}/sources/connected", headers=hdr(token), params={"user_id": uid}, timeout=30)
    if src.status_code == 200:
        data = src.json()
        sources = data if isinstance(data, list) else data.get("sources") or []
        ok(f"connected_sources={len(sources)} (bank-link / statement sources)")
    else:
        fail("bank", "connected sources", src.text[:200])


def check_dashboard(token: str, uid: int) -> None:
    r = requests.get(
        f"{BASE}/transactions/{uid}",
        headers=hdr(token),
        params={"limit": 20},
        timeout=60,
    )
    if r.status_code != 200:
        fail("dashboard", "transactions list", r.text[:200])
        return
    rows = r.json()
    if isinstance(rows, dict):
        rows = rows.get("transactions") or rows.get("items") or []
    if len(rows) >= 5:
        ok(f"transactions list count={len(rows)}")
    else:
        fail("dashboard", "transaction list too small", f"count={len(rows)}")

    summ = requests.get(
        f"{BASE}/transactions/{uid}/summary",
        headers=hdr(token),
        params={"month": date.today().month, "year": date.today().year},
        timeout=30,
    )
    if summ.status_code == 200:
        s = summ.json()
        ok(
            f"summary income={float(s.get('total_income') or 0):,.0f} "
            f"expense={float(s.get('total_expense') or 0):,.0f} "
            f"count={s.get('transaction_count')}"
        )
    else:
        fail("dashboard", "monthly summary", summ.text[:200])

    for path, timeout in [
        (f"/analysis/{uid}/trends", 60),
        (f"/financial-state/{uid}", 60),
        (f"/dashboard/{uid}", 120),
    ]:
        try:
            tr = requests.get(f"{BASE}{path}", headers=hdr(token), timeout=timeout)
            if tr.status_code == 200:
                ok(f"GET {path}")
            else:
                fail("dashboard", path, tr.text[:200])
        except requests.exceptions.Timeout:
            fail("dashboard", f"{path} timed out", f">{timeout}s")


def check_features(token: str, uid: int) -> None:
    checks = [
        ("insights", f"/insights/{uid}", 90),
        ("fraud alerts", f"/fraud-shield/{uid}/alerts", 60),
        ("fraud stats", f"/fraud-shield/{uid}/stats", 60),
        ("dark patterns", f"/dark-patterns/{uid}", 90),
        ("festival", f"/festivals/{uid}", 60),
        ("emi", f"/emi/{uid}", 60),
        ("subscriptions", f"/subscriptions/{uid}", 60),
        ("pattern alerts", f"/pattern-alerts/{uid}/active", 60),
        ("health score", f"/health-score/{uid}", 30),
    ]
    for name, path, timeout in checks:
        r = requests.get(f"{BASE}{path}", headers=hdr(token), timeout=timeout)
        if r.status_code == 200:
            ok(name)
        else:
            fail(name, path, r.text[:200])

    goal = requests.post(
        f"{BASE}/purchases/{uid}/add-goal",
        headers=hdr(token),
        json={
            "item_name": "Karan QA Test",
            "target_amount": 25000,
            "target_date": (date.today() + timedelta(days=90)).isoformat(),
            "use_emi": False,
        },
        timeout=30,
    )
    if goal.status_code in (200, 201):
        ok("purchase planner add goal")
    else:
        fail("purchase", "add goal", goal.text[:200])


def main() -> int:
    print(f"\n=== Karan Full App Test (signin only, NO PDF) ===")
    print(f"API: {BASE}")
    print(f"User: {EMAIL} | income target INR {EXPECTED_INCOME:,.0f}\n")

    try:
        requests.get(BASE.replace("/api", "/health"), timeout=15).raise_for_status()
        ok("backend health")
    except Exception as exc:
        fail("infra", "backend down", str(exc))
        return 1

    token, me = signin()
    uid = check_profile(me)
    check_bank_and_data(token, uid)
    check_dashboard(token, uid)
    check_features(token, uid)

    print(f"\n=== SUMMARY ===")
    print(f"Passed: {len(passed)}")
    print(f"Failed: {len(issues)}")
    if issues:
        for i, x in enumerate(issues, 1):
            print(f"  {i}. [{x['area']}] {x['msg']}")
        return 1
    print("\nAll Karan full-app checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
