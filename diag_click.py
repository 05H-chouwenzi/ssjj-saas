# -*- coding: utf-8 -*-
"""一次性诊断：为什么模拟点击对游戏无效（「点击游戏画面继续操作」框不消失）
步骤：
  1) 找到游戏窗口 → 查游戏进程与 bot 自身的管理员权限（UIPI 会拦截低权限进程向高权限窗口注入输入）
  2) 激活游戏 → 截"点击前"图 → pyautogui 在提示框中心真实点击一次 → 1.5 秒后截"点击后"图
  3) 若提示框没消失，再用 PostMessage 直接给窗口发 WM_LBUTTONDOWN/UP 试一次
结论自动打印。图片存 debug_frames/click_test/
"""
import os
import sys
import time
import ctypes
from ctypes import wintypes

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win_dpi  # noqa: F401  必须最先导入（DPI 感知）

from capture import _pick_window, _hwnd_of, find_window_rect, activate_window, grab

GAME_TITLE = "生死狙击"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_frames", "click_test")
os.makedirs(OUT_DIR, exist_ok=True)

# 提示框区域（物理像素，来自 0912-1520 现场截图 2560x1368）
OVERLAY_BOX = (1130, 410, 1440, 600)


def is_elevated(pid):
    """查询指定进程是否以管理员权限运行"""
    k32 = ctypes.windll.kernel32
    a32 = ctypes.windll.advapi32
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    TOKEN_QUERY = 0x0008
    TokenElevation = 20
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None  # 打不开（多半意味着对方权限更高）
    tok = wintypes.HANDLE()
    if not a32.OpenProcessToken(h, TOKEN_QUERY, ctypes.byref(tok)):
        k32.CloseHandle(h)
        return None
    val = wintypes.DWORD()
    ret_len = wintypes.DWORD()
    ok = a32.GetTokenInformation(tok, TokenElevation, ctypes.byref(val), 4, ctypes.byref(ret_len))
    k32.CloseHandle(tok)
    k32.CloseHandle(h)
    return bool(val.value) if ok else None


def self_elevated():
    k32 = ctypes.windll.kernel32
    a32 = ctypes.windll.advapi32
    tok = wintypes.HANDLE()
    a32.OpenProcessToken(k32.GetCurrentProcess(), 0x0008, ctypes.byref(tok))
    val = wintypes.DWORD()
    ret_len = wintypes.DWORD()
    a32.GetTokenInformation(tok, 20, ctypes.byref(val), 4, ctypes.byref(ret_len))
    return bool(val.value)


def diff_stats(img_a, img_b, box=None):
    a = np.asarray(img_a.convert("L"), dtype=np.int16)
    b = np.asarray(img_b.convert("L"), dtype=np.int16)
    if box:
        x0, y0, x1, y1 = box
        a = a[y0:y1, x0:x1]
        b = b[y0:y1, x0:x1]
    return float(np.abs(a - b).mean())


def main():
    rect = find_window_rect(GAME_TITLE)
    if not rect:
        print("❌ 没找到游戏窗口，请先把游戏开起来再跑本诊断")
        return
    print(f"[窗口] rect={rect}")

    w = _pick_window(GAME_TITLE)
    hwnd = _hwnd_of(w)
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    game_elev = is_elevated(pid.value)
    mine = self_elevated()
    print(f"[权限] 游戏进程 PID={pid.value} 管理员权限={game_elev}（None=查询失败/对方权限更高）")
    print(f"[权限] 本进程(bot)   管理员权限={mine}")
    if game_elev and not mine:
        print(">>> 结论A：游戏以管理员运行、bot 是普通权限 → Windows UIPI 直接丢弃注入的鼠标事件！")
        print(">>> 解决：用管理员身份运行终端/软件（右键 → 以管理员身份运行）")

    # ---- 实验一：pyautogui 真实点击 ----
    print("\n---- 实验一：pyautogui 点击提示框中心 ----")
    activate_window(GAME_TITLE)
    time.sleep(0.8)
    before = grab(resize=False, activate=False)
    before.save(os.path.join(OUT_DIR, "before_pyautogui.png"))

    ox = rect[0] + (OVERLAY_BOX[0] + OVERLAY_BOX[2]) // 2
    oy = rect[1] + (OVERLAY_BOX[1] + OVERLAY_BOX[3]) // 2
    print(f"[点击] pyautogui -> screen=({ox},{oy})")
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        pyautogui.moveTo(ox, oy, duration=0.1)
        pyautogui.click()
    except Exception as e:
        print(f"❌ pyautogui 异常: {e}")
    time.sleep(1.5)
    after1 = grab(resize=False, activate=False)
    after1.save(os.path.join(OUT_DIR, "after_pyautogui.png"))
    d_box = diff_stats(before, after1, OVERLAY_BOX)
    d_all = diff_stats(before, after1)
    print(f"[对比] 提示框区域平均差={d_box:.1f}（>15 视为消失）  全图平均差={d_all:.1f}")
    if d_box > 15:
        print(">>> 提示框已消失：pyautogui 点击有效！之前的失败可能是焦点/遮挡问题")
        return

    # ---- 实验二：PostMessage 直接投递 ----
    print("\n---- 实验二：PostMessage WM_LBUTTONDOWN/UP ----")
    u32 = ctypes.windll.user32
    pt = wintypes.POINT(ox, oy)
    u32.ScreenToClient(hwnd, ctypes.byref(pt))
    lparam = (pt.y << 16) | (pt.x & 0xFFFF)
    before2 = grab(resize=False, activate=False)
    before2.save(os.path.join(OUT_DIR, "before_postmsg.png"))
    r1 = u32.PostMessageW(hwnd, 0x0201, 0x00000001, lparam)  # WM_LBUTTONDOWN
    time.sleep(0.05)
    r2 = u32.PostMessageW(hwnd, 0x0202, 0, lparam)           # WM_LBUTTONUP
    print(f"[发送] PostMessage 返回 down={r1} up={r2}（0=被系统丢弃，UIPI/权限问题）")
    time.sleep(1.5)
    after2 = grab(resize=False, activate=False)
    after2.save(os.path.join(OUT_DIR, "after_postmsg.png"))
    d2_box = diff_stats(before2, after2, OVERLAY_BOX)
    print(f"[对比] 提示框区域平均差={d2_box:.1f}（>15 视为消失）")
    if d2_box > 15:
        print(">>> PostMessage 有效！可以把 bot 的点击方式改为 PostMessage")
        return
    print("\n>>> 两种点击都无效。结合上面的权限信息：")
    if game_elev and not mine:
        print(">>> 原因确认 = UIPI 权限拦截 → 以管理员身份重新运行 bot 即可解决")
    elif game_elev is None:
        print(">>> 游戏进程权限查询被拒（OpenProcess 失败），这本身通常就说明游戏权限更高 → 用管理员运行 bot")
    else:
        print(">>> 游戏并非管理员权限但两种注入都被无视 → 可能是启动器反注入，需进一步排查（把 4 张测试图发回来看）")


if __name__ == "__main__":
    main()
