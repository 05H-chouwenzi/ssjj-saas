# -*- coding: utf-8 -*-
"""纯 Python 生成 app.ico（64x64，32bit 带 alpha），不依赖任何第三方包。"""
import struct
import math
import os

W = H = 64
cx = cy = (W - 1) / 2.0


def px(x, y):
    # 背景：深蓝灰
    r, g, b = 0x1f, 0x2a, 0x44
    dx = x - cx
    dy = y - cy
    d = math.hypot(dx, dy)
    # 外环（瞄准/领取标记）
    if 21 <= d <= 25:
        r, g, b = 0x39, 0xd9, 0x8a
    # 中心亮点
    if d <= 6:
        r, g, b = 0x7c, 0xf2, 0xb8
    # 十字线
    if abs(dx) <= 1.5 and d <= 28:
        r, g, b = 0x39, 0xd9, 0x8a
    if abs(dy) <= 1.5 and d <= 28:
        r, g, b = 0x39, 0xd9, 0x8a
    return (r, g, b, 255)


pixels = bytearray()
for y in range(H - 1, -1, -1):       # BMP 自下而上
    for x in range(W):
        r, g, b, a = px(x, y)
        pixels += bytes((b, g, r, a))  # BGRA

and_mask = b"\x00" * ((W * H) // 8)   # 512 字节全 0（透明由 alpha 控制）

bih = struct.pack("<IiiHHIIiiII", 40, W, H * 2, 1, 32, 0, 0, 0, 0, 0, 0)
img = bih + bytes(pixels) + and_mask

icon_dir = struct.pack("<HHH", 0, 1, 1)
entry = struct.pack("<BBBBHHII", W, H, 0, 0, 1, 32, len(img), 6 + 16)
out = icon_dir + entry + img

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.ico")
with open(path, "wb") as f:
    f.write(out)
print("wrote", path, len(out), "bytes")
