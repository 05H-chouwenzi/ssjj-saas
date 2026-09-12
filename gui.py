# -*- coding: utf-8 -*-
"""
《生死狙击》AI 控制台 —— GUI 壳子 (tkinter)
功能：启动 / 停止 / 重启 bot 脚本、实时日志、环境自检、参数设置。
打包：pyinstaller --onefile --noconsole --name SniperAIConsole gui.py
      然后把生成的 dist/SniperAIConsole.exe 放到本目录（与 main.py / .venv 同级）即可双击运行。
"""
import os
import sys
import shutil
import subprocess
import threading
import queue

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

try:
    import requests
except ImportError:
    requests = None

# BASE_DIR：开发态用脚本目录；打包成 exe 后用 exe 所在目录（需与 main.py/.venv 同级）
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULTS = {
    "model_url": "http://localhost:11434/api/chat",
    "model": "qwen2.5vl:3b",
    "window_title": "生死狙击",
    "auto": True,
    "confidence": 0.35,
    "loop_interval": 0.4,
    "openai_compat": False,
    "hold_fire": False,
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("生死狙击 AI 控制台")
        self.geometry("940x680")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.proc = None
        self.log_q = queue.Queue()
        self.python_exe = self.find_python()

        self.build_ui()
        self.after(120, self.pump_log)
        self.log(f"Python 解释器: {self.python_exe or '未找到（需安装 Python 3.10+）'}", "info")

    # ---------------- 工具 ----------------
    @staticmethod
    def find_python():
        venv_py = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")
        if os.path.exists(venv_py):
            return venv_py
        for name in ("python", "python3", "py"):
            p = shutil.which(name)
            if p:
                return p
        return None

    def log(self, msg, level="info"):
        self.log_q.put((level, msg))

    # ---------------- UI ----------------
    def build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=6)
        self.status_var = tk.StringVar(value="● 空闲")
        self.status_label = ttk.Label(top, textvariable=self.status_var, foreground="#888")
        self.status_label.pack(side="left")
        ttk.Button(top, text="检查环境", command=self.check_env).pack(side="right", padx=4)
        ttk.Button(top, text="打开目录", command=self.open_dir).pack(side="right", padx=4)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=4)
        self.settings_frame = ttk.Frame(nb)
        self.console_frame = ttk.Frame(nb)
        nb.add(self.settings_frame, text="设置")
        nb.add(self.console_frame, text="控制台")
        self.build_settings()
        self.build_console()

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=6)
        self.start_btn = ttk.Button(bar, text="▶ 启动", command=self.start)
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = ttk.Button(bar, text="■ 停止", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=4)
        self.restart_btn = ttk.Button(bar, text="↻ 重启", command=self.restart, state="disabled")
        self.restart_btn.pack(side="left", padx=4)
        ttk.Label(bar, text="热键: F8 自动开关 / F9 暂停 / F12 退出").pack(side="right", padx=4)

    def build_settings(self):
        f = self.settings_frame
        pad = dict(padx=8, pady=4)
        ttk.Label(f, text="模型接口地址:").grid(row=0, column=0, sticky="e", **pad)
        self.v_model_url = tk.StringVar(value=DEFAULTS["model_url"])
        ttk.Entry(f, textvariable=self.v_model_url, width=48).grid(row=0, column=1, sticky="w", **pad)

        ttk.Label(f, text="模型名:").grid(row=1, column=0, sticky="e", **pad)
        self.v_model = tk.StringVar(value=DEFAULTS["model"])
        ttk.Entry(f, textvariable=self.v_model, width=48).grid(row=1, column=1, sticky="w", **pad)

        ttk.Label(f, text="游戏窗口标题(含):").grid(row=2, column=0, sticky="e", **pad)
        self.v_win = tk.StringVar(value=DEFAULTS["window_title"])
        ttk.Entry(f, textvariable=self.v_win, width=48).grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(f, text="置信度阈值:").grid(row=3, column=0, sticky="e", **pad)
        self.v_conf = tk.DoubleVar(value=DEFAULTS["confidence"])
        ttk.Spinbox(f, from_=0.0, to=1.0, increment=0.05, textvariable=self.v_conf, width=10).grid(row=3, column=1, sticky="w", **pad)

        ttk.Label(f, text="循环间隔(秒):").grid(row=4, column=0, sticky="e", **pad)
        self.v_int = tk.DoubleVar(value=DEFAULTS["loop_interval"])
        ttk.Spinbox(f, from_=0.05, to=5.0, increment=0.05, textvariable=self.v_int, width=10).grid(row=4, column=1, sticky="w", **pad)

        self.v_auto = tk.BooleanVar(value=DEFAULTS["auto"])
        ttk.Checkbutton(f, text="自动接管键鼠", variable=self.v_auto).grid(row=5, column=1, sticky="w", **pad)
        self.v_openai = tk.BooleanVar(value=DEFAULTS["openai_compat"])
        ttk.Checkbutton(f, text="OpenAI 兼容接口(vLLM/llama.cpp 等)", variable=self.v_openai).grid(row=6, column=1, sticky="w", **pad)
        self.v_hold = tk.BooleanVar(value=DEFAULTS["hold_fire"])
        ttk.Checkbutton(f, text="有目标时持续按住开火(连射)", variable=self.v_hold).grid(row=7, column=1, sticky="w", **pad)

        ttk.Label(f, text="提示: 修改后点『重启』生效；或先停止再启动。").grid(row=8, column=1, sticky="w", **pad)

    def build_console(self):
        f = self.console_frame
        self.console = scrolledtext.ScrolledText(f, wrap="word", font=("Consolas", 10))
        self.console.pack(fill="both", expand=True, padx=6, pady=6)
        self.console.tag_config("info", foreground="#222")
        self.console.tag_config("ok", foreground="#157f3b")
        self.console.tag_config("warn", foreground="#b8860b")
        self.console.tag_config("err", foreground="#c0392b")
        self.console.tag_config("bot", foreground="#1f5fb0")

    # ---------------- 日志泵 ----------------
    def pump_log(self):
        try:
            while True:
                level, msg = self.log_q.get_nowait()
                self.console.insert("end", msg + "\n", level)
                self.console.see("end")
        except queue.Empty:
            pass
        self.after(120, self.pump_log)

    # ---------------- 环境检查 ----------------
    def check_env(self):
        if not self.python_exe:
            self.log("未找到 python，无法运行 bot（请先安装 Python 3.10+ 并加入 PATH，或运行 setup.bat）。", "err")
            return
        if not os.path.exists(os.path.join(BASE_DIR, "main.py")):
            self.log("同目录未找到 main.py，请确认 bot 脚本在一起。", "err")
            return
        self.log("Python 与主程序 OK。", "ok")

        base = self.v_model_url.get()
        host = base.split("/api/")[0] if "/api/" in base else base
        if requests is None:
            self.log("未安装 requests，跳过模型在线检查（可忽略）。", "warn")
            return
        try:
            r = requests.get(host + "/api/tags", timeout=4)
            if r.status_code == 200:
                tags = [m["name"] for m in r.json().get("models", [])]
                model = self.v_model.get()
                if model in tags:
                    self.log(f"Ollama 在线，模型 {model} 已就绪。", "ok")
                else:
                    self.log(f"Ollama 在线，但未找到模型 {model}，请先执行: ollama pull {model}", "warn")
            else:
                self.log(f"Ollama 返回状态码 {r.status_code}。", "warn")
        except Exception as e:
            self.log(f"无法连接 Ollama ({host})：{e}", "err")
            self.log("请确认已执行 ollama serve 且模型已 pull。", "warn")

    def open_dir(self):
        try:
            os.startfile(BASE_DIR)
        except Exception:
            pass

    # ---------------- 启动 / 停止 ----------------
    def build_cmd(self):
        exe = self.python_exe or "python"
        cmd = [exe, "main.py",
               "--model-url", self.v_model_url.get(),
               "--model", self.v_model.get(),
               "--window-title", self.v_win.get(),
               "--confidence", str(self.v_conf.get()),
               "--loop-interval", str(self.v_int.get())]
        cmd.append("--auto" if self.v_auto.get() else "--no-auto")
        if self.v_openai.get():
            cmd.append("--openai-compat")
        if self.v_hold.get():
            cmd.append("--hold-fire")
        return cmd

    def start(self):
        if self.proc and self.proc.poll() is None:
            self.log("已在运行中。", "warn")
            return
        if not self.python_exe:
            messagebox.showerror("错误", "未找到 python，无法启动。请先安装 Python 3.10+ 或运行 setup.bat。")
            return
        cmd = self.build_cmd()
        self.log("启动命令: " + " ".join(cmd), "info")
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.proc = subprocess.Popen(
                cmd, cwd=BASE_DIR,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, creationflags=flags,
            )
        except Exception as e:
            self.log(f"启动失败: {e}", "err")
            return
        self.set_status("运行中", "#157f3b")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.restart_btn.configure(state="normal")
        threading.Thread(target=self.reader, args=(self.proc,), daemon=True).start()

    def reader(self, proc):
        for line in proc.stdout:
            self.log_q.put(("bot", line.rstrip("\n")))
        rc = proc.wait()
        self.log_q.put(("warn", f"bot 进程已结束，返回码 {rc}。"))
        self.after(0, self.on_proc_exit)

    def on_proc_exit(self):
        self.set_status("空闲", "#888")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.restart_btn.configure(state="disabled")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.log("正在停止 bot ...", "info")
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()
        self.set_status("空闲", "#888")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.restart_btn.configure(state="disabled")

    def restart(self):
        self.stop()
        self.after(600, self.start)

    def set_status(self, text, color):
        self.status_var.set("● " + text)
        self.status_label.configure(foreground=color)

    def on_close(self):
        if self.proc and self.proc.poll() is None:
            if messagebox.askyesno("退出", "bot 仍在运行，确定退出并停止它吗？"):
                self.stop()
            else:
                return
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
