# -*- coding: utf-8 -*-
"""紧急诊断：游戏是否无响应 + bot 进程是否还在跑。"""
import ctypes
from ctypes import wintypes
import os
import subprocess
import sys

u32 = ctypes.windll.user32
u32.IsHungAppWindow.argtypes = [wintypes.HWND]
u32.IsHungAppWindow.restype = wintypes.BOOL
proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
u32.EnumWindows.argtypes = [proto, wintypes.LPARAM]
u32.IsWindowVisible.argtypes = [wintypes.HWND]
u32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

# 1) 游戏窗口无响应检测
state = {}
def cb(hwnd, lp):
    if not u32.IsWindowVisible(hwnd):
        return True
    buf = ctypes.create_unicode_buffer(128)
    u32.GetWindowTextW(hwnd, buf, 128)
    t = buf.value
    if "生死狙击" in t and "助手" not in t:
        wpid = wintypes.DWORD(0)
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        hung = bool(u32.IsHungAppWindow(hwnd))
        state["pid"] = wpid.value
        state["hung"] = hung
        print("[游戏] 窗口=%s PID=%s 无响应=%s" % (t[:40], wpid.value, hung))
    return True
u32.EnumWindows(proto(cb), 0)
if not state:
    print("[游戏] 没找到游戏窗口（可能已被关闭/最小化到任务栏）")

# 2) bot 进程
out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
                     capture_output=True, text=True, encoding="gbk", errors="replace").stdout or ""
bots = []
for line in out.splitlines():
    if "python.exe" in line.lower():
        parts = [p.strip('"') for p in line.split('","')]
        bots.append((parts[1], parts[-2] if len(parts) >= 2 else ""))
print("[python 进程] 共 %d 个: %s" % (len(bots), bots))

# 3) 杀掉所有 auto_lobby（按命令行匹配）
out2 = subprocess.run(["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine"],
                      capture_output=True, text=True, encoding="gbk", errors="replace").stdout or ""
killed = 0
for line in out2.splitlines():
    if "auto_lobby" in line:
        pid = line.strip().split()[-1]
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
        killed += 1
        print("[已停止] auto_lobby PID=%s" % pid)
print("共停止 %d 个 bot 进程" % killed)
