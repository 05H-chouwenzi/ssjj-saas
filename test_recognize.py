# -*- coding: utf-8 -*-
"""test_recognize.py —— 拿一张图片跑识别，检查模板是否匹配。

用法：
    python test_recognize.py <图片路径>
不带参数时默认用最近收到的那张"大厅+房间列表"截图。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image

import gvision as gv

DEFAULT = r"C:\Users\你雄哥\.workbuddy\clipboard-images\clipboard-2026-09-12T06-47-33-194Z-261aed6a.jpg"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    print("图片:", path)
    im0 = Image.open(path).convert("RGB")
    print("原始尺寸:", im0.size)
    im = gv.to_ref(im0)
    print("to_ref 后:", im.size, " _PAD=", gv._PAD)
    rgb = np.asarray(im, dtype=np.float32)
    prepped = gv.prep_full(gv.gray_of(im))
    loc = gv.locate_count_col(prepped)
    print("自动定位(人数表头):", loc)
    if loc:
        cx, sc = loc[0], loc[2]
    else:
        cx, sc = None, 1.0
    for r in gv.scan_rooms(rgb, prepped, count_x=cx, scale=sc):
        m = "✓" if r["ok"] else " "
        s = r["scores"]
        print(" %s 行%-2d y=%-4d 难度=%-9s 人数=%-4s 锁=%-5s 刚开始=%-5s (难%.2f 困%.2f c1=%.2f c6=%.2f 状%.2f 锁%.0f)"
              % (m, r["row"], r["y"], r["difficulty"], r["count"], r["has_lock"],
                 r["starting"], s["nightmare"], s["hard"], s["count1"], s["count6"],
                 s["status"], s["lock"]))


if __name__ == "__main__":
    main()
