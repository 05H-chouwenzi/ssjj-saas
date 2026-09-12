# -*- coding: utf-8 -*-
"""
gvision.py —— 《生死狙击》界面的局部识别（模板匹配 + 自动定位）

设计要点：
  * 不使用视觉大模型、不使用 OpenCV；只用 Pillow + numpy，CPU 占用极低。
  * 所有坐标基于"参考分辨率" REF_W x REF_H（= 用户截图尺寸 1920x1077）。
    运行时把实际截图缩放到该尺寸后再识别，因此与实际屏幕分辨率无关。
  * 关键1：先做【局部照明归一化】(减去局部均值)，消除行背景色(土黄/亮黄/灰蓝)差异，
    只留文字/图标的形状信息，再做归一化互相关(NCC)匹配 —— 跨背景也能匹配。
  * 关键2：【自动定位】房间面板的水平位置会变（对局失败回大厅等少见情况下会偏移），
    所以运行时先用「人数」表头模板搜索出人数列的实际 x，其余各列按相对偏移推算。
"""
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TPL_DIR = os.path.join(HERE, "templates")

# ---------------- 参考坐标系 ----------------
REF_W, REF_H = 1920, 1077

# 当前截图经 to_ref 处理时，为保持比例而填充的黑边偏移 (pad_x, pad_y)。
# 行/列坐标需补偿此偏移（仅纵向会影响行 y；横向 pad_x 一般=0）。
_PAD = (0, 0)

# 房间列表面板（基于参考坐标）
PANEL_X0, PANEL_X1 = 898, 1195
ROW0_Y = 319          # 第 1 行数据中心的 y（自动检测得出）
ROW_H = 20.1          # 行高（自动检测得出；实测另一布局 ~23，故有 detect_row_grid 动态检测）
MAX_ROWS = 10         # 面板最多可见行数

# 基准列位置（取自 samples/lobby.jpg）
BASE_COUNT_X = 1111   # 「人数」列中心 x（基准）

# 各列相对「人数」列的 x 偏移（2026-09-12 晚按实机截图 0912-165411 重标）
COL_OFFSET = {
    "id": 1123 - 1290,        # -167
    "lock": 1141 - 1290,      # -149（锁图标中心）
    "map": 1230 - 1290,
    "difficulty": 1240 - 1290,  # -50
    "count": 0,
    "status": 1353 - 1290,    # +63
}

# 锁检测区域（旧方法：ID 数字右侧亮度的标准差；v2 改用 lock_icon 模板匹配）
LOCK_OFF_X0 = 953 - BASE_COUNT_X
LOCK_OFF_X1 = 975 - BASE_COUNT_X
LOCK_HALF_H = 9
LOCK_STD_THR = 28.0   # 亮度标准差阈值：超过视为有锁（锁图标纹理复杂）

THR_TEXT = 0.40       # 文字类模板匹配阈值
THR_V2 = 0.45         # v2 最近邻分类的最低可信分

# v2 模板集（2026-09-12 从实机截图重裁；判定=最近邻分类，抗字体渲染变化）
DIFF_TPLS = ["d_nightmare", "d_speed", "d_expert", "d_common"]
CNT_TPLS = ["n_1", "n_2", "n_4", "n_6"]
LOCK_CX_OFF = -149    # 锁图标中心相对人数列的偏移

# 「人数」表头模板在基准图中的位置（make_templates.py 裁的是 1078..1152）
HDR_X0 = 1078

_tpl_cache = {}


# ---------------- 基础图像工具 ----------------
def box_blur(a, k):
    """均值滤波（积分图实现，向量化、快）。"""
    h, w = a.shape
    ii = np.cumsum(np.cumsum(a, axis=0), axis=1)
    ii = np.pad(ii, ((1, 0), (1, 0)), mode="constant")
    r = k // 2
    ys = np.arange(h)
    xs = np.arange(w)
    y0 = np.clip(ys - r, 0, h)
    y1 = np.clip(ys + r + 1, 0, h)
    x0 = np.clip(xs - r, 0, w)
    x1 = np.clip(xs + r + 1, 0, w)
    Y0, X0 = np.meshgrid(y0, x0, indexing="ij")
    Y1, X1 = np.meshgrid(y1, x1, indexing="ij")
    s = ii[Y1, X1] - ii[Y0, X1] - ii[Y1, X0] + ii[Y0, X0]
    cnt = ((Y1 - Y0) * (X1 - X0)).astype(np.float32)
    return s / cnt


def local_norm(a, k=11):
    """局部照明归一化：减去局部均值并除以标准差，消除背景亮度/色差影响。"""
    m = box_blur(a, k)
    d = a - m
    s = float(d.std())
    if s < 1e-6:
        return d
    return d / s


