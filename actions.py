# -*- coding: utf-8 -*-
"""
执行器：把模型决策变成真实键鼠操作；并用 pynput 监听热键。
坐标映射：模型给的是归一化坐标(0~1)，乘上截屏区域尺寸得到屏幕坐标。
"""
import time

import pyautogui
from pynput import keyboard

import config

# 把鼠标甩到屏幕角落会触发 pyautogui 的 FAILSAFE，避免失控；保留它当紧急保险。
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.0

# 全局运行状态，被热键修改
state = {
    "auto": config.AUTO_EXECUTE,   # 是否真正操作键鼠
    "paused": False,               # 主循环是否暂停
    "quit": False,                 # 是否退出
    "firing": False,               # 当前是否按住左键（连射模式）
}


def _on_press(key):
    try:
        k = key.name
    except Exception:
        k = str(key)
    if k == config.TOGGLE_KEY:
        state["auto"] = not state["auto"]
        print(f"[热键] 自动操作 => {'开' if state['auto'] else '关'}")
    elif k == config.PAUSE_KEY:
        state["paused"] = not state["paused"]
        print(f"[热键] 主循环 => {'暂停' if state['paused'] else '继续'}")
    elif k == config.QUIT_KEY:
        state["quit"] = True
        print("[热键] 请求退出")


def start_hotkeys():
    if config.ENABLE_HOTKEYS:
        listener = keyboard.Listener(on_press=_on_press)
        listener.daemon = True
        listener.start()


def _stop_fire():
    if state["firing"]:
        pyautogui.mouseUp(button=config.CLICK_BUTTON)
        state["firing"] = False


def execute(decision, screen_rect):
    """
    decision: agent.safe_get 的结果（dict）
    screen_rect: (left, top, w, h) 截屏在屏幕上的实际区域
    """
    # 连射模式：本帧没开火信号就松手
    if config.HOLD_FIRE and not config.AUTO_EXECUTE:
        _stop_fire()

    if not state["auto"]:
        if decision:
            print(f"[仅观察] {decision['reason']} | 目标=({decision['target_x']:.2f},{decision['target_y']:.2f}) "
                  f"动作={decision['action']} 置信={decision['confidence']:.2f}")
        return

    if not decision or not decision["has_target"]:
        if config.HOLD_FIRE:
            _stop_fire()
        return

    if decision["confidence"] < config.CONFIDENCE_THRESHOLD:
        if config.HOLD_FIRE:
            _stop_fire()
        return

    left, top, w, h = screen_rect
    sx = int(left + decision["target_x"] * w)
    sy = int(top + decision["target_y"] * h)
    action = decision["action"]

    # 移动到目标点并点击（UI 点击：领取 / 确认 / 进入）
    pyautogui.moveTo(sx, sy, duration=0.05)

    if config.HOLD_FIRE and action in ("fire", "click"):
        if not state["firing"]:
            pyautogui.mouseDown(button=config.CLICK_BUTTON)
            state["firing"] = True
    elif action in ("fire", "click"):
        pyautogui.click(button=config.CLICK_BUTTON)
        time.sleep(0.4)   # 等弹窗/界面切换，避免下一帧重复点同一处

    # 处理功能键
    for k in decision["keys"]:
        try:
            pyautogui.press(k)
        except Exception:
            pass

    print(f"[操作] 移动到 ({sx},{sy}) 动作={action} 键={decision['keys']} 置信={decision['confidence']:.2f} | {decision['reason']}")
