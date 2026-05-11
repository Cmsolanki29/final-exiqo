"""Integration check - verify all phase API routes return expected data."""
import requests

HEADERS = {"X-Admin-Token": "dev-admin-secret"}
BASE = "http://localhost:8001"
USER_ID = 5

checks = [
    ("GET", f"{BASE}/health", None, "status"),
    ("GET", f"{BASE}/api/fraud-shield/{USER_ID}/stats", None, "threats_blocked"),
    ("GET", f"{BASE}/api/risk/orchestrator/costs/today", None, "phase_9_calls"),
    ("GET", f"{BASE}/api/fraud-shield/rings", None, None),
    ("GET", f"{BASE}/api/risk/dnn/health", None, "model_loaded"),
    ("GET", f"{BASE}/api/risk/gnn/health", None, "model_loaded"),
    ("GET", f"{BASE}/api/risk/investigations/health", None, None),
    ("GET", f"{BASE}/api/risk/review-queue", None, None),
    ("GET", f"{BASE}/api/fraud-shield/{USER_ID}/alerts", None, None),
    ("GET", f"{BASE}/api/health-score/{USER_ID}", None, "score"),
]

passed = 0
failed = 0
for method, url, body, key in checks:
    try:
        r = requests.get(url, headers=HEADERS, timeout=5)
        status = "[OK]" if r.status_code == 200 else f"[{r.status_code}]"
        val = ""
        if r.status_code == 200 and key:
            try:
                d = r.json()
                val = f" | {key}={d.get(key, '?')}"
            except Exception:
                pass
        print(f"{status} {url.replace(BASE, '')}{val}")
        if r.status_code == 200:
            passed += 1
        else:
            failed += 1
            print(f"   ERROR: {r.text[:80]}")
    except Exception as e:
        print(f"[ERR] {url.replace(BASE, '')} -> {e}")
        failed += 1

print(f"\nResults: {passed} passed, {failed} failed out of {passed+failed} checks")
