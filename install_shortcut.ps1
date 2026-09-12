# 安装/刷新开始菜单快捷方式（中文名走 base64，避免 bat 编码问题）
$ErrorActionPreference = 'Stop'

$dir = (Get-Location).Path
$base = Join-Path $env:USERPROFILE 'AppData\Roaming\Microsoft\Windows\Start Menu\Programs'
$b64 = '55Sf5q2754uZ5Ye7IEFJIOWKqeaJiw=='
$name = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($b64))

$ws = New-Object -ComObject WScript.Shell
$lnk = Join-Path $base ($name + '.lnk')
$s = $ws.CreateShortcut($lnk)
$s.TargetPath = Join-Path $dir 'run_client.vbs'
$s.WorkingDirectory = $dir
$s.IconLocation = Join-Path $dir 'app.ico'
$s.Description = '生死狙击 AI 助手 - 仿 WorkBuddy 客户端'
$s.Save()

$log = Join-Path $dir 'install_log.txt'
$msg = "[{0}] UPDATED Target -> run_client.vbs : {1}" -f (Get-Date -Format 'yyyy/MM/dd HH:mm:ss'), $lnk
Add-Content -Path $log -Value $msg -Encoding utf8
Write-Host '[OK] Updated shortcut:' $lnk -ForegroundColor Green
