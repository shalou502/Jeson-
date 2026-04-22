@echo off
setlocal
cd /d "%~dp0"

echo [INFO] Script directory: %~dp0

if not exist "server\app.py" (
  echo [ERROR] server\app.py not found.
  echo [ERROR] Please place this .cmd in the project root folder.
  pause
  exit /b 1
)

if not exist "requirements.txt" (
  echo [ERROR] requirements.txt not found.
  echo [ERROR] Please place this .cmd in the project root folder.
  pause
  exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Please install Python and add it to PATH.
  pause
  exit /b 1
)

echo [INFO] Python:
python --version

echo [INFO] Installing/checking dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip install failed.
  echo [TIP] Check network/proxy and run manually: python -m pip install -r requirements.txt
  pause
  exit /b 1
)

echo [INFO] Opening dashboard URL...
start "" "http://192.168.30.212:8000/dashboard"

echo [INFO] Starting Jeson management service...
echo [INFO] If startup fails, error details will be shown below.
python -m uvicorn server.app:app --host 0.0.0.0 --port 8000

echo.
echo [INFO] Service exited. Press any key to close.
pause
