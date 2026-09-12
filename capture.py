# -*- coding: utf-8 -*-
"""
截屏模块：用 mss 高速截屏（Windows 下走 Desktop Duplication，几乎不掉帧）。
优先锁定游戏窗口，找不到退回全屏，也支持手动区域。
返回 (PIL.Image, screen_rect)，screen_rect=(left, top, w, h) 用于把模型坐标映射回屏幕。

重要：mss 截的是"屏幕像素"，如果游戏窗口被别的窗口（bot 界面 / 开始菜单等）盖住，
     就会截到遮挡物。所以 grab(activate=True) 会先把游戏窗口激活到最前台再截图。
"""
import os
import sys
import time
import ctypes
import ctypes.wintypes
import mss
from PIL import Image

# 必须在导入 pygetwindow / 做任何窗口·GDI 调用之前声明 DPI 感知，
# 否则窗口坐标(逻辑)与截图(物理)会错位 1.5 倍（150% 缩放屏幕）。
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import win_dpi  # noqa: F401

import config

try:
    import pygetwindow as gw
except Exception:  # pygetwindow 在某些环境缺失时不影响全屏路径
    gw = None


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.wintypes.DWORD),
        ("biWidth", ctypes.wintypes.LONG),
        ("biHeight", ctypes.wintypes.LONG),
        ("biPlanes", ctypes.wintypes.WORD),
        ("biBitCount", ctypes.wintypes.WORD),
        ("biCompression", ctypes.wintypes.DWORD),
        ("biSizeImage", ctypes.wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.wintypes.LONG),
        ("biYPelsPerMeter", ctypes.wintypes.LONG),
        ("biClrUsed", ctypes.wintypes.DWORD),
        ("biClrImportant", ctypes.wintypes.DWORD),
    ]

# 这些关键字的窗口要排除（bot 自己的界面、登录器 标题里也可能含"生死狙击"）
EXCLUDE_SUBSTR = ("AI 助手", "助手", "WorkBuddy", "CodeBuddy", "登录器", "启动器", "Launcher")
# 优先选择标题含这些关键字的窗口（游戏主窗口而非登录器）
PREFER_SUBSTR = ("极速双擎", "生死狙击")


def _is_hidden_pos(l, t):
    """Windows 把隐藏窗口放在 (-32000,-32000) 附近；最小化窗口在 (-21333,-21333) 附近。"""
    return l <= -30000 and t <= -30000


def _hwnd_of(w):
    return getattr(w, "_hWnd", None)


def _is_minimized(w):
    hwnd = _hwnd_of(w)
    if hwnd:
        try:
            return bool(ctypes.windll.user32.IsIconic(hwnd))
        except Exception:
            pass
    return _is_hidden_pos(w.left, w.top)


def _restore_window(w):
    """还原（取消最小化）窗口。"""
    hwnd = _hwnd_of(w)
    if hwnd:
        try:
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            return
        except Exception:
            pass
    try:
        w.restore()
    except Exception:
        pass


def _pick_window(title):
    """按标题子串找最像"游戏主窗口"的窗口对象，找不到返回 None。
    规则：排除 bot 自身界面/登录器；排除真正隐藏的窗口；优先关键字匹配、尺寸足够大、面积最大。
    注意：**最小化窗口会被保留**（位置在 -21333 附近），以便上层还原它。
    """
    if gw is None or not title:
        return None
    try:
        wins = gw.getWindowsWithTitle(title)
    except Exception as e:
        print(f"[截屏] 枚举窗口失败: {e}")
        return None
    wins = [w for w in wins if w.width > 0 and w.height > 0]
    # 排除 bot 自己的界面 / 登录器（标题里也可能含"生死狙击"）
    wins = [w for w in wins
            if not any(s in (w.title or "") for s in EXCLUDE_SUBSTR)]
    # 丢弃真正隐藏的窗口（最小化的 -21333 不算，要保留以便还原）
    vis = [w for w in wins if not _is_hidden_pos(w.left, w.top)]
    if vis:
        wins = vis
    if not wins:
        return None
    # 优先含"极速双擎"等关键字的游戏主窗口
    pref = [w for w in wins if any(s in (w.title or "") for s in PREFER_SUBSTR)]
    if pref:
        wins = pref
    # 只保留尺寸足够大的窗口（避免把浏览器标签、小弹窗当成主窗口）
    big = [w for w in wins if w.width >= 800 and w.height >= 600]
    if big:
        wins = big
    # 面积最大者最可能是游戏主窗口
    return max(wins, key=lambda x: x.width * x.height)


