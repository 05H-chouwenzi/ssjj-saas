# -*- coding: utf-8 -*-
"""
主循环：截屏 -> 发给本地视觉模型 -> 解析决策 -> 执行键鼠 -> 循环。
一直运行，直到按 QUIT_KEY (默认 F12) 退出。
"""
import os
import time

import config
from capture import grab, save_debug
from vision import ask
from agent import parse_decision, safe_get, USER_PROMPT
from actions import execute, start_hotkeys, state


def main():
    import argparse
    ap = argparse.ArgumentParser(description="生死狙击 AI 操作脚本")
    ap.add_argument("--model-url")
    ap.add_argument("--model")
    ap.add_argument("--window-title")
    ap.add_argument("--auto", dest="auto", action="store_true")
    ap.add_argument("--no-auto", dest="auto", action="store_false")
    ap.set_defaults(auto=None)
    ap.add_argument("--confidence", type=float)
    ap.add_argument("--loop-interval", type=float)
    ap.add_argument("--openai-compat", action="store_true")
    ap.add_argument("--hold-fire", action="store_true")
    ap.add_argument("--prompt", help="脚本列表里选中脚本的提示词（决定找什么按钮）")
    args = ap.parse_args()

    # GUI 壳子通过命令行覆盖配置（只在显式传入时覆盖，保持 config.py 默认值）
    _overrides = {
        "VISION_BASE_URL": args.model_url,
        "VISION_MODEL": args.model,
        "GAME_WINDOW_TITLE": args.window_title,
        "CONFIDENCE_THRESHOLD": args.confidence,
        "LOOP_INTERVAL": args.loop_interval,
        "USE_OPENAI_COMPAT": args.openai_compat,
        "HOLD_FIRE": args.hold_fire,
    }
    for _k, _v in _overrides.items():
        if _v is not None:
            setattr(config, _k, _v)
    if args.auto is not None:
        config.AUTO_EXECUTE = args.auto

    os.makedirs(config.DEBUG_DIR, exist_ok=True)
    start_hotkeys()

    print("=" * 60)
    print("《生死狙击》AI 大厅领奖 / 跑图助手已启动")
    print(f"  模型: {config.VISION_MODEL}  ({config.VISION_BASE_URL})")
    print(f"  自动操作: {'开' if config.AUTO_EXECUTE else '关'}"
          f"（按 {config.TOGGLE_KEY.upper()} 切换）")
    print(f"  暂停: {config.PAUSE_KEY.upper()}   退出: {config.QUIT_KEY.upper()}")
    print(f"  截屏窗口标题: {config.GAME_WINDOW_TITLE or '(未设，用全屏)'}")
    if args.prompt:
        print(f"  当前脚本任务: {args.prompt}")
    print("=" * 60)

    task_prompt = args.prompt or USER_PROMPT
    frame = 0
    while not state["quit"]:
        if state["paused"]:
            time.sleep(0.2)
            continue
        try:
            img, rect = grab()
            text = ask(img, task_prompt)
            dec = safe_get(parse_decision(text))

            if config.SAVE_DEBUG_FRAMES and frame % config.DEBUG_EVERY_N == 0:
                save_debug(img, dec, rect, os.path.join(config.DEBUG_DIR, f"frame_{frame:05d}.png"))

            execute(dec, rect)
        except Exception as e:
            print(f"[错误] 第 {frame} 帧异常: {e}")

        frame += 1
        time.sleep(config.LOOP_INTERVAL)

    print("脚本已退出。")


if __name__ == "__main__":
    main()