def to_ref(img):
    """把截图保持比例缩放到参考分辨率（居中填充黑边，避免拉伸变形导致模板失配）。"""
    global _PAD
    if img.size == (REF_W, REF_H):
        _PAD = (0, 0)
        return img
    iw, ih = img.size
    scale = min(REF_W / iw, REF_H / ih)
    nw, nh = int(round(iw * scale)), int(round(ih * scale))
    im = img.resize((nw, nh), Image.LANCZOS)
    px = (REF_W - nw) // 2
    py = (REF_H - nh) // 2
    _PAD = (px, py)
    canvas = Image.new("RGB", (REF_W, REF_H), (0, 0, 0))
    canvas.paste(im, (px, py))
    return canvas


def gray_of(img):
    if isinstance(img, np.ndarray):
        return img.astype(np.float32)
    return np.asarray(img.convert("L"), dtype=np.float32)


def prep_full(gray):
    return local_norm(gray)


# ---------------- 模板 ----------------
def load_tpl(name):
    if name not in _tpl_cache:
        path = os.path.join(TPL_DIR, name + ".png")
        im = Image.open(path).convert("L")
        arr = np.asarray(im, dtype=np.float32)
        _tpl_cache[name] = local_norm(arr, k=9)
    return _tpl_cache[name]


def _ncc(a, b):
    a = a - a.mean()
    b = b - b.mean()
    da = float(np.sqrt(np.sum(a * a)))
    db = float(np.sqrt(np.sum(b * b)))
    if da < 1e-6 or db < 1e-6:
        return -1.0
    return float(np.sum(a * b) / (da * db))


def match_score(prepped, tpl_name, cx, cy, search=22):
    """在 (cx,cy) 附近 ±search 内搜索模板，返回最高 NCC。"""
    tpl = load_tpl(tpl_name)
    th, tw = tpl.shape
    h, w = prepped.shape
    best = -1.0
    for dy in range(-search, search + 1):
        for dx in range(-search, search + 1):
            x0 = int(round(cx + dx - tw / 2.0))
            y0 = int(round(cy + dy - th / 2.0))
            if x0 < 0 or y0 < 0 or x0 + tw > w or y0 + th > h:
                continue
            s = _ncc(prepped[y0:y0 + th, x0:x0 + tw], tpl)
            if s > best:
                best = s
    return best


def _max_of(names, prepped, cx, cy, search=22):
    return max(match_score(prepped, n, cx, cy, search=search) for n in names)


# ---------------- 自动定位 ----------------
def locate_count_col(prepped, x_range=(880, 1730), y_range=None, scales=None):
    """多尺度搜索「人数」表头，返回 (count_col_x, score, scale)；失败返回 None。

    房间面板位置会变，运行时先调用本函数校准，再据此推算各列 x。
    优先使用 v2 表头模板 hdr_count2（模板中心即人数列中心，换算与基准解耦）；
    无 v2 模板时回退旧 hdr_count + HDR_X0 换算。
    """
    if y_range is None:
        y_range = (272 + _PAD[1], 336 + _PAD[1])
    path2 = os.path.join(TPL_DIR, "hdr_count2.png")
    use_v2 = os.path.exists(path2)
    path = path2 if use_v2 else os.path.join(TPL_DIR, "hdr_count.png")
    if not os.path.exists(path):
        return None
    tpl = Image.open(path).convert("L")
    scales = scales or [0.90, 0.93, 0.96, 0.98, 1.00, 1.02, 1.04, 1.07, 1.10]
    h, w = prepped.shape
    best = None
    for sc in scales:
        tw, th = int(round(tpl.width * sc)), int(round(tpl.height * sc))
        if tw < 8 or th < 6:
            continue
        t = tpl.resize((tw, th), Image.LANCZOS)
        ta = local_norm(np.asarray(t, dtype=np.float32), 9)
        for y in range(y_range[0], y_range[1], 2):
            for x in range(x_range[0], x_range[1], 2):
                if y + th > h or x + tw > w:
                    continue
                s = _ncc(prepped[y:y + th, x:x + tw], ta)
                if best is None or s > best[0]:
                    best = (s, x, y, sc)
    if best is None or best[0] < 0.5:
        return None
    score, x, y, sc = best
    if use_v2:
        tw = int(round(tpl.width * sc))
        count_x = x + tw / 2.0 - 1.0     # 模板中心即人数列中心（裁剪时对准，-1 修正）
    else:
        count_x = x + (BASE_COUNT_X - HDR_X0) * sc
    return (count_x, round(float(score), 3), sc)


