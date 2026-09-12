# -*- coding: utf-8 -*-
"""
决策解析：把模型返回的（可能带噪声的）文本稳健地解析成 dict。
同时提供拼装每帧 user 提示词的函数。
"""
import json
import re

USER_PROMPT = (
    "分析当前《生死狙击》大厅/活动界面，找出可领取的任务、奖励、签到、确认弹窗等按钮。\n"
    "按系统设定的 JSON 格式输出：has_target / target_x / target_y / action / keys / confidence / reason。\n"
    "target_x、target_y 为归一化坐标(0,0=左上角)。没有可点项时 has_target=false、action=none。\n"
    "找到可领取/可确认按钮时 action 用 \"click\"，并给出按钮中心坐标；需要进入某个页/模式也用 click。"
)


def parse_decision(text):
    """返回 dict 或 None。对模型输出做多重容错。"""
    if not text:
        return None
    t = text.strip()
    # 去掉可能的 ```json ``` 代码块
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = t.rstrip("`").strip()
    # 直接整体解析
    try:
        return json.loads(t)
    except Exception:
        pass
    # 退而求其次：抓取第一个 {...}（贪婪，含嵌套）
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def safe_get(decision):
    """把模型决策规整成执行器需要的字段，缺字段给默认值。"""
    if not isinstance(decision, dict):
        return None
    return {
        "has_target": bool(decision.get("has_target", False)),
        "target_x": float(decision.get("target_x", 0.5)),
        "target_y": float(decision.get("target_y", 0.5)),
        "action": str(decision.get("action", "none")),
        "keys": list(decision.get("keys", []) or []),
        "confidence": float(decision.get("confidence", 0.0)),
        "reason": str(decision.get("reason", "")),
    }


if __name__ == "__main__":
    samples = [
        '{"has_target": true, "target_x": 0.52, "target_y": 0.47, "action": "fire", "keys": [], "confidence": 0.8, "reason": "中央敌人"}',
        '```json\n{"has_target":false,"action":"none","keys":[],"confidence":0.0,"reason":"无敌人"}\n```',
        '我觉得有敌人 {"has_target": true, "target_x": 0.3, "target_y": 0.6, "action": "fire", "keys": ["w"], "confidence": 0.6, "reason": "左侧"}',
    ]
    for s in samples:
        print(parse_decision(s))
