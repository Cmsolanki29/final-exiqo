import requests, json
r = requests.post('http://localhost:8001/api/auth/signin', json={'email':'abc@gmail.com','password':'Pass@123'}, timeout=5)
token = r.json()['access_token']
headers = {'Authorization': 'Bearer ' + token}

check_r = requests.post('http://localhost:8001/api/fraud-shield/5/check-transaction',
    json={'merchant': 'foreignwire99@ybl', 'amount': 175000, 'payment_method': 'IMPS', 'time': '03:45', 'location': 'International'},
    headers=headers, timeout=20)
d = check_r.json()
print(f"HIGH RISK score: {d['risk_score']} level={d['risk_level']}")
print(f"Risk factors: {d['risk_factors']}")
print(f"Model comparison: {json.dumps(d.get('model_comparison'), indent=2)}")
