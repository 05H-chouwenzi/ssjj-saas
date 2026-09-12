# -*- coding: utf-8 -*-
"""帮用户查：游戏进程和当前终端的管理员权限状态。结果写入 elev_report.txt"""
import ctypes
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win_dpi  # noqa: F401

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_frames", "elev_report.txt")


def token_elevated(pid):
    k32 = ctypes.windll.kernel32
    a32 = ctypes.windll.advapi32
    h = k32.OpenProcess(0x1000, False, pid)
    if not h:
        return "查询失败(OpenProcess被拒,通常=对方权限更高)"
    tok = ctypes.c_void_p()
    if not a32.OpenProcessToken(h, 0x0008, ctypes.byref(tok)):
        k32.CloseHandle(h)
        return "查询失败"
    val = ctypes.c_uint32(0)
    ret = ctypes.c_uint32(0)
    ok = a32.GetTokenInformation(tok, 20, ctypes.byref(val), 4, ctypes.byref(ret))
    k32.CloseHandle(tok)
    k32.CloseHandle(h)
    if not ok:
        return "查询失败"
    return "管理员" if val.value else "普通"


def self_elev():
    k32 = ctypes.windll.kernel32
    a32 = ctypes.windll.advapi32
    tok = ctypes.c_void_p()
    a32.OpenProcessToken(k32.GetCurrentProcess(), 0x0008, ctypes.byref(tok))
    val = ctypes.c_uint32(0)
    ret = ctypes.c_uint32(0)
    a32.GetTokenInformation(tok, 20, ctypes.byref(val), 4, ctypes.byref(ret))
    return "管理员" if val.value else "普通"


lines = []
try:
    import pygetwindow as gw
    from capture import _hwnd_of, _pick_window
    from ctypes import wintypes

    ws = [w for w in gw.getAllWindows() if w.visible and w.title]
    cands = [w for w in ws if ("生死狙击" in w.title or "极速" in w.title)]
    lines.append("候选窗口 %d 个：" % len(cands))
    for w in cands:
        lines.append("  - %r" % w.title)

    w = _pick_window("生死狙击")
    if not w:
        lines.append("!! 没锁定到游戏窗口（游戏可能没开）")
    else:
        hwnd = _hwnd_of(w)
        pid = wintypes.DWORD(0)
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        lines.append("游戏窗口: %r  PID=%s" % (w.title, pid.value))
        lines.append("游戏进程身份: %s" % token_elevated(pid.value))
    lines.append("本脚本身份: %s" % self_elev())
except Exception as e:
    lines.append("异常: %r" % (e,))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("\n".join(lines))
