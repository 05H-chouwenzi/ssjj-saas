# -*- coding: utf-8 -*-
"""查看房间面板下部是否有房间行数据。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from PIL import Image

SRC = os.path.join(HERE, "debug_frames", "auto_lobby", "0912-152018_39612_02_roomlist_not_found.png")
img = Image.open(SRC)
box = (1400, 760, 2200, 1100)
crop = img.crop(box)
big = crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
OUT = os.path.join(HERE, "debug_frames", "zoom_roomrows.png")
big.save(OUT)
print("saved:", OUT, "box:", box, "size:", big.size)