# ---------------- 行判定 ----------------
def detect_row_grid(prepped, count_x, scale=1.0, rows=10,
                    h_range=(19.0, 26.0), r0_span=8):
    """自动检测行格 (row0_y, row_h)：网格搜索使各行「刚开始」状态模板分数之和最大。

    背景：面板行高随游戏 UI 布局变化（实测出现过 20.1 与 ~23 两种），
    固定行高会导致越往后行越错位、人数/难度全部误判。
    每行状态列必有「刚开始」字样（跨背景 NCC 已验证），对齐时分数高、
    错位时骤降 —— 以 10 行总分为目标函数，粗(步长0.5/2)+细(0.125/0.5)两轮搜索。
    坐标体系与 ROW0_Y 相同（不含 _PAD，judge_row 内部会加）。
    失败返回 (None, None)，调用方回退 ROW0_Y/ROW_H。
    """
    st_x = count_x + COL_OFFSET["status"] * scale
    st_tpls = [t for t in ("status2", "status2_g", "status_y")
               if os.path.exists(os.path.join(TPL_DIR, t + ".png"))]
    if not st_tpls:
        return None, None

    def _total(r0, rh, n):
        s = 0.0
        for i in range(n):
            y = r0 + i * rh + _PAD[1]
            s += _max_of(st_tpls, prepped, st_x, y, search=2)
        return s / n

    best = None
    # 粗搜
    for rh in np.arange(h_range[0], h_range[1] + 0.01, 0.5):
        for r0 in np.arange(ROW0_Y - r0_span, ROW0_Y + r0_span + 0.01, 2.0):
            t = _total(r0, rh, rows)
            if best is None or t > best[0]:
                best = (t, r0, rh)
    # 细搜
    _, r0b, rhb = best
    for rh in np.arange(rhb - 0.5, rhb + 0.51, 0.125):
        for r0 in np.arange(r0b - 2.0, r0b + 2.01, 0.5):
            t = _total(r0, rh, rows)
            if t > best[0]:
                best = (t, r0, rh)
    if best is None or best[0] < 0.45:
        return None, None
    return float(best[1]), float(best[2])