def find_window_rect(title):
    """按标题（子串匹配）找窗口，返回 (left, top, width, height) 或 None。
    若窗口处于最小化状态，会先还原再返回其真实矩形。
    """
    w = _pick_window(title)
    if w is None:
        return None
    if _is_minimized(w):
        print("[截屏] 游戏窗口处于最小化，正在还原…")
        _restore_window(w)
        time.sleep(0.25)
        w = _pick_window(title) or w
    rect = (int(w.left), int(w.top), int(w.width), int(w.height))
    print(f"[截屏] 锁定窗口 '{w.title[:24]}': {rect}")
    return rect


_last_act_fail = 0.0   # 上次激活失败的时间戳：失败后 5s 内不重试，避免对全屏游戏造成切换风暴


def activate_window(title=None):
    """把游戏窗口激活到最前台（截图前调用，防止截到遮挡物）。返回是否成功。

    pygetwindow 的 Window.activate() 底层用的是 SetForegroundWindow，
    在调用进程不是前台进程时会被 Windows 前台锁拦截而失败。
    这里用 AttachThreadInput + ShowWindow(SW_RESTORE) + SetForegroundWindow 组合绕过，
    并用 GetForegroundWindow 校验是否真的切到了目标窗口。

    【2026-09-12 教训】全屏游戏被高频强制切换前台（每次截图都试）会触发
    显示模式重置风暴，把游戏直接卡死。因此：失败后 5 秒节流，绝不连击；
    已移除 SwitchToThisWindow（未公开 API，对全屏游戏行为不可控）。
    """
    global _last_act_fail
    title = title or config.GAME_WINDOW_TITLE

    w = _pick_window(title)
    if w is None:
        return False

    hwnd = getattr(w, "_hWnd", None)
    user32 = ctypes.windll.user32

    # 已是前台窗口就无需处理——这个检查必须放在节流之前：
    # 否则节流期内会误报"未能切到前台"，而游戏明明就在前台（2026-09-12 误报实证）。
    try:
        if hwnd and user32.GetForegroundWindow() == hwnd:
            return True
    except Exception:
        pass

    if time.time() - _last_act_fail < 5.0:
        return False   # 刚失败过，节流中：宁可这轮截图可能截到遮挡，也不折腾游戏

    if not hwnd:
        # 兜底：没有 hwnd 就用 pygetwindow 自带方法
        try:
            w.activate()
            return True
        except Exception:
            return False

    SW_RESTORE = 9
    SW_MAXIMIZE = 3

    try:
        # 仅当窗口最小化时才还原；不要对最大化窗口调用 SW_RESTORE，
        # 否则会把最大化窗口变成窗口化，导致 UI 尺寸变化、模板失配。
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
    except Exception:
        pass

    # 自动最大化：让游戏窗口尺寸固定为"最大化"，与识别模板的标定尺寸一致。
    if getattr(config, "ENSURE_MAXIMIZED", True):
        try:
            if not user32.IsZoomed(hwnd):
                user32.ShowWindow(hwnd, SW_MAXIMIZE)
        except Exception:
            pass

    ok = False
    try:
        fg = user32.GetForegroundWindow()
        tid_fg = user32.GetWindowThreadProcessId(fg, None)
        tid_tg = user32.GetWindowThreadProcessId(hwnd, None)
        attached = False
        if tid_fg and tid_tg and tid_fg != tid_tg:
            attached = bool(user32.AttachThreadInput(tid_fg, tid_tg, True))
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(tid_fg, tid_tg, False)
        ok = (user32.GetForegroundWindow() == hwnd)
    except Exception as e:
        print(f"[截屏] 强置前台异常(忽略): {e}")

    if not ok:
        # 再兜底试一次 pygetwindow 原生方法
        try:
            w.activate()
            ok = (user32.GetForegroundWindow() == hwnd)
        except Exception:
            pass

    if not ok:
        _fg = user32.GetForegroundWindow()
        _buf = ctypes.create_unicode_buffer(96)
        try:
            user32.GetWindowTextW(_fg, _buf, 96)
        except Exception:
            pass
        print("[截屏] 警告：未能把游戏窗口切到前台（当前前台=%s），可能截到遮挡物"
              % (_buf.value[:40] or "无标题"))
    if not ok:
        _last_act_fail = time.time()   # 记录失败时间，5 秒内不再重试（防切换风暴）
    # 等窗口尺寸/渲染稳定
    time.sleep(0.20)
    return ok


