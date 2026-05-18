# Karan demo user — full app API test (no PDF)
# Signin: karan@smartspend.in / Demo@1234
.\start-backend.ps1 -Port 8810
Start-Sleep -Seconds 12
$env:QA_API_BASE = "http://127.0.0.1:8810/api"
Set-Location "$PSScriptRoot\backend"
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe scripts\qa_karan_full_app_test.py
exit $LASTEXITCODE