def lock_std(rgb, row_y, count_x=None, scale=1.0):
    """ID 数字右侧区域的亮度标准差。有锁（锁图标纹理复杂）时显著偏高。"""
    cx = count_x if count_x is not None else BASE_COUNT_X
    sc = scale if scale else 1.0
    x0 = int(round(cx + LOCK_OFF_X0 * sc))
    x1 = int(round(cx + LOCK_OFF_X1 * sc))
    y0 = int(round(row_y - LOCK_HALF_H))
    y1 = int(round(row_y + LOCK_HALF_H))
    reg = rgb[y0:y1, x0:x1].astype(np.float32)
    r, g, b = reg[:, :, 0], reg[:, :, 1], reg[:, :, 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return float(lum.std())


def judge_row(rgb, prepped, row_idx, count_x=None, scale=1.0, row0_y=None, row_h=None):
    """判定第 row_idx 行（从 1 开始）。

    count_x：「人数」列实际中心 x（None 用基准）
    scale ：面板相对基准的横向缩放（各列偏移随之缩放）
    row0_y/row_h：动态检测的行格（None 用常量 ROW0_Y/ROW_H）

    v2 逻辑：难度/人数用多模板最近邻分类（抗字体渲染变化），
    锁用 lock_icon 模板匹配（替代亮度标准差）。
    """
    cx = count_x if count_x is not None else BASE_COUNT_X
    sc = scale if scale else 1.0
    r0 = row0_y if row0_y else ROW0_Y
    rh = row_h if row_h else ROW_H
    y = r0 + (row_idx - 1) * rh + _PAD[1]

    off_diff = COL_OFFSET["difficulty"] * sc
    off_stat = COL_OFFSET["status"] * sc
    dx = cx + off_diff
    sx = cx + off_stat

    use_v2 = os.path.exists(os.path.join(TPL_DIR, "d_nightmare.png"))
    if use_v2:
        # ---- 难度：4 类最近邻 ----
        d_scores = {t: match_score(prepped, t, dx, y, search=5) for t in DIFF_TPLS}
        best_d = max(d_scores, key=lambda k: d_scores[k])
        s_nm = d_scores["d_nightmare"]
        is_nightmare = (best_d == "d_nightmare" and s_nm >= THR_V2)
        is_hard = (best_d in ("d_speed", "d_common") and d_scores[best_d] >= THR_V2)
        diff_name = {"d_nightmare": "nightmare", "d_speed": "speed",
                     "d_expert": "expert", "d_common": "common"}.get(best_d, "unknown")

        # ---- 人数：{1,2,4,6}/6 串最近邻 → 1 / 6 / 2-5 ----
        n_scores = {t: match_score(prepped, t, cx, y, search=5) for t in CNT_TPLS}
        best_n = max(n_scores, key=lambda k: n_scores[k])
        if n_scores[best_n] < THR_V2:
            count, count_is_1, count_is_6 = "?", False, False
        elif best_n == "n_1":
            count, count_is_1, count_is_6 = "1", True, False
        elif best_n == "n_6":
            count, count_is_1, count_is_6 = "6", False, True
        else:
            count, count_is_1, count_is_6 = "2-5", False, False

        # ---- 状态：刚开始（蓝底橙字/黄底白字两模板取 max） ----
        s_st = _max_of(["status2", "status2_g"], prepped, sx, y, search=6)
        is_starting = s_st >= THR_V2

        # ---- 锁：lock_icon 模板（双底色取 max）。
        # 实测（2026-09-12 两帧 16 行样本）：有锁 0.68~0.97，无锁 0.23~0.48，0.55 分界清晰；
        # 亮度 std 兜底会误报（无锁行可达 39+，ID 数字边缘干扰），已弃用。
        s_lock_img = _max_of(["lock_icon", "lock_icon2"], prepped,
                             cx + LOCK_CX_OFF * sc, y, search=5)
        has_lock = s_lock_img >= 0.55
        s_lock = s_lock_img

        ok = (not has_lock) and is_nightmare and (not count_is_1) and \
             (not count_is_6) and is_starting

        return {
            "row": row_idx,
            "y": y,
            "scores": {
                "lock": round(s_lock, 3),
                "nightmare": round(s_nm, 3),
                "hard": round(float(max(d_scores["d_speed"], d_scores["d_common"])), 3),
                "count1": round(n_scores["n_1"], 3),
                "count6": round(n_scores["n_6"], 3),
                "status": round(s_st, 3),
                "diff_best": best_d,
                "count_best": best_n,
            },
            "has_lock": has_lock,
            "difficulty": diff_name if d_scores[best_d] >= THR_V2 else "unknown",
            "count": count,
            "starting": is_starting,
            "ok": ok,
        }

    # ---- v1 旧逻辑回退（无 v2 模板时） ----
    s_lock = lock_std(rgb, y, cx, sc)
    s_nm = _max_of(["nightmare_y", "nightmare_g"], prepped, dx, y)
    s_hd = match_score(prepped, "hard_g", dx, y)
    s_c1 = _max_of(["count1_y", "count1_g"], prepped, cx, y)
    s_c6 = _max_of(["count6_y", "count6_g"], prepped, cx, y)
    s_st = _max_of(["status_y", "status_g"], prepped, sx, y)

    has_lock = s_lock >= LOCK_STD_THR
    is_nightmare = (s_nm >= THR_TEXT) and (s_nm > s_hd)
    is_hard = (s_hd >= THR_TEXT) and (s_hd >= s_nm)
    count_is_1 = (s_c1 >= THR_TEXT) and (s_c1 > s_c6)
    count_is_6 = (s_c6 >= THR_TEXT) and (s_c6 >= s_c1)
    is_starting = s_st >= THR_TEXT

    ok = (not has_lock) and is_nightmare and (not count_is_1) and (not count_is_6) and is_starting

    return {
        "row": row_idx,
        "y": y,
        "scores": {
            "lock": round(s_lock, 1),
            "nightmare": round(s_nm, 3),
            "hard": round(s_hd, 3),
            "count1": round(s_c1, 3),
            "count6": round(s_c6, 3),
            "status": round(s_st, 3),
        },
        "has_lock": has_lock,
        "difficulty": "nightmare" if is_nightmare else ("hard" if is_hard else "unknown"),
        "count": "1" if count_is_1 else ("6" if count_is_6 else "2-5"),
        "starting": is_starting,
        "ok": ok,
    }


def scan_rooms(rgb, prepped, rows=None, count_x=None, scale=1.0, row0_y=None, row_h=None):
    rows = rows or MAX_ROWS
    return [judge_row(rgb, prepped, i, count_x, scale, row0_y, row_h)
            for i in range(1, rows + 1)]


def pick_room(rgb, prepped, rows=None, count_x=None, scale=1.0, row0_y=None, row_h=None):
    """返回第一个符合条件的房间行（dict）或 None。"""
    for r in scan_rooms(rgb, prepped, rows=rows, count_x=count_x, scale=scale,
                        row0_y=row0_y, row_h=row_h):
        if r["ok"]:
            return r
    return None


def click_x(count_x=None, scale=1.0):
    """点击整行时使用的 x（取地图列附近，避开锁和数字）。"""
    cx = count_x if count_x is not None else BASE_COUNT_X
    sc = scale if scale else 1.0
    return int(round(cx + COL_OFFSET["map"] * sc))


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "samples", "lobby.jpg")
    im = to_ref(Image.open(path).convert("RGB"))
    rgb = np.asarray(im, dtype=np.float32)
    prepped = prep_full(gray_of(im))
    loc = locate_count_col(prepped)
    print("自动定位:", loc)
    cxx = loc[0] if loc else None
    for r in scan_rooms(rgb, prepped, count_x=cxx):
        print(r)
