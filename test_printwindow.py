# -*- coding: utf-8 -*-
"""test_printwindow.py —— 测试 PrintWindow 抓取游戏窗口（不受遮挡影响）"""
import ctypes
from ctypes import wintypes

import numpy as np
from PIL import Image

import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import win_dpi  # noqa: F401  (先声明 DPI 感知)
import capture

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetProcessDPIAware()


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def capture_window(hwnd):
    wr = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(wr))
    w = wr.right - wr.left
    h = wr.bottom - wr.top
    if w <= 0 or h <= 0:
        return None, (0, 0, 0, 0)
    hdc = user32.GetWindowDC(hwnd)
    memdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(memdc, bmp)
    # PW_RENDERFULLCONTENT = 2
    ok = user32.PrintWindow(hwnd, memdc, 2)
    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = w
    bmi.biHeight = -h
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(memdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(memdc)
    user32.ReleaseDC(hwnd, hdc)
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    return img, (wr.left, wr.top, w, h), ok


def main():
    w = capture._pick_window("生死狙击")
    if w is None:
        print("没找到游戏窗口")
        return
    hwnd = getattr(w, "_hWnd", None)
    print("窗口:", w.title, "hwnd=", hwnd)
    img, rect, ok = capture_window(hwnd)
    print("PrintWindow ok=", ok, "rect=", rect, "size=", img.size)
    arr = np.asarray(img, dtype=np.float32)
    print("像素均值=%.1f  最大=%.0f  标准差=%.1f (若全黑则均值≈0)" %
          (arr.mean(), arr.max(), arr.std()))
    os.makedirs("debug_frames/diag", exist_ok=True)
    out = "debug_frames/diag/printwindow_test.png"
    img.save(out)
    print("已保存:", out)


if __name__ == "__main__":
    main()
