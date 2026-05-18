# Vikram + Axis bank link only (no PDF). Restart backend first:
#   .\start-backend.ps1 -Port 8810
$env:QA_API_BASE = "http://127.0.0.1:8810/api"
Set-Location "$PSScriptRoot\backend"
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe scripts\qa_vikram_bank_link_full.py
exit $LASTEXITCODE
