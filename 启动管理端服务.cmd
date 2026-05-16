@echo off
setlocal
cd /d "%~dp0"

echo [INFO] Script directory: %~dp0

if not exist "server\app.py" (
  echo [ERROR] server\app.py not found.
  echo [ERROR] Please place this .cmd in the project root folder.
  exit /b 1
)

if not exist "requirements.txt" (
  echo [ERROR] requirements.txt not found.
  echo [ERROR] Please place this .cmd in the project root folder.
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
  exit /b 1
)

echo [INFO] Python command: %PY_CMD%
call %PY_CMD% --version

echo [INFO] Checking required modules...
call %PY_CMD% -c "import fastapi,uvicorn,pydantic,requests" >nul 2>nul
if errorlevel 1 (
  echo [INFO] Missing modules, trying pip install...
  call %PY_CMD% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [WARN] Online install failed (network/proxy maybe blocked).
    if exist "wheelhouse" (
      echo [INFO] Trying offline install from wheelhouse...
      call %PY_CMD% -m pip install --no-index --find-links=wheelhouse -r requirements.txt
    )
  )
)

call %PY_CMD% -c "import fastapi,uvicorn,pydantic,requests" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Dependencies are still missing.
  echo [TIP] Option A: enable internet and run: %PY_CMD% -m pip install -r requirements.txt
  echo [TIP] Option B: copy offline wheels into .\wheelhouse then rerun this script.
  exit /b 1
)

echo [INFO] Opening dashboard URL...
start "" "http://192.168.30.212:8000/dashboard"

echo [INFO] Starting Jeson management service in a new window...
start "Jeson管理端服务" cmd /k "cd /d "%~dp0" && %PY_CMD% -m uvicorn server.app:app --host 0.0.0.0 --port 8000"

echo [INFO] Launcher finished.
exit /b 0
