# -*- coding: utf-8 -*-
"""
diag.py —— 一键诊断：窗口锁定 + 截图 + 识别

用途：不再依赖界面来回点，直接在终端跑一次，把关键信息全部打出来，并存调试图。
用法（游戏先开在大厅界面）：
    python diag.py            # 截当前画面并诊断
    python diag.py 2          # 连拍 2 张（间隔 1 秒），观察窗口/面板是否稳定

它会输出：
  1. 找到的所有候选窗口（标题 / 位置 / 尺寸）
  2. 最终锁定的窗口 rect
  3. 截图实际尺寸
  4. 「人数」表头模板能否定位（score / scale / count_x）
  5. 逐行识别结果（难度 / 人数 / 锁 / 状态 / 是否命中）
  6. 保存原图到 debug_frames/diag/  （可以把它发给我）
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 声明 DPI 感知（必须在任何窗口枚举/截图/鼠标调用之前）。
import win_dpi  # noqa: F401

import numpy as np
from PIL import Image

import config
import gvision as gv


def list_windows(title):
    """列出所有标题匹配的窗口，方便看有没有抓错。"""
    try:
        import pygetwindow as gw
    except Exception as e:
        print("  [警告] 未安装 pygetwindow:", e)
        return []
    try:
        wins = gw.getWindowsWithTitle(title)
    except Exception as e:
        print("  [警告] 枚举窗口失败:", e)
        return []
    rows = []
    for w in wins:
        rows.append({
            "title": w.title,
            "left": int(w.left), "top": int(w.top),
            "w": int(w.width), "h": int(w.height),
            "visible": bool(w.visible),
            "minimized": bool(getattr(w, "isMinimized", False)),
        })
    return rows


def main():
    n = 1
    if len(sys.argv) > 1:
        try:
            n = max(1, int(sys.argv[1]))
        except Exception:
            n = 1

    print("=" * 68)
    print("生死狙击 · 挂机找房 诊断工具")
    print("  窗口标题匹配关键词:", config.GAME_WINDOW_TITLE)
    print("=" * 68)

    # 1) 列出候选窗口
    print("\n[1] 候选窗口（标题含「%s」）：" % config.GAME_WINDOW_TITLE)
    wins = list_windows(config.GAME_WINDOW_TITLE)
    if not wins:
        print("    （没有找到任何匹配窗口！请确认游戏已打开、窗口标题包含关键词）")
    for i, w in enumerate(wins):
        flag = ""
        if not w["visible"]:
            flag += " 不可见"
        if w["minimized"]:
            flag += " 已最小化"
        if w["w"] < 800 or w["h"] < 600:
            flag += " 尺寸偏小"
        print("    #%d '%s'  rect=(%d,%d,%d,%d)%s"
              % (i, w["title"][:40], w["left"], w["top"], w["w"], w["h"], flag))

    # 2) 实际用 capture.grab 截图（内部会走窗口锁定逻辑）
    from capture import grab
    debug_dir = os.path.join(HERE, "debug_frames", "diag")
    os.makedirs(debug_dir, exist_ok=True)

    from datetime import datetime
    for k in range(n):
        if k > 0:
            time.sleep(1.0)
        print("\n" + "-" * 68)
        print("[2] 第 %d 张截图" % (k + 1))
        img, rect = grab(resize=False, activate=True)
        print("    截图尺寸 = %s   锁定 rect = %s" % (img.size, rect))

        ts = datetime.now().strftime("%m%d-%H%M%S")
        save_path = os.path.join(debug_dir, "diag_%s.png" % ts)
        img.save(save_path)
        print("    原图已保存:", save_path)

        # 3) 识别
        im = gv.to_ref(img)
        rgb = np.asarray(im, dtype=np.float32)
        prepped = gv.prep_full(gv.gray_of(im))
        print("    to_ref 后尺寸 = %s  _PAD = %s" % (im.size, gv._PAD))

        loc = gv.locate_count_col(prepped)
        if loc:
            count_x, score, scale = loc
            print("    [定位] 「人数」表头 OK  score=%.3f  scale=%.3f  count_x=%d"
                  % (score, scale, count_x))
        else:
            count_x, scale = None, 1.0
            print("    [定位] 「人数」表头 未找到（模板失配 or 面板没开）")
            # 额外探测：全图最佳匹配分（放宽范围再试一次，看差多少）
            best = None
            for sc in [0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15]:
                try:
                    t = Image.open(os.path.join(gv.TPL_DIR, "hdr_count.png")).convert("L")
                    tw, th = int(t.width * sc), int(t.height * sc)
                    t2 = t.resize((tw, th), Image.LANCZOS)
                    ta = gv.local_norm(np.asarray(t2, dtype=np.float32), 9)
                    h, w = prepped.shape
                    bs = -1.0
                    for y in range(200 + gv._PAD[1], 420 + gv._PAD[1], 4):
                        for x in range(800, 1800, 4):
                            if y + th > h or x + tw > w:
                                continue
                            s = gv._ncc(prepped[y:y + th, x:x + tw], ta)
                            if s > bs:
                                bs = s
                    if best is None or bs > best[0]:
                        best = (bs, sc)
                except Exception as e:
                    print("      模板探测异常:", e)
            if best:
                print("    全图最佳模板分=%.3f (scale=%.2f, 阈值0.50)" % (best[0], best[1]))

        rows = gv.scan_rooms(rgb, prepped, count_x=count_x, scale=scale)
        print("    逐行识别（共 %d 行）：" % len(rows))
        hit = 0
        for r in rows:
            sc = r["scores"]
            mark = "✓命中" if r["ok"] else "     "
            if r["ok"]:
                hit += 1
            print("      %s 行%-2d y=%-4d 难度=%-9s 人数=%-4s 锁=%-5s 刚开始=%-5s "
                  "(难%.2f 困%.2f c1=%.2f c6=%.2f 状%.2f 锁亮度%.0f)"
                  % (mark, r["row"], r["y"], r["difficulty"], r["count"],
                     r["has_lock"], r["starting"], sc["nightmare"], sc["hard"],
                     sc["count1"], sc["count6"], sc["status"], sc["lock"]))
        print("    命中 %d 行" % hit)


if __name__ == "__main__":
    main()
