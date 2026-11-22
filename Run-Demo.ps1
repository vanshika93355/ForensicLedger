$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "`n=== ForensicLedger: One-click faculty demo ===" -ForegroundColor Cyan

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[1/5] Creating virtual environment..."
    py -m venv .venv
}
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

Write-Host "[2/5] Installing/checking dependencies..."
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed. Check internet and try again." }

Write-Host "[3/5] Running automated tests..."
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Automated tests failed. Review the errors above." }

Write-Host "[4/5] Starting Flask API..."
$existing = $null
try { $existing = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/health" -TimeoutSec 2 } catch {}
$server = $null
if (-not $existing) {
    $server = Start-Process -FilePath $python -ArgumentList "backend/app.py" -WorkingDirectory $PSScriptRoot -PassThru -WindowStyle Minimized
    $ready = $false
    for ($i=0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/health" -TimeoutSec 2
            if ($health.status -eq "ok") { $ready = $true; break }
        } catch {}
    }
    if (-not $ready) {
        if ($server) { Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue }
        throw "Flask did not start on port 5000. Close any conflicting app and retry."
    }
} else {
    Write-Host "An API server is already running on port 5000; using it."
}

try {
    Write-Host "[5/5] Running live API demonstration..."
    & $python scripts\run_demo.py
    if ($LASTEXITCODE -ne 0) { throw "Demo failed. Review the error above." }
    Write-Host "`nSUCCESS: Open faculty_demo_report.html in your browser." -ForegroundColor Green
    Start-Process (Join-Path $PSScriptRoot "faculty_demo_report.html")
} finally {
    if ($server) {
        Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
        Write-Host "Demo server stopped. Run this script again whenever you need the demo."
    }
}
