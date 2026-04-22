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

echo [信息] 正在启动 Jeson 渲染节点托盘...
python agent\tray_worker.py
if errorlevel 1 (
  echo [错误] 启动失败，请检查依赖是否安装: pip install -r requirements.txt
  pause
)
