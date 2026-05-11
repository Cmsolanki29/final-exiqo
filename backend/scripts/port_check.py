import requests

for url in [
    "http://localhost:8001/health",
    "http://localhost:8001/api/fraud-shield/5/stats",
    "http://localhost:8001/api/risk/orchestrator/costs/today",
    "http://localhost:8001/api/fraud-shield/rings",
    "http://localhost:8001/api/risk/investigations/1",
    "http://localhost:8001/api/risk/dnn/health",
    "http://localhost:8001/api/risk/gnn/health",
]:
    try:
        r = requests.get(url, timeout=5, headers={"X-Admin-Token": "dev-admin-secret"})
        print(f"[{r.status_code}] {url}")
        if r.status_code != 200:
            print(f"   -> {r.text[:100]}")
    except Exception as e:
        print(f"[ERR] {url} -> {e}")
