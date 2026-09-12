# -*- coding: utf-8 -*-
"""从现场截图裁「点击游戏画面继续操作」失焦提示框模板，并验证正/负样本区分度。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import win_dpi  # noqa: F401

import numpy as np
from PIL import Image
import gvision as gv

FRAME = os.path.join(HERE, "debug_frames", "auto_lobby", "0912-152018_39612_02_roomlist_not_found.png")
NEG = os.path.join(HERE, "samples", "lobby.jpg")   # 无提示框的大厅参考图
OUT = os.path.join(gv.TPL_DIR, "overlay_focus.png")

img = Image.open(FRAME)
ref = gv.to_ref(img)
s = min(gv.REF_W / img.width, gv.REF_H / img.height)
px, py = gv._PAD
print("frame:", img.size, "scale=%.4f pad=%s" % (s, (px, py)))

# 提示框在物理截图里的估算范围（2560x1368 帧）
ph_x0, ph_y0, ph_x1, ph_y1 = 1150, 430, 1420, 600
x0, y0 = int(ph_x0 * s + px), int(ph_y0 * s + py)
x1, y1 = int(ph_x1 * s + px), int(ph_y1 * s + py)
print("ref box:", (x0, y0, x1, y1))

crop = ref.crop((x0, y0, x1, y1))
crop.save(OUT)
print("template saved:", OUT, "size=", crop.size)

prep = gv.prep_full(gv.gray_of(ref))
cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
pos = gv.match_score(prep, "overlay_focus", cx, cy, search=12)
print("正样本(同一张图) score=%.3f" % pos)

if os.path.exists(NEG):
    ref2 = gv.to_ref(Image.open(NEG))
    prep2 = gv.prep_full(gv.gray_of(ref2))
    neg = gv.match_score(prep2, "overlay_focus", cx, cy, search=45)
    print("负样本(无提示框大厅) score=%.3f" % neg)
