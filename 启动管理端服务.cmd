@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Please install Python and add it to PATH.
  pause
  exit /b 1
)

echo [INFO] Opening dashboard in browser...
start "" "http://192.168.30.212:8000/dashboard"

echo [INFO] Starting Jeson management service...
python -m uvicorn server.app:app --host 0.0.0.0 --port 8000
if errorlevel 1 (
  echo [ERROR] Service failed. Run: pip install -r requirements.txt
  pause
)
