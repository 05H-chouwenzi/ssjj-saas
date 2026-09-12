@echo off
chcp 65001 >nul
echo [1/3] Creating virtual environment...
python -m venv .venv
if errorlevel 1 (
  echo Failed to create venv. Make sure python is on PATH, or run: python -m venv .venv
  pause
  exit /b 1
)
echo [2/3] Installing dependencies...
call .venv\Scripts\activate
python -m pip install -U pip
pip install -r requirements.txt
echo [3/3] Done.
echo Run the bot with:  python main.py
echo Or check env first: python check_env.py
pause
