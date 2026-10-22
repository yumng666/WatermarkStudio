@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY="
where pythonw >nul 2>nul && set "PY=pythonw"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  if exist "C:\Users\%USERNAME%\.workbuddy\binaries\python\envs\default\Scripts\pythonw.exe" (
    set "PY=C:\Users\%USERNAME%\.workbuddy\binaries\python\envs\default\Scripts\pythonw.exe"
  )
)
if not defined PY (
  echo 未找到 Python，请先安装 Python 3.10+ 并勾选 Add to PATH
  pause
  exit /b 1
)

start "" "%PY%" "%~dp0main.py"
