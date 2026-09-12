@echo off
rem One-click admin launcher: double-click me, click "Yes" on the UAC popup.
rem Self-relaunch pattern keeps this file pure ASCII (no encoding issues).
if "%~1"=="elevated" goto :run
powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList 'elevated' -Verb RunAs"
exit /b

:run
cd /d "%~dp0"
title SniperBot (Admin)
call ".venv\Scripts\activate.bat"
python app.py
pause
