@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 Python，请先安装 Python 并加入 PATH。
  pause
  exit /b 1
)

echo [信息] 启动 Jeson 管理服务 (FastAPI)...
python -m uvicorn server.app:app --host 0.0.0.0 --port 8000
if errorlevel 1 (
  echo [错误] 启动失败，请先执行: pip install -r requirements.txt
  pause
)
