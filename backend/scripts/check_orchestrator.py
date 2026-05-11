import requests, json

r = requests.post('http://localhost:8001/api/auth/signin', json={'email':'abc@gmail.com','password':'Pass@123'}, timeout=5)
token = r.json()['access_token']
headers = {'Authorization': 'Bearer ' + token, 'X-Admin-Token': 'dev-admin-secret'}

# Test orchestrator costs today
oc = requests.get('http://localhost:8001/api/risk/orchestrator/costs/today', headers=headers, timeout=8)
print('Orchestrator costs/today:')
print(json.dumps(oc.json(), indent=2)[:500])

# Test investigation costs
ic = requests.get('http://localhost:8001/api/risk/investigations/budget/today', headers=headers, timeout=8)
print('\nInvestigation budget/today:')
d = ic.json()
print(f"  Date: {d.get('date')}")
print(f"  Phase 9 investigations: {d.get('phase_9_investigations')}")
print(f"  Total requests: {sum(m.get('requests',0) for m in d.get('models',{}).values())}")

# Test DNN runs
dn = requests.get('http://localhost:8001/api/risk/dnn/runs', headers=headers, timeout=8)
dr = dn.json()
print(f'\nDNN runs: {len(dr.get("runs",[]))} runs found')

# Test GNN status
gs = requests.get('http://localhost:8001/api/risk/gnn/status', headers=headers, timeout=8)
gr = gs.json()
print(f'GNN status: embeddings={gr.get("embeddings",{}).get("total")} model_version={gr.get("embeddings",{}).get("model_version")}')

# Test shadow evaluation
se = requests.get('http://localhost:8001/api/risk/dnn/shadow/evaluation', headers=headers, timeout=8)
sr = se.json()
print(f'DNN shadow eval: passed={sr.get("passed")} score_psi={sr.get("score_psi")}')
