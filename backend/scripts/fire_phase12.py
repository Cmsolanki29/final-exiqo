"""
Submit 5 ultra-high-risk transactions to fire Phase 12 judge.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")
import requests

BASE = "http://localhost:8001"

# Login
login = requests.post(f"{BASE}/api/auth/signin", json={"email": "abc@gmail.com", "password": "Pass@123"}, timeout=10)
token = login.json().get("access_token", "")
admin_token = os.getenv("ADMIN_TOKEN", "dev-admin-secret")
headers = {"Authorization": f"Bearer {token}", "X-Admin-Token": admin_token}
print(f"Login: {login.status_code}, user token obtained: {bool(token)}")

ULTRA_HIGH_RISK = [
    {"amount": 175000, "merchant": "International Wire Transfer", "location": "Unknown", "category": "Wire"},
    {"amount": 220000, "merchant": "Crypto Exchange Offshore",  "location": "Foreign",  "category": "Transfer"},
    {"amount": 98000,  "merchant": "Gift Card Bulk Purchase",   "location": "Unknown",  "category": "Other"},
    {"amount": 150000, "merchant": "Unverified Merchant 9921",  "location": "International", "category": "Wire"},
    {"amount": 300000, "merchant": "Overseas Remittance Co",    "location": "Foreign",  "category": "Transfer"},
]

print("\nSubmitting 5 ultra-high-risk transactions via /api/risk/orchestrator/decide...")
print("=" * 60)

judge_calls = 0
for i, txn in enumerate(ULTRA_HIGH_RISK, 1):
    # Correct payload format for /risk/orchestrator/decide
    # Pass features with a very high risk_score (95+) to force Tier 4
    payload = {
        "user_id": 5,
        "txn": {
            "amount": txn["amount"],
            "merchant": txn["merchant"],
            "location": txn["location"],
            "category": txn["category"],
            "description": f"High-risk test transaction {i}",
            "is_new_payee": True,
            "hour_of_day": 2,
            "is_night_txn": True,
            "type": "DEBIT",
        },
        "user": {"id": 5},
        "features": {
            # Force a risk score > 85 to trigger Tier 4 (Full Stack)
            "risk_score": 95,
            "anomaly_score": 0.97,
            "is_high_amount": True,
            "is_new_payee": True,
            "is_night_txn": True,
            "location_anomaly": True,
            "gnn_ring_flag": True,
            "dnn_score": 0.95,
        },
    }

    r = requests.post(f"{BASE}/api/risk/orchestrator/decide", json=payload, headers=headers, timeout=60)
    if r.status_code == 200:
        d = r.json()
        tier = (d.get("tier_used") or d.get("routing", {}).get("tier_label") or
                d.get("routing", {}).get("tier") or d.get("tier") or "?")
        risk = (d.get("final_score") or d.get("risk_score") or
                d.get("routing", {}).get("score") or "?")
        decision = d.get("decision") or d.get("action") or "?"
        judge_used = d.get("judge_used") or d.get("llm_judge_called") or False
        tier_num = d.get("routing", {}).get("tier") or 0
        if judge_used or "4" in str(tier) or tier_num >= 4:
            judge_calls += 1
        print(f"[{i}] {txn['merchant'][:40]:<40} | amount={txn['amount']:>8} | tier={tier} | risk={risk} | decision={decision} | judge={judge_used}")
    else:
        print(f"[{i}] FAIL {r.status_code}: {r.text[:200]}")

# Check judge call counter
print("\n" + "=" * 60)
costs = requests.get(f"{BASE}/api/risk/orchestrator/costs/today", headers=headers, timeout=10)
if costs.status_code == 200:
    d = costs.json()
    print("Orchestrator costs today:", d)

# Check health
orch_health = requests.get(f"{BASE}/api/health/orchestrator", timeout=10)
if orch_health.status_code == 200:
    print("Orchestrator health:", orch_health.json())

print(f"\nEstimated Phase 12 judge calls triggered: {judge_calls}")
print("Done.")
