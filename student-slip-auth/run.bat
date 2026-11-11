@echo off
setlocal enabledelayedexpansion

echo ===================================================================
echo     Smart QR Student Slip Generator ^& Authentication Website
echo ===================================================================
echo.

:: Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10 or newer from https://www.python.org/
    pause
    exit /b 1
)

:: Virtual environment setup (optional, creates if not exists)
if not exist "venv" (
    echo [SETUP] Creating Python virtual environment...
    python -m venv venv
)

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo [SETUP] Verifying and installing required packages...
pip install -r requirements.txt --quiet

echo.
echo [INIT] Initializing database and admin account...
python scripts\init_db.py

echo.
echo ===================================================================
echo   Server is starting at: http://localhost:8000
echo   Admin Portal:          http://localhost:8000/login
echo   QR Scanner:            http://localhost:8000/scan
echo   Default Username:      admin
echo   Default Password:      AdminPass@2026
echo ===================================================================
echo Press Ctrl+C in this window to stop the server.
echo.

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
