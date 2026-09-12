@echo off
chcp 65001 >nul
cd /d %~dp0

:: 优先用本项目自带虚拟环境里的 python，否则退回系统 python
if exist .venv\Scripts\python.exe (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

if not exist %PY% (
    echo 未找到 Python。请先双击本目录下的 setup.bat 安装依赖，再回来打开。
    pause
    exit /b 1
)

echo 正在打开《生死狙击》AI 控制台 ...
%PY% gui.py
