@echo off
setlocal
cd /d "%~dp0"

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

echo [INFO] Starting Jeson tray worker...
call %PY_CMD% agent\tray_worker.py
if errorlevel 1 (
  echo [ERROR] Tray worker failed. Run: %PY_CMD% -m pip install -r requirements.txt
  pause
)