def _printwindow_capture(hwnd):
    """用 PrintWindow(PW_RENDERFULLCONTENT) 直接抓取窗口自身内容，
    不受遮挡/最小化影响。失败或抓到全黑时返回 None（由上层回退到 mss）。
    """
    if not hwnd:
        return None
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    try:
        wr = ctypes.wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(wr)):
            return None
        w = int(wr.right - wr.left)
        h = int(wr.bottom - wr.top)
        if w <= 0 or h <= 0:
            return None
        hdc = user32.GetWindowDC(hwnd)
        memdc = gdi32.CreateCompatibleDC(hdc)
        bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
        gdi32.SelectObject(memdc, bmp)
        ok = user32.PrintWindow(hwnd, memdc, 2)  # 2 = PW_RENDERFULLCONTENT
        bmi = _BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0
        buf = ctypes.create_string_buffer(w * h * 4)
        got = gdi32.GetDIBits(memdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(memdc)
        user32.ReleaseDC(hwnd, hdc)
        if not got:
            return None
        img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
        return img
    except Exception as e:
        print(f"[截屏] PrintWindow 失败(忽略): {e}")
        return None


def _is_blank(img):
    """判断是否接近纯色（PrintWindow 对某些硬件加速窗口会返回全黑）。"""
    try:
        lo, hi = img.convert("L").getextrema()
        return (hi - lo) < 8
    except Exception:
        return False


def grab(region=None, resize=True, activate=False, prefer_printwindow=False):
    """
    截一张图。
    region: (left, top, w, h) 屏幕坐标；为 None 时按 config 自动选择。
    resize: True=按 config.MAX_IMAGE_SIZE 缩放（给视觉大模型用，省带宽）；
            False=保留原始分辨率（给 gvision 局部模板匹配用，避免小字被压糊）。
    activate: True=先激活游戏窗口到前台再截图（防止截到遮挡物）。
    prefer_printwindow: True=优先用 PrintWindow 抓窗口自身内容（不受遮挡），失败再回退 mss。
            注意：本游戏（GPU 直绘）PrintWindow 返回全黑，故默认 False，靠 mss + 置前台。
    返回 (img, screen_rect)
    """
    if region is None:
        region = config.CAPTURE_REGION

    # 自动模式：优先锁定游戏窗口
    if region is None:
        w = _pick_window(config.GAME_WINDOW_TITLE)
        if w is not None:
            if _is_minimized(w):
                _restore_window(w)
                time.sleep(0.25)
                w = _pick_window(config.GAME_WINDOW_TITLE) or w
            hwnd = _hwnd_of(w)

            # 1) 优先 PrintWindow（不受遮挡影响）
            if prefer_printwindow:
                img = _printwindow_capture(hwnd)
                if img is not None and not _is_blank(img):
                    rect = (int(w.left), int(w.top), int(w.width), int(w.height))
                    if resize:
                        _apply_resize(img)
                    return img, rect

            # 2) 回退 mss：先把窗口激活到前台，再按窗口矩形截屏
            if activate:
                activate_window(config.GAME_WINDOW_TITLE)
                w = _pick_window(config.GAME_WINDOW_TITLE) or w
            region = (int(w.left), int(w.top), int(w.width), int(w.height))

    if region is None:
        # 退回主显示器全屏
        with mss.mss() as sct:
            mon = sct.monitors[1]
            region = (mon["left"], mon["top"], mon["width"], mon["height"])

    left, top, w, h = [int(v) for v in region]
    with mss.mss() as sct:
        shot = sct.grab({"left": left, "top": top, "width": w, "height": h})
        # mss 返回 BGRA；用 .rgb 直接拿 RGB 字节
        img = Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)

    if resize:
        _apply_resize(img)

    return img, (left, top, w, h)


def _apply_resize(img):
    max_w, max_h = config.MAX_IMAGE_SIZE
    if img.width > max_w or img.height > max_h:
        img.thumbnail((max_w, max_h), Image.LANCZOS)


def save_debug(img, decision, screen_rect, path):
    """在截图上画红圈标记目标点并保存，便于你回看模型判断得准不准。"""
    try:
        from PIL import ImageDraw
        d = img.copy()
        draw = ImageDraw.Draw(d)
        if decision and decision.get("has_target"):
            tx = float(decision.get("target_x", 0.5))
            ty = float(decision.get("target_y", 0.5))
            # 模型坐标是归一化的，缩放到当前图尺寸
            px = int(tx * d.width)
            py = int(ty * d.height)
            r = max(12, int(min(d.width, d.height) * 0.04))
            draw.ellipse([px - r, py - r, px + r, py + r], outline="red", width=3)
            draw.line([(px - r * 2, py), (px + r * 2, py)], fill="red", width=1)
            draw.line([(px, py - r * 2), (px, py + r * 2)], fill="red", width=1)
            label = f"({tx:.2f},{ty:.2f}) {decision.get('action','')} c={decision.get('confidence',0):.2f}"
            draw.text((10, 10), label, fill="red")
        d.save(path)
    except Exception as e:
        print(f"[调试] 保存标记帧失败: {e}")


if __name__ == "__main__":
    im, rect = grab()
    os.makedirs("debug_frames", exist_ok=True)
    im.save("debug_frames/test_capture.png")
    print("截屏测试 OK，尺寸:", im.size, "屏幕区域:", rect)
