# -*- coding: utf-8 -*-
"""
make_templates.py —— 从 samples/lobby.jpg（大厅房间列表截图）生成识别模板。

模板坐标基于参考分辨率 1920x1077，与 gvision.py 的坐标系一致。
以后如果游戏 UI 改版，用新截图替换 samples/lobby.jpg 后重跑本脚本即可重建模板。
"""
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "samples", "lobby.jpg")
DST = os.path.join(HERE, "templates")

# 行位置（与 gvision.py 保持一致）
ROW0_Y, ROW_H = 319.0, 20.1
TPL_H = 18


def row_box(x0, x1, row_idx):
    """row_idx 从 1 开始，返回以该行中心为中心的裁剪框。"""
    y = int(round(ROW0_Y + (row_idx - 1) * ROW_H))
    return (x0, y - TPL_H // 2, x1, y + TPL_H // 2)


def main():
    os.makedirs(DST, exist_ok=True)
    im = Image.open(SAMPLE).convert("RGB")
    print("sample size:", im.size)

    tpls = {
        "nightmare_y": row_box(1040, 1080, 1),   # 噩梦（行1 黄底）
        "nightmare_g": row_box(1040, 1080, 3),   # 噩梦（行3 灰底）
        "hard_g":      row_box(1040, 1080, 2),   # 困难（行2 灰底）
        "count1_g":    row_box(1098, 1113, 2),   # 1/6 的分子数字"1"（行2 灰底）
        "count1_y":    row_box(1098, 1113, 4),   # 1/6 的分子数字"1"（行4 黄底）
        "count6_y":    row_box(1098, 1113, 1),   # 6/6 的分子数字"6"（行1 黄底）
        "count6_g":    row_box(1098, 1113, 6),   # 6/6 的分子数字"6"（行6 灰底）
        "status_y":    row_box(1134, 1205, 1),   # 刚开始（行1 黄底）
        "status_g":    row_box(1134, 1205, 2),   # 刚开始（行2 灰底）
    }
    for name, bx in tpls.items():
        t = im.crop(bx)
        t.save(os.path.join(DST, name + ".png"))
        print("  %-12s %s -> %s" % (name, bx, t.size))

    # 「人数」表头（绝对坐标）—— 用于运行时自动定位面板的水平位置
    hdr = im.crop((1078, 286, 1152, 306))
    hdr.save(os.path.join(DST, "hdr_count.png"))
    print("  hdr_count      (1078, 286, 1152, 306) -> %s" % (hdr.size,))

    # 「确定」/「退出」按钮（来自结算页截图）
    p2 = os.path.join(HERE, "samples", "confirm.jpg")
    if os.path.exists(p2):
        im2 = Image.open(p2).convert("RGB")
        im2.crop((902, 424, 1058, 478)).save(os.path.join(DST, "btn_ok.png"))
        print("  btn_ok         from confirm.jpg (902,424,1058,478)")
    p3 = os.path.join(HERE, "samples", "after_ok.jpg")
    if os.path.exists(p3):
        im3 = Image.open(p3).convert("RGB")
        im3.crop((890, 638, 1012, 694)).save(os.path.join(DST, "btn_quit.png"))
        print("  btn_quit       from after_ok.jpg (890,638,1012,694)")
    print("done.")


if __name__ == "__main__":
    main()
