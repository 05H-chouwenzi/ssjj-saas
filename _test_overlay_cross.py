# -*- coding: utf-8 -*-
"""交叉验证 overlay 模板在另一张现场截图上的得分。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import win_dpi  # noqa: F401

from PIL import Image
import gvision as gv

ref = gv.to_ref(Image.open(os.path.join(
    HERE, "debug_frames", "auto_lobby", "0912-151857_39612_00_initial.png")))
p = gv.prep_full(gv.gray_of(ref))
print("cross-frame score=%.3f" % gv.match_score(p, "overlay_focus", 963, 411, search=45))
