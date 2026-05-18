"""
Comprehensive QA audit script — API-level validation for CTO protocol.
Run: cd backend && python scripts/qa_comprehensive_audit.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

# Default matches frontend/package.json proxy (8001). Override: QA_API_BASE=http://127.0.0.1:8765/api
BASE = os.getenv("QA_API_BASE", "http://127.0.0.1:8001/api")
SAMPLES = Path(__file__).resolve().parents[2] / "test samples"

issues: list[dict] = []
passed: list[str] = []


def ok(msg: str) -> None:
    passed.append(msg)
    print(f"  PASS  {msg}")


def fail(area: str, msg: str, detail: str = "") -> None:
    issues.append({"area": area, "msg": msg, "detail": detail})
    print(f"  FAIL  [{area}] {msg}" + (f" — {detail[:200]}" if detail else ""))


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def signup_user() -> tuple[str, int]:
    email = f"qa.audit.{int(time.time())}@example.com"
    r = requests.post(
        f"{BASE}/auth/signup",
        json={
            "name": "QA Audit User",
            "email": email,
            "password": "TestPass123!",
            "signup_connection": "add_later",
        },
        timeout=60,
    )
    if r.status_code != 201:
        fail("auth", "signup failed", r.text)
        sys.exit(1)
    data = r.json()
    token = data["access_token"]
    # decode user_id from /auth/me
    me = requests.get(f"{BASE}/auth/me", headers=auth_headers(token), timeout=30)
    uid = me.json().get("id") or me.json().get("user_id")
    ok(f"signup user_id={uid} email={email}")
    return token, int(uid)


def test_health() -> None:
    r = requests.get(BASE.replace("/api", "") + "/health", timeout=5)
    if r.status_code == 200:
        ok("backend health")
    else:
        fail("infra", "health check", str(r.status_code))


def test_password_validation() -> None:
    r = requests.post(
        f"{BASE}/auth/signup",
        json={
            "name": "X",
            "email": f"weak.{int(time.time())}@example.com",
            "password": "123",
            "signup_connection": "add_later",
        },
        timeout=15,
    )
    if r.status_code in (400, 422):
        ok("weak password rejected")
    else:
        fail("auth", "weak password should be rejected", r.text[:200])


def test_bank_connection(token: str, uid: int) -> None:
    mobile = "9876543210"
    send = requests.post(f"{BASE}/otp/send", json={"mobile_number": mobile}, timeout=15)
    if send.status_code != 200:
        fail("connection", "otp send", send.text[:200])
        return
    otp = send.json().get("otp_code")
    ver = requests.post(
        f"{BASE}/otp/verify",
        json={"mobile_number": mobile, "otp_code": str(otp)},
        timeout=15,
    )
    if ver.status_code != 200:
        fail("connection", "otp verify", ver.text[:200])
        return
    r = requests.post(
        f"{BASE}/onboarding/link-bank",
        headers=auth_headers(token),
        json={"user_id": uid, "bank_slug": "hdfc", "mobile_number": mobile},
        timeout=60,
    )
    if r.status_code in (200, 201):
        ok("bank connection (OTP + link-bank)")
    else:
        fail("connection", "bank connect", r.text[:300])


def test_credit_card(token: str, uid: int) -> None:
    pdf = SAMPLES / "AXIS_CREDIT_CARD_STATEMENT_Vikram_REALISTIC.pdf"
    if not pdf.exists():
        fail("connection", "credit card sample PDF missing", str(pdf))
        return
    with pdf.open("rb") as f:
        r = requests.post(
            f"{BASE}/documents/upload",
            headers=auth_headers(token),
            data={
                "user_id": str(uid),
                "source_type": "credit_card",
                "institution_name": "Axis Magnus QA",
                "added_via": "settings_upload",
            },
            files={"file": (pdf.name, f, "application/pdf")},
            timeout=180,
        )
    if r.status_code in (200, 201):
        body = r.json()
        imported = body.get("imported") or body.get("transactions_imported") or 0
        ok(f"credit card statement upload imported={imported}")
    else:
        fail("connection", "credit card upload", r.text[:400])


def test_statement_upload(token: str, uid: int) -> None:
    pdf = SAMPLES / "AXIS_BANK_ACCOUNT_STATEMENT_SAMPLE_Vikram_Singh.pdf"
    if not pdf.exists():
        fail("connection", "sample PDF missing", str(pdf))
        return
    with pdf.open("rb") as f:
        r = requests.post(
            f"{BASE}/documents/upload",
            headers=auth_headers(token),
            data={
                "user_id": str(uid),
                "source_type": "bank_statement_pdf",
                "institution_name": "HDFC Bank QA",
                "added_via": "settings_upload",
            },
            files={"file": (pdf.name, f, "application/pdf")},
            timeout=180,
        )
    if r.status_code in (200, 201):
        body = r.json()
        imported = body.get("imported") or body.get("transactions_imported") or 0
        ok(f"statement upload imported={imported}")
        if imported == 0:
            fail("connection", "PDF uploaded but 0 transactions", json.dumps(body)[:300])
    else:
        fail("connection", "statement upload", r.text[:400])


def test_dashboard(token: str, uid: int) -> None:
    for path in [
        f"/analysis/{uid}/trends",
        f"/financial-state/{uid}",
    ]:
        r = requests.get(f"{BASE}{path}", headers=auth_headers(token), timeout=60)
        if r.status_code == 200:
            ok(f"dashboard endpoint {path}")
        else:
            fail("dashboard", path, r.text[:200])


def test_transactions(token: str, uid: int) -> None:
    r = requests.get(
        f"{BASE}/transactions/{uid}",
        headers=auth_headers(token),
        params={"limit": 50},
        timeout=60,
    )
    if r.status_code != 200:
        fail("transactions", "list", r.text[:200])
        return
    txns = r.json()
    if isinstance(txns, dict):
        txns = txns.get("transactions") or txns.get("items") or []
    ok(f"transactions count={len(txns)}")
    if len(txns) == 0:
        fail("transactions", "no transactions after signup seed", "")


def test_purchase_emi_link(token: str, uid: int) -> None:
    r = requests.post(
        f"{BASE}/purchases/{uid}/add-goal",
        headers=auth_headers(token),
        json={
            "item_name": "QA Test Laptop",
            "target_amount": 120000,
            "target_date": (date.today() + timedelta(days=180)).isoformat(),
            "use_emi": True,
            "emi_tenure_months": 12,
            "interest_rate_annual": 14.0,
            "down_payment": 20000,
        },
        timeout=30,
    )
    if r.status_code not in (200, 201):
        fail("purchase", "add goal with EMI", r.text[:300])
        return
    goal = r.json()
    goal_id = goal.get("id") or goal.get("goal_id")
    ok(f"purchase goal created id={goal_id}")

    emi_r = requests.get(f"{BASE}/emi/{uid}", headers=auth_headers(token), timeout=60)
    if emi_r.status_code == 200:
        ok("emi report after purchase goal")
    else:
        fail("emi", "get report", emi_r.text[:200])

    fs = requests.get(f"{BASE}/financial-state/{uid}", headers=auth_headers(token), timeout=30)
    if fs.status_code == 200:
        ok("financial state after purchase")
    else:
        fail("savings", "financial-state", fs.text[:200])

    # Postpone test
    if goal_id:
        target = goal.get("target_date") or (date.today() + timedelta(days=180)).isoformat()
        try:
            td = datetime.strptime(str(target)[:10], "%Y-%m-%d").date()
        except ValueError:
            td = date.today() + timedelta(days=180)
        new_td = (td + timedelta(days=30)).isoformat()
        post = requests.post(
            f"{BASE}/purchases/{uid}/goals/{goal_id}/postpone",
            headers=auth_headers(token),
            json={"new_target_date": new_td, "reason": "QA festival defer"},
            timeout=30,
        )
        if post.status_code in (200, 201):
            ok("purchase postpone")
        else:
            fail("purchase", "postpone", post.text[:200])


def test_festival(token: str, uid: int) -> None:
    r = requests.get(f"{BASE}/festivals/{uid}", headers=auth_headers(token), timeout=30)
    if r.status_code == 200:
        ok("festival predictor")
    else:
        fail("festival", "get festivals", r.text[:200])


def test_insights_fraud_dark(token: str, uid: int) -> None:
    for name, path in [
        ("insights", f"/insights/{uid}"),
        ("fraud alerts", f"/fraud-shield/{uid}/alerts"),
        ("fraud stats", f"/fraud-shield/{uid}/stats"),
        ("dark patterns", f"/dark-patterns/{uid}"),
    ]:
        r = requests.get(f"{BASE}{path}", headers=auth_headers(token), timeout=90)
        if r.status_code == 200:
            ok(name)
        else:
            fail(name, path, r.text[:200])


def main() -> None:
    print(f"\n=== SmartSpend QA Audit ===\nAPI: {BASE}\n")
    test_health()
    test_password_validation()
    token, uid = signup_user()
    test_bank_connection(token, uid)
    test_credit_card(token, uid)
    test_statement_upload(token, uid)
    test_dashboard(token, uid)
    test_transactions(token, uid)
    test_purchase_emi_link(token, uid)
    test_festival(token, uid)
    test_insights_fraud_dark(token, uid)

    print(f"\n=== SUMMARY ===")
    print(f"Passed: {len(passed)}")
    print(f"Failed: {len(issues)}")
    if issues:
        print("\nIssues:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. [{issue['area']}] {issue['msg']}")
            if issue.get("detail"):
                print(f"     {issue['detail'][:150]}")
        sys.exit(1)
    print("\nAll API checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
