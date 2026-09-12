# -*- coding: utf-8 -*-
"""
auto_lobby.py —— 沙漠奇兵2 · 噩梦 自动挂机找房引擎

闭环流程：
    找房(点地图节点 → 点房间列表 → 扫描筛选 → 点整行)
      -> 进房挂机(等「确定」出现)
      -> 点「确定」-> 点「退出」
      -> 等加载完成(回到大厅)
      -> 回到找房，循环

设计原则：
  * 识别用 gvision（局部模板匹配，无大模型，CPU 极低）。
  * 频率默认 3 秒一次轮询；每次动作后做"校验 + 重试"，抗卡顿。
  * 所有点击坐标来自 lobby_calib.json（参考分辨率 1920x1077 坐标系），
    运行时按游戏窗口实际大小换算，因此分辨率/窗口变化不影响。
  * 热键 F12 急停（与主脚本一致）。

用法：
    python auto_lobby.py            # 开始跑
    python auto_lobby.py --dry      # 只识别不点击（安全观察）
"""
import argparse
import ctypes
import json
import os
import sys
import time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 声明 DPI 感知（必须在任何窗口/截图/鼠标调用之前），保证坐标与截图都用物理像素。
import win_dpi  # noqa: F401

import config
import gvision as gv

CALIB_PATH = os.path.join(HERE, "lobby_calib.json")

DEFAULT_CALIB = {
    "map_node_desert2": [862, 205],
    "btn_roomlist": [1085, 588],
    "btn_chat": [795, 300],
    # btn_ok / btn_quit 不在用户校准文件里时用的兜底值：
    # 取自结算页截图精标定（confirm.jpg / after_ok.jpg），模板匹配已验证区分度足够。
    "btn_ok": [980, 451],
    "btn_quit": [950, 666],
    "wait_sec_scan": 1.5,
    "wait_sec_battle": 2,
    "max_wait_min": 5,
    "click_retry": 3,
    "click_retry_gap": 0.4,
    "wait_sec_load": 8,
    # 点击方式：pyautogui=移动真实鼠标点击；postmsg=向窗口直接投递鼠标消息（不占前台）
    "click_mode": "pyautogui",
}


def _token_elevated(pid):
    """查询指定进程是否以管理员权限运行（None=查询失败，通常意味着对方权限更高）。"""
    k32 = ctypes.windll.kernel32
    a32 = ctypes.windll.advapi32
    h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None
    tok = ctypes.c_void_p()
    if not a32.OpenProcessToken(h, 0x0008, ctypes.byref(tok)):  # TOKEN_QUERY
        k32.CloseHandle(h)
        return None
    val = ctypes.c_uint32(0)
    ret = ctypes.c_uint32(0)
    ok = a32.GetTokenInformation(tok, 20, ctypes.byref(val), 4, ctypes.byref(ret))  # TokenElevation
    k32.CloseHandle(tok)
    k32.CloseHandle(h)
    return bool(val.value) if ok else None


def precheck_elevation():
    """启动前权限自检：游戏是管理员而 bot 不是时，Windows UIPI 会丢弃注入的点击。"""
    try:
        from capture import _pick_window, _hwnd_of
        w = _pick_window(config.GAME_WINDOW_TITLE)
        if not w:
            print("[权限] 未找到游戏窗口，跳过权限自检")
            return True
        pid = ctypes.c_uint32(0)
        ctypes.windll.user32.GetWindowThreadProcessId(_hwnd_of(w), ctypes.byref(pid))
        game = _token_elevated(pid.value) if pid.value else None
        mine = _token_elevated(os.getpid())
        print("[权限] 游戏进程管理员=%s | 本进程管理员=%s" % (game, mine))
        if (game is True or game is None) and mine is False:
            print("❌ 权限不足：游戏以管理员权限运行，而 bot 是普通权限！")
            print("   Windows(UIPI) 会直接丢弃 bot 注入的鼠标事件——这就是「点了没反应」的最常见原因。")
            print("   解决：完全关闭软件，右键终端/软件 →「以管理员身份运行」后再点开始。")
            print("   （确信游戏并非管理员权限、要强行继续，可加参数 --force）")
            return False
        return True
    except Exception as e:
        print("[权限] 自检异常，继续运行:", e)
        return True


