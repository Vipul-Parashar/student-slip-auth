# PowerShell Launcher for Smart QR Student Slip Generator & Authentication
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host "    Smart QR Student Slip Generator & Authentication Website" -ForegroundColor Cyan
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host ""

# Check python
try {
    $pyVersion = python --version
    Write-Host "[OK] Detected: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python is not installed or not in PATH." -ForegroundColor Red
    Exit 1
}

# Virtual environment
if (-not (Test-Path "venv")) {
    Write-Host "[SETUP] Creating virtual environment (venv)..." -ForegroundColor Yellow
    python -m venv venv
}

if (Test-Path "venv\Scripts\Activate.ps1") {
    & "venv\Scripts\Activate.ps1"
}

Write-Host "[SETUP] Installing requirements..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet

Write-Host "[INIT] Initializing database..." -ForegroundColor Yellow
python scripts/init_db.py

Write-Host ""
Write-Host "===================================================================" -ForegroundColor Green
Write-Host "  Server URL:       http://localhost:8000" -ForegroundColor White
Write-Host "  Admin Login:      http://localhost:8000/login" -ForegroundColor White
Write-Host "  QR Scanner:       http://localhost:8000/scan" -ForegroundColor White
Write-Host "  Default Username: admin" -ForegroundColor White
Write-Host "  Default Password: AdminPass@2026" -ForegroundColor White
Write-Host "===================================================================" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server.`n"

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
