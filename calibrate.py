# -*- coding: utf-8 -*-
"""
calibrate.py —— 坐标取点工具（回车记录法，避免游戏吞掉 F7 热键）

用法：
    1. 把游戏开到大厅（窗口模式，保持可见）
    2. 运行： python calibrate.py
    3. 每个提示出现后，把鼠标移到对应按钮上，回到本终端按【回车】记录
       （终端需保持焦点；鼠标位置是全局屏幕坐标，游戏在屏幕上也行）
    4. 不需要的点：直接按回车（留空）即跳过，不覆盖原值
    5. 全部取完自动保存 lobby_calib.json

说明：内部会把"鼠标的屏幕坐标"按游戏窗口矩形换算成参考分辨率(1920x1077)坐标，
     因此以后换分辨率/窗口大小也不用重新取点（只要布局比例不变）。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 声明 DPI 感知：让鼠标坐标(pyautogui)与截图(capture)统一用物理像素。
import win_dpi  # noqa: F401

CALIB_PATH = os.path.join(HERE, "lobby_calib.json")

STEPS = [
    ("map_node_desert2", "地图上的「沙漠奇兵2」节点"),
    ("btn_roomlist", "「房间列表」按钮"),
    ("btn_chat", "右侧的「聊天」按钮"),
    ("btn_ok", "任务完成界面上的「确定」按钮（可把游戏切到那个界面再取；不想取直接回车跳过）"),
    ("btn_quit", "任务完成界面上的「退出」按钮（同上，不想取直接回车跳过）"),
]


def main():
    import pyautogui
    try:
        with open(CALIB_PATH, "r", encoding="utf-8") as f:
            calib = json.load(f)
    except Exception:
        calib = {}

    print("=" * 64)
    print("坐标取点工具（回车记录法）")
    print("  把鼠标移到目标上，回到本终端按【回车】记录。")
    print("  游戏请保持在大厅窗口状态（脚本按游戏窗口换算坐标）。")
    print("  不需要的点：直接按回车（留空），则不覆盖原值。")
    print("=" * 64)

    # 先尝试取一次游戏窗口矩形（用于屏幕坐标 -> 参考坐标换算）
    try:
        from capture import grab
        _img, rect = grab()
    except Exception as e:
        print("[警告] 获取游戏窗口失败，将按整屏 1920x1077 换算:", e)
        rect = (0, 0, 1920, 1077)
    rx, ry, rw, rh = rect
    print("游戏画面矩形 =", rect)

    grabbed = {}
    for name, desc in STEPS:
        ans = input("把鼠标移到【%s】，就位后按回车（直接回车=跳过）：" % desc)
        if ans.strip() == "":
            print("  （跳过 %s，保留 lobby_calib.json 原值）" % name)
            continue
        sx, sy = pyautogui.position()
        x = (sx - rx) / rw * 1920.0
        y = (sy - ry) / rh * 1077.0
        grabbed[name] = [int(round(x)), int(round(y))]
        print("  已记录 %-18s = [%d, %d]   (屏幕坐标 %s)" % (name, x, y, (sx, sy)))

    if grabbed:
        calib.update(grabbed)
        with open(CALIB_PATH, "w", encoding="utf-8") as f:
            json.dump(calib, f, ensure_ascii=False, indent=2)
        print("\n已保存 %d 个点到 %s" % (len(grabbed), CALIB_PATH))
        print(json.dumps(grabbed, ensure_ascii=False, indent=2))
    else:
        print("\n没有记录任何点，未修改文件。")


if __name__ == "__main__":
    main()
