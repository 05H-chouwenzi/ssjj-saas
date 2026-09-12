# -*- coding: utf-8 -*-
"""放大现场截图底部的标签栏区域，便于精确读取「房间列表」按钮位置。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from PIL import Image

SRC = os.path.join(HERE, "debug_frames", "auto_lobby", "0912-152018_39612_02_roomlist_not_found.png")
OUT = os.path.join(HERE, "debug_frames", "zoom_tabbar.png")

img = Image.open(SRC)
print("source size:", img.size)

# 标签栏区域（物理像素）：显示坐标约 (420..790, 275..300) × 2.37037
box = (960, 640, 1900, 745)
crop = img.crop(box)
big = crop.resize((crop.width * 4, crop.height * 4), Image.LANCZOS)
big.save(OUT)
print("saved:", OUT, "crop box:", box, "zoom size:", big.size)

# 再来一张更靠右、含提议按钮行的区域，防止看漏
box2 = (1500, 620, 2140, 800)
crop2 = img.crop(box2)
big2 = crop2.resize((crop2.width * 3, crop2.height * 3), Image.LANCZOS)
OUT2 = os.path.join(HERE, "debug_frames", "zoom_tabbar_right.png")
big2.save(OUT2)
print("saved:", OUT2, "crop box2:", box2)
