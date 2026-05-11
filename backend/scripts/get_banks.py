import requests
import sys

sys.stdout.reconfigure(encoding='utf-8')

r = requests.get('http://localhost:8001/api/onboarding/available-banks', timeout=5)
data = r.json()
banks = data if isinstance(data, list) else data.get('banks', data)
print("Available banks in UI:")
for b in banks:
    name = b.get('name', b) if isinstance(b, dict) else b
    print(f"  - {name}")
