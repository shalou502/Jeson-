@echo off
setlocal
cd /d "%~dp0"

set HOST=0.0.0.0
set PORT=8000
set DASHBOARD_URL=http://192.168.30.212:8000/dashboard

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Please install Python and add it to PATH.
  pause
  exit /b 1
)

echo [INFO] Checking Python dependencies...
python -c "import fastapi,uvicorn,requests" >nul 2>nul
if errorlevel 1 (
  echo [INFO] Installing dependencies from requirements.txt ...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [ERROR] Dependency install failed.
    pause
    exit /b 1
  )
)

echo [INFO] Starting Jeson management service in a new window...
start "Jeson管理端服务" cmd /k "cd /d "%~dp0" && python -m uvicorn server.app:app --host %HOST% --port %PORT%"

echo [INFO] Waiting service health check...
set OK=
for /l %%i in (1,1,30) do (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:%PORT%/health' -UseBasicParsing -TimeoutSec 2).StatusCode } catch { '' }" | findstr /r "^200$" >nul
  if not errorlevel 1 (
    set OK=1
    goto :READY
  )
  timeout /t 1 >nul
)

:READY
if defined OK (
  echo [INFO] Service is up. Opening dashboard...
  start "" "%DASHBOARD_URL%"
) else (
  echo [WARN] Service did not pass health check in time.
  echo [WARN] Please check firewall/port and the service window logs.
  echo [INFO] You can still try: %DASHBOARD_URL%
)

echo.
echo [INFO] Done.
pause
