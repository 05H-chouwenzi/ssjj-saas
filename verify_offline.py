# -*- coding: utf-8 -*-
"""
verify_offline.py —— 离线验证房间识别（不点击鼠标）。

用法：
    python verify_offline.py                 # 用内置示例 samples/lobby.jpg
    python verify_offline.py 你的截图.png     # 用指定截图

输出每一行的识别结果与最终命中房间，用于在实机操作前确认识别准确率。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from PIL import Image

import gvision as gv

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = os.path.join(HERE, "samples", "lobby.jpg")
    if not os.path.exists(path):
        print("找不到截图：", path)
        return

    im = gv.to_ref(Image.open(path).convert("RGB"))
    rgb = np.asarray(im, dtype=np.float32)
    prepped = gv.prep_full(gv.gray_of(im))

    loc = gv.locate_count_col(prepped)
    count_x = loc[0] if loc else None
    panel_scale = loc[2] if loc else 1.0
    print("输入:", path, " 归一化尺寸:", im.size)
    if loc:
        print("自动定位 → 人数列 x=%.0f (匹配度 %.3f, 尺度 %.2f)" % loc)
    else:
        print("自动定位失败，使用基准位置")
    print("判定规则: 无锁 且 难度=噩梦 且 人数(2~5) 且 状态=刚开始\n")
    print("行    y |锁(纹理) 噩梦   困难  人数1  人数6  刚开始| 有锁 难度      人数 符合")
    print("-" * 92)
    for r in gv.scan_rooms(rgb, prepped, count_x=count_x, scale=panel_scale):
        s = r["scores"]
        print("%2d %4d | %7.1f %.3f %.3f %.3f %.3f %.3f | %-4s %-9s %-4s %s" % (
            r["row"], r["y"], s["lock"], s["nightmare"], s["hard"],
            s["count1"], s["count6"], s["status"],
            "有锁" if r["has_lock"] else "  -",
            r["difficulty"], r["count"], "★" if r["ok"] else ""))

    pick = gv.pick_room(rgb, prepped, count_x=count_x, scale=panel_scale)
    print()
    if pick:
        print("=> 选中第 %d 行 (y=%d)，点击坐标: (%d, %d)"
              % (pick["row"], pick["y"], gv.click_x(count_x, panel_scale), pick["y"]))
    else:
        print("=> 本屏没有符合条件的房间（继续等待）")


if __name__ == "__main__":
    main()
