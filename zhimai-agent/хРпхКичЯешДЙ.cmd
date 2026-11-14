@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 未找到运行环境。请先按照 README.md 创建 .venv 并安装依赖。
  pause
  exit /b 1
)
echo 知脉正在启动，请保持此窗口打开。
echo 访问地址: http://127.0.0.1:8765
start "" "http://127.0.0.1:8765"
".venv\Scripts\python.exe" server.py
pause
