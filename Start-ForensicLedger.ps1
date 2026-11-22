$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host "   ForensicLedger — Chain of Custody System (v2.0)    " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Virtual environment not detected. Creating .venv..." -ForegroundColor Yellow
    py -m venv .venv
    & $python -m pip install -r requirements.txt
}

Write-Host "Starting ForensicLedger Application Server on http://127.0.0.1:5000 ..." -ForegroundColor Green

# Background probe loop to open browser only after server is ready
Start-Job -ScriptBlock {
    for ($i=0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 600
        try {
            $h = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/health" -TimeoutSec 1
            if ($h.status -eq "ok") {
                Start-Process "http://127.0.0.1:5000"
                break
            }
        } catch {}
    }
} | Out-Null

Write-Host "Web Dashboard will open in your default browser once the server is listening." -ForegroundColor Gray
Write-Host "Press Ctrl+C to terminate the application.`n" -ForegroundColor Yellow

# Launch Flask application
& $python backend/app.py
