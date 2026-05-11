"""
Fire 5 ultra-high-risk transactions via /decide with risk_score_override=95
to trigger Tier 4 and log Phase 12 judge calls.
"""
import requests
import os
import sys
from dotenv import load_dotenv

load_dotenv('../.env')

BASE_URL = "http://localhost:8001"
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dev-admin-secret")

# Login to get JWT
login_r = requests.post(f"{BASE_URL}/api/auth/signin",
    json={"email": "abc@gmail.com", "password": "Pass@123"}, timeout=10)
if login_r.status_code != 200:
    print(f"[FAIL] Login failed: {login_r.status_code} {login_r.text}")
    sys.exit(1)
token = login_r.json()["access_token"]
print(f"[OK] Login: token obtained")

headers = {
    "Authorization": f"Bearer {token}",
    "X-Admin-Token": ADMIN_TOKEN,
}

transactions = [
    {"amount": 175000, "merchant": "International Wire Transfer", "location": "Unknown", "category": "Wire"},
    {"amount": 220000, "merchant": "Crypto Exchange Offshore",   "location": "Foreign", "category": "Transfer"},
    {"amount": 98000,  "merchant": "Gift Card Bulk Purchase",    "location": "Unknown", "category": "Other"},
    {"amount": 150000, "merchant": "Unverified Merchant 9921",   "location": "International", "category": "Wire"},
    {"amount": 300000, "merchant": "Overseas Remittance Co",     "location": "Foreign", "category": "Transfer"},
]

print("\nFiring 5 ultra-high-risk transactions with risk_score_override=95...")
print("=" * 60)

judge_fired = 0
for i, txn in enumerate(transactions, 1):
    payload = {
        "user_id": 5,
        "txn": {
            "amount": txn["amount"],
            "merchant": txn["merchant"],
            "location": txn["location"],
            "category": txn["category"],
            "type": "DEBIT",
            "is_new_payee": True,
            "hour_of_day": 2,
            "is_night_txn": True,
        },
        "user": {"id": 5},
        "features": {
            "risk_score": 95,
            "anomaly_score": 0.97,
            "is_high_amount": True,
            "gnn_ring_flag": True,
            "dnn_score": 0.95,
        },
        "risk_score_override": 95,
    }

    try:
        r = requests.post(f"{BASE_URL}/api/risk/orchestrator/decide",
                         json=payload, headers=headers, timeout=60)
        if r.status_code != 200:
            print(f"[{i}] {txn['merchant'][:40]:40s} | HTTP {r.status_code}: {r.text[:100]}")
            continue

        d = r.json()
        tier = d.get("tier", "?")
        score = d.get("baseline_score", "?")
        judge = d.get("judge") or d.get("judge_result")
        judge_invoked = judge.get("invoked", False) if isinstance(judge, dict) else False
        if judge_invoked:
            judge_fired += 1

        print(f"[{i}] {txn['merchant'][:40]:40s} | tier={tier} | score={score} | judge={judge_invoked}")
    except Exception as e:
        print(f"[{i}] ERROR: {e}")

print("=" * 60)
print(f"Judge fired: {judge_fired}/5 transactions")

# Check orchestrator costs/calls
r = requests.get(f"{BASE_URL}/api/risk/orchestrator/costs/today",
                headers=headers, timeout=10)
if r.status_code == 200:
    costs = r.json()
    print(f"\nPhase 12 judge calls today: {costs.get('phase_12_judge_calls', 0)}")
    print(f"Phase 9 investigations today: {costs.get('phase_9_investigations', 0)}")
else:
    print(f"[WARN] costs endpoint: {r.status_code}")
