@echo off
chcp 65001 >nul
cd /d %~dp0
echo ================================
echo  打包《生死狙击》AI 控制台为 exe
echo ================================
echo.
echo [1/3] 确保 PyInstaller 已安装 ...
python -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo 安装 PyInstaller 失败，请确认 python 在 PATH 中。
    pause
    exit /b 1
)

echo [2/3] 开始打包 (gui.py -> SniperAIConsole.exe) ...
pyinstaller --onefile --noconsole --name SniperAIConsole --hidden-import requests gui.py
if errorlevel 1 (
    echo 打包失败。
    pause
    exit /b 1
)

echo [3/3] 复制 exe 到本目录（与 main.py / .venv 同级，便于双击运行）...
copy /Y dist\SniperAIConsole.exe .\SniperAIConsole.exe >nul
echo.
echo 完成！双击本目录下的 SniperAIConsole.exe 即可运行控制台。
echo 注意：bot 脚本仍依赖本机 python 环境，请先运行 setup.bat 安装依赖。
pause
