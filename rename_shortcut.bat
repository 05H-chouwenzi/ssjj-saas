@echo off
cd /d "%~dp0"
set "LOG=%~dp0rename_log.txt"
echo [%date% %time%] Start > "%LOG%"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$src=Join-Path $env:APPDATA ('Microsoft\Windows\Start Menu\Programs\Sniper AI Helper.lnk');" ^
  "$b64='55Sf5q2754uZ5Ye7IEFJIOWKqeaJiw==';" ^
  "$name=[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($b64));" ^
  "$dst=Join-Path $env:APPDATA ('Microsoft\Windows\Start Menu\Programs\'+$name+'.lnk');" ^
  "if (Test-Path -LiteralPath $src){ Move-Item -LiteralPath $src -Destination $dst -Force; Write-Host ('RENAMED: '+$dst) } else { Write-Host ('NOT FOUND (already renamed?): '+$src) }"

if errorlevel 1 (
  echo FAILED >> "%LOG%"
  echo [FAILED] See rename_log.txt
) else (
  echo OK >> "%LOG%"
  echo [OK] Renamed to Chinese.
)
echo.
echo Done. Open Start Menu and search the Chinese name.
echo.
pause
