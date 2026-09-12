# -*- coding: utf-8 -*-
"""从实机现场截图重裁全套识别模板（v2）。

基准图：debug_frames/auto_lobby/0912-165411_38996_01_after_roomlist_click.png
（2560x1368 物理截图，to_ref 后 1920x1077 参考系，pad=(0,25)）

实测列位（ref x）：ID 1123 | 锁 ~1142 | 难度 1240 | 人数 1290 | 状态 ~1353
实测行位（ref y，不含 pad）：行1=319，行高 20.1（与旧常量一致）
"""
import os
import numpy as np
from PIL import Image
import gvision as gv

SRC = "debug_frames/auto_lobby/0912-165411_38996_01_after_roomlist_click.png"
im_ref = gv.to_ref(Image.open(SRC).convert("RGB"))   # 1920x1077

# (名字, ref box (x0,y0,x1,y1))
CUTS = [
    # 难度列（x 1220-1260，各行的「难度」两字）
    ("d_nightmare", (1220, 377, 1260, 393)),   # 行3 噩梦（与 n_4 同行）
    ("d_speed",     (1220, 356, 1260, 372)),   # 行2 极速
    ("d_expert",    (1220, 497, 1260, 513)),   # 行9 专家
    ("d_common",    (1220, 336, 1260, 352)),   # 行1 普通
    # 人数列（x 1266-1314，「n/6」整串）
    ("n_1", (1266, 437, 1314, 453)),           # 行6 1/6
    ("n_2", (1266, 477, 1314, 493)),           # 行8 2/6
    ("n_4", (1266, 377, 1314, 393)),           # 行3 4/6
    ("n_6", (1266, 457, 1314, 473)),           # 行7 6/6
    # 状态列「刚开始」（两种底色字形反差相反：蓝底橙字 / 黄底白字，需各一模板）
    ("status2",   (1331, 336, 1377, 352)),       # 行1 蓝底橙字
    ("status2_g", (1331, 356, 1377, 372)),       # 行2 黄底白字
    # 锁图标（两种底色各一）
    ("lock_icon",  (1130, 337, 1152, 353)),      # 行1 锁
    ("lock_icon2", (1130, 497, 1152, 513)),      # 行9 锁
    # 人数表头（更新 locate 用）
    ("hdr_count2", (1268, 311, 1310, 327)),
]

# 拼对照图目检
tiles = []
for name, box in CUTS:
    x0, y0, x1, y1 = box
    crop = im_ref.crop((x0, y0, x1, y1))
    crop.save(os.path.join("templates", name + ".png"))   # 先存原始尺寸模板
    crop = crop.resize((crop.width * 6, crop.height * 6), Image.NEAREST)  # 再放大仅用于目检
    tiles.append((name, crop))
    print("裁剪 %s box=%s size=%s" % (name, box, (x1 - x0, y1 - y0)))

W = max(c.width for _, c in tiles) + 220
H = sum(c.height for _, c in tiles) + 8 * len(tiles)
sheet = Image.new("RGB", (W, H), (30, 30, 30))
from PIL import ImageDraw
dr = ImageDraw.Draw(sheet)
y = 0
for name, c in tiles:
    sheet.paste(c, (210, y))
    dr.text((6, y + c.height // 2 - 8), name, fill=(255, 255, 120))
    y += c.height + 8
sheet.save("debug_frames/_tpl_sheet.png")
print("对照图已存 debug_frames/_tpl_sheet.png")
