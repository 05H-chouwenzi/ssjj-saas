# -*- coding: utf-8 -*-
"""
环境自检：确认本地 Ollama 在运行、且 qwen2.5vl:3b 已拉取。
运行：python check_env.py
"""
import sys

import requests

BASE = "http://localhost:11434"
TARGET = "qwen2.5vl:3b"


def main():
    try:
        r = requests.get(BASE + "/api/tags", timeout=5)
        r.raise_for_status()
    except Exception as e:
        print("无法连接 Ollama：", e)
        print("请先安装 Ollama，并运行：ollama serve")
        sys.exit(1)

    models = [m["name"] for m in r.json().get("models", [])]
    print("Ollama 在线。已安装模型：")
    for m in models:
        print("  -", m)

    if any(TARGET in m for m in models):
        print(f"\n找到 {TARGET}  ✓  可以运行 python main.py")
    else:
        print(f"\n未找到 {TARGET}，请先执行：ollama pull {TARGET}")
        print("（首次拉取较大，请耐心等待；如需 GPU 加速确保已装 CUDA 版 Ollama）")


if __name__ == "__main__":
    main()
