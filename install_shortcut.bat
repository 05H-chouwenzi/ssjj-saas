@echo off
chcp 65001 >nul
cd /d "%~dp0"
wscript //NoLogo "%~dp0install_shortcut.vbs"
