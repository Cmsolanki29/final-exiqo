"""
Upload AXIS_BANK_STATEMENT_REALISTIC_FULL_MAY2026.pdf and validate expected Vikram lines.
Run: cd backend && python scripts/validate_vikram_may2026.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests

BASE = os.getenv("QA_API_BASE", "http://127.0.0.1:8001/api")
PDF = Path(__file__).resolve().parents[2] / "test samples" / "AXIS_BANK_STATEMENT_REALISTIC_FULL_MAY2026.pdf"

# Expected lines from QA spec (amount, substring in description/merchant, type)
EXPECTED = [
    (68450, "INFOSYS", "CREDIT"),
    (2200, "RAHUL", "CREDIT"),
    (1350, "NEHA", "CREDIT"),
    (4000, "AMAN", "CREDIT"),
    (2800, "HARSH", "CREDIT"),
    (3840, "REIMBURSEMENT", "CREDIT"),
    (86, "INTEREST", "CREDIT"),
    (18000, "RENT", "DEBIT"),
    (1860, "MSEDCL", "DEBIT"),
    (284, "UBER", "DEBIT"),
    (649, "NETFLIX", "DEBIT"),
    (2430, "AMAZON", "DEBIT"),
    (1124, "BIGBASKET", "DEBIT"),
    (5000, "ATM", "DEBIT"),
    (488, "ZOMATO", "DEBIT"),
    (3000, "GROWW", "DEBIT"),
    (1500, "HPCL", "DEBIT"),
    (199, "GOOGLE PLAY", "DEBIT"),
    (525, "STARBUCKS", "DEBIT"),
    (4999, "META", "DEBIT"),
    (834, "SWIGGY", "DEBIT"),
    (1, "APPLE", "DEBIT"),
]


def _api_has_statement_filters() -> bool:
    root = BASE.rstrip("/").removesuffix("/api")
    try:
        spec = requests.get(f"{root}/openapi.json", timeout=5).json()
        params = spec.get("paths", {}).get("/api/transactions/{user_id}", {}).get("get", {}).get(
            "parameters", []
        )
        names = {p.get("name") for p in params}
        return "connected_source_id" in names and "uploaded_document_id" in names
    except Exception as exc:
        print(f"Could not load OpenAPI from {root}: {exc}")
        return False


def main() -> int:
    if not PDF.exists():
        print(f"Missing PDF: {PDF}")
        return 1

    if not _api_has_statement_filters():
        print(
            f"\nStale API at {BASE}: missing connected_source_id/uploaded_document_id filters.\n"
            "Port 8001 often keeps zombie uvicorn on Windows. Run:\n"
            "  .\\start-backend.ps1 -Port 8810\n"
            "  $env:QA_API_BASE='http://127.0.0.1:8810/api'\n"
            "Or reboot / clear port 8001, then .\\start-backend.ps1 -Port 8001\n"
        )
        return 1

    email = f"vikram.may.{int(time.time())}@example.com"
    r = requests.post(
        f"{BASE}/auth/signup",
        json={"name": "Vikram Singh", "email": email, "password": "TestPass123!", "signup_connection": "add_later"},
        timeout=60,
    )
    if r.status_code != 201:
        print("signup failed", r.status_code, r.text[:300])
        return 1
    token = r.json()["access_token"]
    me = requests.get(f"{BASE}/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    uid = me["id"]
    print(f"user_id={uid} email={email}")

    with PDF.open("rb") as f:
        up = requests.post(
            f"{BASE}/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            data={
                "user_id": str(uid),
                "source_type": "bank_statement_pdf",
                "institution_name": "Axis Bank Savings",
                "added_via": "settings_upload",
            },
            files={"file": (PDF.name, f, "application/pdf")},
            timeout=300,
        )
    if up.status_code != 200:
        print("upload failed", up.status_code, up.text[:500])
        return 1
    up_body = up.json()
    print("upload:", up.status_code, up_body)
    source_id = up_body.get("source_id")
    document_id = up_body.get("document_id")
    imported = int(up_body.get("imported") or 0)
    if not source_id:
        print("upload response missing source_id")
        return 1

    list_params: dict = {
        "limit": 200,
        "month": 5,
        "year": 2026,
        "connected_source_id": source_id,
    }
    if document_id:
        list_params["uploaded_document_id"] = document_id
    tx = requests.get(
        f"{BASE}/transactions/{uid}",
        headers={"Authorization": f"Bearer {token}"},
        params=list_params,
        timeout=60,
    ).json()
    if isinstance(tx, list):
        rows = tx
    elif isinstance(tx, dict):
        rows = tx.get("transactions") or tx.get("items") or []
    else:
        rows = []

    print(
        f"\nStatement transactions (source_id={source_id}, document_id={document_id}, "
        f"upload imported={imported}): {len(rows)}"
    )
    if imported and len(rows) != imported:
        print(
            f"WARNING: row count {len(rows)} != upload imported {imported} "
            "(restart backend on port 8001 if filters are ignored)"
        )
    for t in sorted(rows, key=lambda x: (x.get("transaction_date") or "", x.get("amount") or 0)):
        print(
            f"  {t.get('transaction_date','')[:10]} | {t.get('type','?'):6} | "
            f"INR {float(t.get('amount') or 0):>8,.0f} | {t.get('category','?')[:20]:20} | "
            f"{(t.get('merchant') or t.get('description') or '')[:60]}"
        )

    missing = []
    for amount, needle, typ in EXPECTED:
        found = False
        for t in rows:
            desc = f"{t.get('merchant','')} {t.get('description','')}".upper()
            if needle.upper() in desc and abs(float(t.get("amount") or 0) - amount) < 1:
                if (t.get("type") or "").upper() == typ:
                    found = True
                    break
        if not found:
            missing.append(f"{typ} INR {amount:,} {needle}")

    inc = sum(float(t["amount"]) for t in rows if (t.get("type") or "").upper() == "CREDIT")
    exp = sum(float(t["amount"]) for t in rows if (t.get("type") or "").upper() == "DEBIT")
    print(f"\nTotals (statement source): income=INR {inc:,.0f} expenses=INR {exp:,.0f} net=INR {inc-exp:,.0f}")
    print(f"Expected income lines sum (spec): INR {sum(a for a, _, t in EXPECTED if t == 'CREDIT'):,.0f}")

    summ = requests.get(
        f"{BASE}/transactions/{uid}/summary",
        headers={"Authorization": f"Bearer {token}"},
        params={"month": 5, "year": 2026},
        timeout=30,
    ).json()
    print(
        f"API summary May 2026: income={summ.get('total_income')} "
        f"expense={summ.get('total_expense')} count={summ.get('transaction_count')}"
    )

    if missing:
        print("\nMISSING:")
        for m in missing:
            print(f"  - {m}")
        return 1
    print("\nAll expected lines matched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
