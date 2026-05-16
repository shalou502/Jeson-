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
  exit /b 1
)

echo [INFO] Python command: %PY_CMD%
call %PY_CMD% --version

echo [INFO] Checking tray dependencies...
call %PY_CMD% -c "import pystray,PIL,requests" >nul 2>nul
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

call %PY_CMD% -c "import pystray,PIL,requests" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Tray dependencies are still missing.
  echo [TIP] Option A: enable internet and run: %PY_CMD% -m pip install -r requirements.txt
  echo [TIP] Option B: copy offline wheels into .\wheelhouse then rerun this script.
  exit /b 1
)

echo [INFO] Starting Jeson tray worker...
start "Jeson渲染节点托盘" cmd /k "cd /d "%~dp0" && %PY_CMD% agent\tray_worker.py"

echo [INFO] Launcher finished.
exit /b 0
