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

set "PY_CMD="
where python >nul 2>nul
if not errorlevel 1 set "PY_CMD=python"
if "%PY_CMD%"=="" (
  where py >nul 2>nul
  if not errorlevel 1 set "PY_CMD=py -3"
)

if "%PY_CMD%"=="" (
  echo [ERROR] Python runtime not found.
  echo [TIP] Please install Python 3.x and check "Add python.exe to PATH".
  echo [TIP] Opening download page...
  start "" "https://www.python.org/downloads/windows/"
  pause
  exit /b 1
)

echo [INFO] Python command: %PY_CMD%
call %PY_CMD% --version

echo [INFO] Installing/checking dependencies...
call %PY_CMD% -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip install failed.
  echo [TIP] Check network/proxy and run manually: %PY_CMD% -m pip install -r requirements.txt
  pause
  exit /b 1
)

echo [INFO] Opening dashboard URL...
start "" "http://192.168.30.212:8000/dashboard"

echo [INFO] Starting Jeson management service...
echo [INFO] If startup fails, error details will be shown below.
call %PY_CMD% -m uvicorn server.app:app --host 0.0.0.0 --port 8000

echo.
echo [INFO] Service exited. Press any key to close.
pause
