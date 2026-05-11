import requests, json
r = requests.post('http://localhost:8001/api/auth/signin', json={'email':'abc@gmail.com','password':'Pass@123'}, timeout=5)
token = r.json()['access_token']
headers = {'Authorization': 'Bearer ' + token}
sr = requests.get('http://localhost:8001/api/subscriptions/5', headers=headers, timeout=10)
d = sr.json()
print('active_count:', d.get('active_count'))
print('suspicious_count:', d.get('suspicious_count'))
print('dead_count:', d.get('dead_count'))
subs = d.get('subscriptions', [])
print(f'Subscriptions returned: {len(subs)}')
for s in subs:
    name = s.get('service_name') or s.get('name') or 'unknown'
    print(f"  - {name} status={s.get('status')} amount={s.get('amount')}")
