# start-backend.ps1
# Kills any process listening on the backend port (default 8001) then starts
# uvicorn fresh with --reload. Stops the "zombie uvicorn worker on port 8000"
# problem from happening again.
#
# Usage:
#   .\start-backend.ps1            # uses port 8001
#   .\start-backend.ps1 -Port 8000 # use a different port

param(
    [int]$Port = 8001
)

Write-Host "[start-backend] Looking for processes on port $Port ..." -ForegroundColor Cyan

# Collect all PIDs that are LISTENING on the given port.
$pidsToKill = @()
try {
    $netstat = netstat -ano | Select-String ":$Port\s"
    foreach ($line in $netstat) {
        $tokens = ($line.ToString() -split "\s+") | Where-Object { $_ -ne "" }
        $candidate = $tokens[-1]
        if ($candidate -match '^\d+$' -and [int]$candidate -ne 0) {
            $pidsToKill += [int]$candidate
        }
    }
} catch {
    Write-Host "[start-backend] netstat scan failed: $_" -ForegroundColor Yellow
}

$pidsToKill = $pidsToKill | Sort-Object -Unique
foreach ($p in $pidsToKill) {
    try {
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
        Write-Host "[start-backend] Killed PID $p" -ForegroundColor Yellow
    } catch {
        # ignore: process may already be gone
    }
}

if ($pidsToKill.Count -gt 0) {
    Start-Sleep -Seconds 2
}

Write-Host "[start-backend] Starting uvicorn on http://127.0.0.1:$Port ..." -ForegroundColor Green
Set-Location -Path "$PSScriptRoot\backend"
uvicorn main:app --host 127.0.0.1 --port $Port --reload
