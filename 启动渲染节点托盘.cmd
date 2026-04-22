@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Please install Python and add it to PATH.
  pause
  exit /b 1
)

echo [INFO] Starting Jeson tray worker...
python agent\tray_worker.py
if errorlevel 1 (
  echo [ERROR] Tray worker failed. Run: pip install -r requirements.txt
  pause
)
