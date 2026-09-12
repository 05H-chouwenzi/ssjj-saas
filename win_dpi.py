# -*- coding: utf-8 -*-
"""
win_dpi.py —— 在 bot 进程启动早期声明「DPI 感知」。

问题背景：用户的屏幕是 2560x1440 物理分辨率 + 150% 缩放（逻辑 1707x960）。
 - 若进程【非】DPI 感知：pygetwindow 返回逻辑坐标(1707x912)，mss 也按逻辑抓 → 与
   按物理分辨率(2560x1440)标定的模板尺寸不一致。
 - 若进程【是】DPI 感知：pygetwindow/mss/pyautogui 统一用物理像素 → 与模板标定一致。

因此 bot 相关进程都要在最早期 import 本模块，让坐标/截图/鼠标统一为物理像素。
注意：只给 bot 进程用（auto_lobby / calibrate / diag），不要放进 config.py，
      否则会连 UI(app.py) 一起变成 DPI 感知，导致软件界面在 150% 缩放下显示过小。
"""
import ctypes


def _ensure_dpi_aware():
    # Windows 8.1+：按显示器 DPI 感知（值 2 = PROCESS_PER_MONITOR_DPI_AWARE）
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return True
    except Exception:
        pass
    # 老系统兜底
    try:
        ctypes.windll.user32.SetProcessDPIAware()
        return True
    except Exception:
        return False


_ensure_dpi_aware()

if __name__ == "__main__":
    print("DPI 感知已设置:", _ensure_dpi_aware())
