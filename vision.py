# -*- coding: utf-8 -*-
"""
视觉大模型调用：把截图(base64 PNG) + 提示词发给本地 qwen2.5vl:3b，拿回文本。
默认走 Ollama /api/chat；USE_OPENAI_COMPAT=True 时走 OpenAI 兼容 /chat/completions。
"""
import base64
import io

import requests

import config

SYSTEM_PROMPT = (
    "你是一个《生死狙击》游戏的【局外界面自动化助手】，专门帮玩家在大厅/活动页自动领取任务与奖励、"
    "跑图领奖，绝不做任何战斗或瞄准。\n"
    "你会看到游戏大厅、任务页或活动页的实时截图。你的任务是：找出当前屏幕上【所有可以点击领取/确认】的"
    "按钮或入口，并选择【最该点的那一个】，给出它的中心坐标。\n"
    "优先点击这些字样相关的按钮：领取任务、领取奖励、签到、每日奖励、一键领取、确认、确定、领取、"
    "活动奖励、福利、邮件领取、开始任务、进入。如果刚点了领取弹出确认框，就点 确认/确定；弹窗关闭点 关闭/X。\n"
    "坐标规则：target_x、target_y 为归一化坐标，取值 0~1，(0,0)=图片左上角，(1,1)=右下角，"
    "target_x 向右增大、target_y 向下增大。脚本会把鼠标移到该点并点击。\n"
    "只允许输出一个 JSON 对象，不要解释性文字、不要 markdown 代码块。字段：\n"
    "  has_target: 布尔，当前是否有可点击的领取/确认/进入按钮\n"
    "  target_x: 0~1，该按钮中心的水平位置\n"
    "  target_y: 0~1，该按钮中心的垂直位置\n"
    "  action: \"click\"=点击该位置(领取/确认/进入), \"none\"=当前没有可点的领取项(等待或翻页)\n"
    "  keys: 字符串数组，极少用到，一般留空 []\n"
    "  confidence: 0~1，你对判断的把握\n"
    "  reason: 简短中文说明你看到并准备点什么\n"
    "没有可点项时：{\"has_target\":false,\"action\":\"none\",\"keys\":[],\"confidence\":0.0,\"reason\":\"当前无可领取项\"}"
)


def _image_to_base64(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def ask(img, user_prompt, system_prompt=None):
    """发一张图 + 提示词，返回模型原始文本。

    system_prompt 为 None 时用默认 SYSTEM_PROMPT；
    脚本列表里每个脚本可传入自己的提示词，决定模型找什么按钮。
    """
    b64 = _image_to_base64(img)
    sys_prompt = system_prompt or SYSTEM_PROMPT

    if config.USE_OPENAI_COMPAT:
        payload = {
            "model": config.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                },
            ],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {config.OPENAI_API_KEY}"}
        r = requests.post(config.OPENAI_BASE_URL, json=payload, headers=headers, timeout=config.VISION_TIMEOUT)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    # 默认 Ollama
    payload = {
        "model": config.VISION_MODEL,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2},
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt, "images": [b64]},
        ],
    }
    r = requests.post(config.VISION_BASE_URL, json=payload, timeout=config.VISION_TIMEOUT)
    r.raise_for_status()
    return r.json()["message"]["content"]


if __name__ == "__main__":
    from capture import grab
    im, _ = grab()
    out = ask(im, "画面里有没有可领取/可确认的任务或奖励按钮？按规则输出 JSON。")
    print("模型返回：", out)
