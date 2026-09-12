# -*- coding: utf-8 -*-
"""
《生死狙击》AI 大厅领奖 / 跑图助手 - 全局配置
用途：局外自动点击领取任务、领取奖励、签到、确认弹窗等（不涉战斗）。
所有可调参数都在这里，改完保存即可生效。
"""

# ===================== 视觉大模型对接 =====================
# 默认按 Ollama 本地部署（qwen2.5vl:3b 是 Ollama 的模型命名）。
VISION_BASE_URL = "http://localhost:11434/api/chat"
VISION_MODEL = "qwen2.5vl:3b"

# 如果你其实是用 vLLM / llama.cpp 等暴露的 OpenAI 兼容多模态接口，
# 把 USE_OPENAI_COMPAT 改成 True，并填下面的地址（截图会以 base64 图片发过去）。
USE_OPENAI_COMPAT = False
OPENAI_BASE_URL = "http://localhost:8000/v1/chat/completions"
OPENAI_API_KEY = "not-needed"          # 本地部署一般随便填
OPENAI_MODEL = "qwen2.5vl:3b"          # 对应你服务里的模型名

# 推理超时（秒）。3B 视觉模型在 CPU 上可能很慢，按需调大。
VISION_TIMEOUT = 120

# ===================== 截屏 =====================
# 1) 优先按窗口标题锁定游戏窗口；2) 找不到则退回全屏；3) 也可手动指定区域。
GAME_WINDOW_TITLE = "生死狙击"          # 改成你游戏窗口标题里包含的文字
CAPTURE_REGION = None                  # 手动区域 (left, top, width, height)；为 None 时用窗口/全屏

# 截屏前是否把游戏窗口最大化。识别模板按"最大化/全屏"尺寸标定，
# 窗口化时游戏 UI 是固定像素渲染、不随窗口缩放，会导致模板失配，所以默认自动最大化。
ENSURE_MAXIMIZED = True

# 发给模型前把截屏缩放到的最大宽高（降低延迟）。坐标用归一化，缩放不影响定位。
MAX_IMAGE_SIZE = (1280, 720)

# ===================== 决策 / 执行 =====================
AUTO_EXECUTE = True        # 是否真正接管键鼠（False = 只打印模型决策，不操作）
ENABLE_HOTKEYS = True      # 是否启用键盘热键
TOGGLE_KEY = "f8"          # 切换「自动操作」开/关
PAUSE_KEY = "f9"           # 暂停 / 继续主循环
QUIT_KEY = "f12"           # 退出程序

LOOP_INTERVAL = 0.4        # 每轮最小间隔(秒)；实际节奏受推理耗时限制
CLICK_BUTTON = "left"      # 射击用哪个键
HOLD_FIRE = False          # True = 有目标时持续按住左键（连射）；False = 每轮点一下
CONFIDENCE_THRESHOLD = 0.35  # 模型置信度低于此值不操作

# ===================== 调试 =====================
SAVE_DEBUG_FRAMES = True   # 每隔几帧保存一张带标记(红圈+坐标)的截图
DEBUG_EVERY_N = 3          # 每 N 帧存一张
DEBUG_DIR = "debug_frames"
LOG_FILE = "sniper_bot.log"
