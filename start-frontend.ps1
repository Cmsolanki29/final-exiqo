# start-frontend.ps1
# Convenience launcher for the React dev server.  Make sure frontend/.env.local
# points at the same port that start-backend.ps1 is using (default 8001).
#
# Usage:
#   .\start-frontend.ps1

Write-Host "[start-frontend] Starting React dev server (CRA) ..." -ForegroundColor Green
Set-Location -Path "$PSScriptRoot\frontend"
npm start
