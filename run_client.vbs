' Launcher: open Sniper AI client without terminal window
' Prefer project .venv pythonw, fallback to system pythonw
Option Explicit

Dim fso, wshell, baseDir, venvPyw, py, appPy
Set fso = CreateObject("Scripting.FileSystemObject")
Set wshell = CreateObject("WScript.Shell")

baseDir = fso.GetParentFolderName(WScript.ScriptFullName)

venvPyw = fso.BuildPath(baseDir, ".venv\Scripts\pythonw.exe")
If fso.FileExists(venvPyw) Then
    py = venvPyw
Else
    MsgBox "No project .venv found. Please run setup.bat first.", vbExclamation, "Sniper AI Helper"
    py = "pythonw.exe"
End If

appPy = fso.BuildPath(baseDir, "app.py")
If Not fso.FileExists(appPy) Then
    MsgBox "app.py not found.", vbCritical, "Sniper AI Helper"
    WScript.Quit 1
End If

wshell.Run """" & py & """ """ & appPy & """", 0, False
