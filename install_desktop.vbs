Option Explicit

Dim fso, wshell, baseDir, desktopDir, lnkPath, sc
Set fso = CreateObject("Scripting.FileSystemObject")
Set wshell = CreateObject("WScript.Shell")

baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
desktopDir = wshell.SpecialFolders("Desktop")

lnkPath = fso.BuildPath(desktopDir, "Sniper AI Helper.lnk")

Set sc = wshell.CreateShortcut(lnkPath)
sc.TargetPath = fso.BuildPath(baseDir, "run_client.vbs")
sc.WorkingDirectory = baseDir
sc.IconLocation = fso.BuildPath(baseDir, "app.ico")
sc.Description = "Sniper AI Helper - lobby reward bot"
sc.Save

MsgBox "Desktop shortcut created at:" & vbCrLf & vbCrLf & lnkPath, vbInformation, "Sniper AI Helper"
