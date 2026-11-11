#!/usr/bin/env bash
set -e

echo "==================================================================="
echo "    Smart QR Student Slip Generator & Authentication Website"
echo "==================================================================="
echo ""

# Python check
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 could not be found. Please install Python 3.10+."
    exit 1
fi

# Virtualenv
if [ ! -d "venv" ]; then
    echo "[SETUP] Creating virtual environment (venv)..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "[SETUP] Installing dependencies..."
pip install -r requirements.txt --quiet

echo "[INIT] Initializing database..."
python3 scripts/init_db.py

echo ""
echo "==================================================================="
echo "  Server running at: http://localhost:8000"
echo "  Admin Login:       http://localhost:8000/login"
echo "  QR Scanner:        http://localhost:8000/scan"
echo "  Default Username:  admin"
echo "  Default Password:  AdminPass@2026"
echo "==================================================================="
echo "Press Ctrl+C to terminate."
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
