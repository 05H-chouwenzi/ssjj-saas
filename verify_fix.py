# -*- coding: utf-8 -*-
"""离线验证动态行格+v2分类：对指定截图跑完整识别，打印每行判定。"""
import sys
import numpy as np
from PIL import Image
import gvision as gv

path = sys.argv[1] if len(sys.argv) > 1 else "debug_frames/auto_lobby/0912-165411_38996_01_after_roomlist_click.png"
im = gv.to_ref(Image.open(path).convert("RGB"))
rgb = np.asarray(im, dtype=np.float32)
prepped = gv.prep_full(gv.gray_of(im))
loc = gv.locate_count_col(prepped)
print("定位(人数表头):", loc)
if not loc:
    print("!! 未能定位人数列")
    sys.exit(1)
count_x, sc = loc[0], loc[2]
r0, rh = gv.detect_row_grid(prepped, count_x, sc)
print("行格自动检测: row0_y=%s row_h=%s   (旧常量: %s/%s)"
      % (round(r0, 1) if r0 else None, round(rh, 2) if rh else None, gv.ROW0_Y, gv.ROW_H))
rows = gv.scan_rooms(rgb, prepped, count_x=count_x, scale=sc, row0_y=r0, row_h=rh)
print("-" * 100)
hit = 0
for r in rows:
    flag = "✓" if r["ok"] else " "
    s = r["scores"]
    if r["ok"]:
        hit += 1
    db = s.get("diff_best", "-")
    nb = s.get("count_best", "-")
    print(" [%s] 行%-2d y=%.0f 难度=%-9s 人数=%-3s 锁=%-5s 刚开始=%-5s (best %s/%s  nm=%.2f c=%.2f st=%.2f lock=%.2f)"
          % (flag, r["row"], r["y"], r["difficulty"], r["count"], r["has_lock"], r["starting"],
             db, nb, s["nightmare"], max(s["count1"], s["count6"]), s["status"], s["lock"]))
print("-" * 100)
print("符合条件行数:", hit)
