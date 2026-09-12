Option Explicit

Dim fso, wshell, baseDir, appData, startMenuDir, lnkPath, sc
Set fso = CreateObject("Scripting.FileSystemObject")
Set wshell = CreateObject("WScript.Shell")

baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
appData = wshell.ExpandEnvironmentStrings("%APPDATA%")
startMenuDir = appData & "\Microsoft\Windows\Start Menu\Programs"

lnkPath = fso.BuildPath(startMenuDir, "Sniper AI Helper.lnk")

Set sc = wshell.CreateShortcut(lnkPath)
sc.TargetPath = fso.BuildPath(baseDir, "run_client.vbs")
sc.WorkingDirectory = baseDir
sc.IconLocation = fso.BuildPath(baseDir, "app.ico")
sc.Description = "Sniper AI Helper - lobby reward bot"
sc.Save

MsgBox "Start menu shortcut created at:" & vbCrLf & vbCrLf & lnkPath, vbInformation, "Sniper AI Helper"