def load_calib():
    cfg = dict(DEFAULT_CALIB)
    if os.path.exists(CALIB_PATH):
        try:
            with open(CALIB_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as e:
            print("[警告] 读取校准文件失败，用默认值:", e)
    return cfg


class LobbyBot:
    def __init__(self, calib, dry=False):
        self.cfg = calib
        self.dry = dry
        self.ref_w, self.ref_h = gv.REF_W, gv.REF_H
        self._row_grid = None   # (row0_y, row_h, time) 行格缓存，避免每轮 3~6 秒网格搜索

    # ---------- 截屏 ----------
    def shot(self, resize=False, activate=True):
        """返回 (PIL图, rect)；rect=(x,y,w,h) 为游戏画面在屏幕上的矩形。
        resize=False：保留原始分辨率交给 gvision 做局部模板匹配（避免小字被压糊）。
        activate=True：截图前先把游戏窗口激活到最前台，否则会截到盖在上面的窗口。
        """
        from capture import grab
        img, rect = grab(resize=resize, activate=activate)
        return img, rect

    # ---------- 坐标换算 + 点击 ----------
    def to_screen(self, rect, pt):
        """参考坐标 -> 屏幕坐标。"""
        rx, ry, rw, rh = rect
        x = rx + pt[0] / self.ref_w * rw
        y = ry + pt[1] / self.ref_h * rh
        return int(round(x)), int(round(y))

    def click(self, rect, pt, label=None, times=None, gap=None):
        """点击参考坐标处的按钮，带重试。
        label：可选描述，用于日志说明点击的是哪里（如"沙漠奇兵2节点"）。
        click_mode：pyautogui=真实鼠标；postmsg=向窗口投递鼠标消息（不占前台）。
        """
        times = times or self.cfg.get("click_retry", 3)
        gap = gap or self.cfg.get("click_retry_gap", 0.4)
        sx, sy = self.to_screen(rect, pt)
        tag = ("[%s]" % label) if label else ""
        mode = self.cfg.get("click_mode", "pyautogui")
        print("  [点击]%s ref=%s -> screen=%s（dry=%s mode=%s）"
              % (tag, pt, (sx, sy), self.dry, mode))
        if self.dry:
            return
        if mode == "postmsg":
            for i in range(times):
                self._postmsg_click(sx, sy)
                time.sleep(gap)
            return
        import pyautogui
        # 安全护栏（2026-09-12）：真实鼠标点击会落在"该屏幕点最上层的窗口"上。
        # 游戏全屏在底层、bot 界面/聊天窗浮在上层时，若目标点恰好被别的窗口盖住，
        # 这一 click 就会点进那个窗口（曾疑似点到 UI 的"停止"按钮导致 bot 无声消失）。
        # 所以：点击前用 WindowFromPoint 确认该点顶层窗口确实是游戏，否则跳过。
        if not self._point_on_game(sx, sy):
            now = time.time()
            if now - getattr(self, "_last_skip_click", 0) > 10:
                self._last_skip_click = now
                print("  [点击][跳过] (%d, %d) 被其他窗口盖住（前台=%s），不点，避免误点你的窗口"
                      % (sx, sy, self.fg_title()))
            return
        for i in range(times):
            pyautogui.moveTo(sx, sy, duration=0.08)
            time.sleep(0.05)
            pyautogui.click()
            time.sleep(gap)

    def _point_on_game(self, sx, sy):
        """屏幕点 (sx, sy) 的顶层窗口是否为游戏窗口（或其子窗口）。"""
        try:
            from ctypes import wintypes
            u32 = ctypes.windll.user32
            hwnd = self._get_hwnd()
            if not hwnd:
                return True   # 拿不到游戏窗口时放行，保持旧行为
            p = wintypes.POINT(int(sx), int(sy))
            u32.WindowFromPoint.restype = wintypes.HWND
            top = u32.WindowFromPoint(ctypes.byref(p))
            if not top:
                return False
            root = u32.GetAncestor(top, 2)   # 2 = GA_ROOT
            return (root or top) == hwnd
        except Exception:
            return True

    def _get_hwnd(self):
        if getattr(self, "_hwnd", None):
            return self._hwnd
        try:
            from capture import _pick_window, _hwnd_of
            w = _pick_window(config.GAME_WINDOW_TITLE)
            self._hwnd = _hwnd_of(w) if w else None
        except Exception:
            self._hwnd = None
        return self._hwnd

    def _postmsg_click(self, sx, sy):
        """PostMessage 直接向游戏窗口投递左键按下/抬起（不需要前台，可绕过部分注入拦截）。"""
        from ctypes import wintypes
        u32 = ctypes.windll.user32
        hwnd = self._get_hwnd()
        if not hwnd:
            print("  [点击] postmsg 拿不到窗口句柄，本组点击跳过")
            return
        pt = wintypes.POINT(int(sx), int(sy))
        u32.ScreenToClient(hwnd, ctypes.byref(pt))
        lp = ((pt.y & 0xFFFF) << 16) | (pt.x & 0xFFFF)
        u32.PostMessageW(hwnd, 0x0201, 0x00000001, lp)  # WM_LBUTTONDOWN, MK_LBUTTON
        time.sleep(0.06)
        u32.PostMessageW(hwnd, 0x0202, 0, lp)           # WM_LBUTTONUP

    def save_debug(self, img, name, rect=None):
        """把当前截图保存到 debug_frames/auto_lobby/，方便回看 bot 实际看到了什么。"""
        try:
            debug_dir = os.path.join(HERE, "debug_frames", "auto_lobby")
            os.makedirs(debug_dir, exist_ok=True)
            ts = time.strftime("%m%d-%H%M%S")
            pid = os.getpid()
            path = os.path.join(debug_dir, f"{ts}_{pid}_{name}.png")
            img.save(path)
            extra = f" rect={rect}" if rect else ""
            print(f"  [调试] 截图已保存: {path}{extra}")
        except Exception as e:
            print(f"  [调试] 保存截图失败: {e}")

    # ---------- 识别 ----------
    def analyze(self, img):
        """返回 (rows, count_x, scale)。"""
        im = gv.to_ref(img)
        rgb = np.asarray(im, dtype=np.float32)
        prepped = gv.prep_full(gv.gray_of(im))
        loc = gv.locate_count_col(prepped)
        count_x = loc[0] if loc else None
        scale = loc[2] if loc else 1.0
        # 动态行格：面板行高随布局变化（实测 20.1 / 23 两态），固定值会整体错位。
        # 网格搜索一次要数秒，缓存 60 秒内复用，后续每轮扫描 <1 秒。
        row0_y, row_h = None, None
        if count_x is not None:
            now = time.time()
            if self._row_grid and now - self._row_grid[2] < 60:
                row0_y, row_h = self._row_grid[0], self._row_grid[1]
            else:
                row0_y, row_h = gv.detect_row_grid(prepped, count_x, scale)
                if row0_y is not None:
                    self._row_grid = (row0_y, row_h, now)
                    print("  [行格] 自动检测: 行1 y=%.1f 行高=%.1f（缓存 60s）"
                          % (row0_y, row_h))
                else:
                    print("  [行格] 自动检测失败，回退常量 行1 y=%s 行高=%s"
                          % (gv.ROW0_Y, gv.ROW_H))
        rows = gv.scan_rooms(rgb, prepped, count_x=count_x, scale=scale,
                             row0_y=row0_y, row_h=row_h)
        return rows, count_x, scale

    def find_ok_to_enter(self, rows):
        cands = [r for r in rows if r["ok"]]
        if not cands:
            return None
        # 只区分 1/6、6/6 和 2-5，暂时取第一个命中（后续补 2~5 样本再改成"人数最多"）
        return cands[0]

    # ---------- 失焦提示框 ----------
    # 「点击游戏画面继续操作」提示框中心（ref 坐标）；模板 templates/overlay_focus.png
    OVERLAY_XY = (963, 411)

    def detect_overlay(self, img):
        """检测画面中是否挂着「点击游戏画面继续操作」失焦提示框。"""
        if not os.path.exists(os.path.join(gv.TPL_DIR, "overlay_focus.png")):
            return False
        im = gv.to_ref(img)
        prepped = gv.prep_full(gv.gray_of(im))
        return gv.match_score(prepped, "overlay_focus",
                              self.OVERLAY_XY[0], self.OVERLAY_XY[1], search=45) >= 0.45

    def fg_title(self):
        """当前前台窗口标题（诊断用：谁抢了游戏的前台）。"""
        try:
            import ctypes
            from ctypes import wintypes
            u32 = ctypes.windll.user32
            u32.GetForegroundWindow.restype = wintypes.HWND
            u32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
            h = u32.GetForegroundWindow()
            buf = ctypes.create_unicode_buffer(128)
            u32.GetWindowTextW(h, buf, 128)
            return buf.value[:40] or "(无标题)"
        except Exception:
            return "?"

    # ---- 防挂机微动 ----
    # 【2026-09-12 破案】「点击游戏画面继续操作」提示框根本不是失焦——
    # 日志实证遮罩挂着时前台=游戏自己。真因：4399 平台检测到一段时间无
    # 鼠标移动/输入就暂停游戏弹此提示（防挂机）。bot 挂机时鼠标静止，
    # 几秒必弹。对策：每隔一两秒把鼠标微微挪 6px（模拟人在操作）。
    _wiggle = False

    def keep_alive(self):
        """鼠标微微动一下，防止 4399 平台判定挂机而暂停游戏。
        仅当游戏在前台时才动：游戏在后台时微动毫无意义，还会干扰用户操作鼠标。"""
        try:
            u32 = ctypes.windll.user32
            hwnd = self._get_hwnd()
            if hwnd and u32.GetForegroundWindow() != hwnd:
                return
            import pyautogui
            self._wiggle = not self._wiggle
            pyautogui.moveRel(6 if self._wiggle else -6,
                              3 if self._wiggle else -3, duration=0.03)
        except Exception:
            pass

    def ensure_focus(self):
        """游戏失焦时会挂提示框，任何点击都被它吃掉——识别到就点它一下恢复。
        点完 0.8s 复查，仍在则再点一次（应对刚弹出、第一次没点中的情况）。
        返回最新 (img, rect)。"""
        img, rect = self.shot()
        if img is None:
            return img, rect
        if self.detect_overlay(img):
            print("  [焦点] 检测到「点击游戏画面继续操作」挂机暂停提示（当前前台=%s），点击恢复"
                  % self.fg_title())
            self.click(rect, list(self.OVERLAY_XY), label="失焦提示框", times=1, gap=0.6)
            time.sleep(0.8)
            img, rect = self.shot()
            if self.detect_overlay(img):
                print("  [焦点] 提示框仍在，再点一次")
                self.click(rect, list(self.OVERLAY_XY), label="失焦提示框(重试)", times=1, gap=0.6)
                time.sleep(0.5)
                img, rect = self.shot()
        return img, rect

    # ---------- 各阶段 ----------
    def wait_roomlist_open(self, timeout=8.0, return_img=False):
        """等待房间列表出现（用人数表头是否可定位来判断）。
        return_img=True 时返回 (opened, img, rect)，复用同一张截图给后续分析，
        避免 analyze 二次截屏截到列表已关闭的帧。
        """
        t0 = time.time()
        last = (None, None)
        while time.time() - t0 < timeout:
            img, rect = self.shot()
            last = (img, rect)
            im = gv.to_ref(img)
            prepped = gv.prep_full(gv.gray_of(im))
            loc = gv.locate_count_col(prepped)
            if loc:
                print("  [定位] 房间列表已打开，score=%.3f scale=%.2f"
                      % (loc[1], loc[2]))
                if return_img:
                    return True, img, rect
                return True
            time.sleep(0.6)
        print("  [提示] 未能定位「人数」表头（房间列表可能未打开或识别失败）")
        if last[0] is not None:
            self.save_debug(last[0], "02_roomlist_not_found", last[1])
        if return_img:
            return False, last[0], last[1]
        return False

    def locate_list(self, img):
        """尝试定位房间列表（人数表头）。返回 locate 结果 tuple 或 None。"""
        try:
            im = gv.to_ref(img)
            prepped = gv.prep_full(gv.gray_of(im))
            return gv.locate_count_col(prepped)
        except Exception:
            return None

    def stage_enter_room(self):
        """阶段A：打开房间列表并进入符合条件的房间。成功返回 True。"""
        cfg = self.cfg
        img, rect = self.shot()
        print("  [窗口] 游戏窗口 rect=%s" % (rect,))
        self.save_debug(img, "00_initial", rect)
        self.keep_alive()   # 防挂机微动（4399 无输入会暂停游戏弹提示）

        # A0：失焦处理——识别到「点击游戏画面继续操作」提示框就点它一下恢复焦点，
        # 再继续后续点击（没检测到就不乱点）。
        img, rect = self.ensure_focus()

        # A1/A2：「房间列表」按钮是开关式的——列表已开着时再点会把面板关掉，
        # 点地图节点也会点到面板外把面板收起。所以先检测列表是否已开，已开则跳过点击。
        if self.locate_list(img) is not None:
            print("  [定位] 房间列表已开着，跳过节点/按钮点击")
        else:
            self.click(rect, cfg["map_node_desert2"], label="沙漠奇兵2节点")
            time.sleep(0.5)
            self.click(rect, cfg["btn_roomlist"], label="房间列表按钮")

        # 点完房间列表后截一张，看面板是否真的弹出来了
        img_after, rect_after = self.shot()
        self.save_debug(img_after, "01_after_roomlist_click", rect_after)

        opened, img, rect = self.wait_roomlist_open(return_img=True)
        if not opened:
            print("  [提示] 房间列表似乎没打开，检查失焦提示框后重试")
            img, rect = self.ensure_focus()
            if self.locate_list(img) is None:
                self.click(rect, cfg["map_node_desert2"], label="沙漠奇兵2节点")
                time.sleep(0.4)
                self.click(rect, cfg["btn_roomlist"], label="房间列表按钮")
            opened, img, rect = self.wait_roomlist_open(return_img=True)

        if not opened:
            return False

        # A3：分析房间列表（复用 wait_roomlist_open 成功时的同一张截图）
        rows, count_x, scale = self.analyze(img)
        n_ok = sum(1 for r in rows if r["ok"])
        print("  [扫描] 识别 %d 行，符合条件 %d 个" % (len(rows), n_ok))
        if self.dry:
            print("  [dry] 自动定位 count_x=%s scale=%.3f，扫描 %d 行:"
                  % (count_x, scale, len(rows)))
            for r in rows:
                flag = "✓" if r["ok"] else " "
                sc = r["scores"]
                print("    [%s] 行%-2d y=%d 难度=%-8s 人数=%s 锁=%s 刚开始=%s (c1=%.2f c6=%.2f)"
                      % (flag, r["row"], r["y"], r["difficulty"], r["count"],
                         r["has_lock"], r["starting"], sc["count1"], sc["count6"]))
        pick = self.find_ok_to_enter(rows)
        if not pick:
            return False
        cx = gv.click_x(count_x, scale)
        label = "房间行-第%d行" % pick["row"]
        print("  [命中] 第 %d 行 (y=%d) -> 点击 (%d, %d)" % (pick["row"], pick["y"], cx, pick["y"]))
        # 识别计算期间游戏可能失焦（弹「点击游戏画面继续操作」遮罩），
        # 不点掉它这次点击会被遮罩吃掉 —— 点击房间行前必须再确保一次焦点。
        img, rect = self.ensure_focus()
        self.click(rect, [cx, pick["y"]], label=label, times=1)
        return True

    def wait_battle_end(self, timeout=120):
        """阶段B：挂机；检测到「确定」出现则返回 True。
        超时返回 False（很可能没真正进房），由上层回大厅重找，避免卡死。
        """
        t0 = time.time()
        warned = False
        n = 0
        while True:
            n += 1
            self.keep_alive()   # 挂机等待时鼠标静止最久，必须定期微动防暂停
            img, rect = self.shot()
            if self.detect_overlay(img):
                # 提示框正好盖住「确定」按钮区域，必须先点掉，否则结算判定永远失败
                now = time.time()
                if now - getattr(self, "_last_ov_print", 0) > 10:
                    self._last_ov_print = now
                    print("  [焦点] 挂机中检测到失焦提示框（前台=%s），点击恢复"
                          % self.fg_title())
                self.click(rect, list(self.OVERLAY_XY), label="失焦提示框(挂机中)", times=1, gap=0.6)
                time.sleep(1)
                continue
            ok = self.detect_ok_button(img)
            if ok is True:
                return True
            if ok is None:
                # 模板缺失：无法自动判定结算界面
                if not warned:
                    print("  [提示] 缺少 templates/btn_ok.png，无法自动判定结算界面。")
                    print("         请提供一张「任务完成」界面截图以便裁该模板；")
                    print("         现在先用固定时长兜底（等待 30 秒后按已结算处理）。")
                    warned = True
                if time.time() - t0 > 30:
                    return True
            if time.time() - t0 > timeout:
                return False
            print("  [挂机#%d] 已等待 %ds，检测「确定」中…" % (n, int(time.time() - t0)))
            time.sleep(self.cfg.get("wait_sec_battle", 2))

    def detect_ok_button(self, img):
        """检测「确定」按钮是否出现。

        依赖 templates/btn_ok.png（从"任务完成"界面裁的小图）。
        若模板不存在，返回 None 表示"无法判定"，由上层用兜底逻辑处理。
        """
        if not os.path.exists(os.path.join(gv.TPL_DIR, "btn_ok.png")):
            return None
        im = gv.to_ref(img)
        prepped = gv.prep_full(gv.gray_of(im))
        pt = self.cfg["btn_ok"]
        return gv.match_score(prepped, "btn_ok", pt[0], pt[1], search=14) >= 0.32

    def detect_quit_button(self, img):
        """检测「退出」按钮是否出现（点确定之后的界面）。"""
        if not os.path.exists(os.path.join(gv.TPL_DIR, "btn_quit.png")):
            return None
        im = gv.to_ref(img)
        prepped = gv.prep_full(gv.gray_of(im))
        pt = self.cfg["btn_quit"]
        return gv.match_score(prepped, "btn_quit", pt[0], pt[1], search=14) >= 0.32

    def stage_settle(self):
        """阶段C：点「确定」-> 等「退出」出现 -> 点「退出」-> 等加载 -> 回大厅。"""
        img, rect = self.shot()
        self.click(rect, self.cfg["btn_ok"], label="确定按钮", times=1, gap=0.6)

        # 等"退出"按钮出现（最多 8 秒）
        t0 = time.time()
        while time.time() - t0 < 8:
            img, rect = self.shot()
            q = self.detect_quit_button(img)
            if q is True:
                break
            if q is None:      # 模板缺失，直接继续
                break
            time.sleep(0.5)

        self.click(rect, self.cfg["btn_quit"], label="退出按钮", times=1, gap=0.6)
        # 等「正在加载资源」结束、回到大厅（固定等待；卡顿时可适当加长）
        time.sleep(self.cfg.get("wait_sec_load", 8))

    # ---------- 主循环 ----------
    def run(self):
        from actions import start_hotkeys, state
        start_hotkeys()
        print("=" * 62)
        print("沙漠奇兵2·噩梦 自动挂机找房 已启动")
        print("  扫描间隔 %ss，挂机检测 %ss，找房上限 %s 分钟"
              % (self.cfg["wait_sec_scan"], self.cfg["wait_sec_battle"], self.cfg["max_wait_min"]))
        if self.dry:
            print("  【dry-run】只识别，不点击鼠标")
        print("  F12 退出 / F9 暂停（与主脚本一致）")
        print("=" * 62)

        scan_sec = self.cfg.get("wait_sec_scan", 3)
        max_wait = self.cfg.get("max_wait_min", 5) * 60
        enter_timeout = self.cfg.get("enter_timeout", 120)
        no_find_since = time.time()
        scan_n = 0

        while not state["quit"]:
            if state["paused"]:
                time.sleep(0.3)
                continue
            scan_n += 1
            try:
                entered = self.stage_enter_room()
                if not entered:
                    if time.time() - no_find_since > max_wait:
                        print("  [提醒] 已经 %.0f 分钟没有符合条件的房间了" % (max_wait / 60))
                        no_find_since = time.time()
                    print("  [扫描#%d] 暂无可进房间，%ds 后重试" % (scan_n, scan_sec))
                    time.sleep(scan_sec)
                    continue

                no_find_since = time.time()
                if not self.wait_battle_end(timeout=enter_timeout):
                    print("  [提示] 进房后 %ds 未出现「确定」，判定进房可能失败，回大厅重找"
                          % enter_timeout)
                    continue
                self.stage_settle()
            except Exception as e:
                print("[错误]", e)
                time.sleep(2.0)

        print("已退出。")


class _Tee:
    """把 stdout/stderr 同步落盘到 bot_run.log（追加模式）。
    无论由 app.py（UI）启动还是命令行直跑，日志都完整留档便于远程诊断；
    同时保留原 stdout（PIPE/控制台），不影响 app.py 的 UI 终端显示。
    """
    def __init__(self, path):
        self.f = open(path, "a", encoding="utf-8", errors="replace")
        self.raw = sys.__stdout__

    def write(self, s):
        try:
            self.f.write(s)
            self.f.flush()
        except Exception:
            pass
        try:
            if self.raw:
                self.raw.write(s)
        except Exception:
            pass
        return len(s)

    def flush(self):
        for x in (self.f, self.raw):
            try:
                if x:
                    x.flush()
            except Exception:
                pass


def main():
    ap = argparse.ArgumentParser(description="沙漠奇兵2 自动挂机找房")
    ap.add_argument("--dry", action="store_true", help="只识别不点击")
    ap.add_argument("--force", action="store_true", help="跳过管理员权限自检")
    args = ap.parse_args()
    if not args.dry and not args.force and not precheck_elevation():
        sys.exit(2)
    # 日志自留档：print 同时写 bot_run.log（追加；UI 每次启动会先清空）
    sys.stdout = _Tee(os.path.join(HERE, "bot_run.log"))
    sys.stderr = _Tee(os.path.join(HERE, "bot_run.log"))
    bot = LobbyBot(load_calib(), dry=args.dry)
    try:
        bot.run()
    finally:
        # 无论正常退出（F12）、异常还是被外部结束前捕获到的路径，都留下一行结束标记，
        # 方便事后从 bot_run.log 判断进程是怎么消失的。
        print("[结束] bot 进程退出。")


if __name__ == "__main__":
    main()
