@echo off
title Smart QR Slip System - Online Live Server
setlocal enabledelayedexpansion

echo ===================================================================
echo     Smart QR Student Slip Generator & Authentication Website
echo                     ONLINE LIVE SHARING TOOL
echo ===================================================================
echo.

cd /d "%~dp0"

:: Start Uvicorn Server in a new window
echo [1/2] Starting local web server on port 8000...
start "SlipAuth Server (Port 8000)" cmd /k "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

:: Wait 2 seconds for server startup
timeout /t 2 /nobreak >nul

:: Start Cloudflare Tunnel
echo [2/2] Connecting to Cloudflare Tunnel for secure public HTTPS link...
echo.
echo ===================================================================
echo   Look for your public HTTPS link below (ending in .trycloudflare.com)
echo   Send that link to your teacher so she can open it on her phone!
echo ===================================================================
echo.

"cloudflared.exe" tunnel --url http://127.0.0.1:8000
pause
