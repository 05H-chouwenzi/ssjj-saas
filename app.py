# -*- coding: utf-8 -*-
"""
生死狙击 AI 助手 - 客户端壳子（仿 WorkBuddy 布局）
技术：pywebview 把 ui/ 下的网页包成一个桌面窗口，后端用 Python 控制 bot。

前端调用入口：window.pywebview.api（下面的 Api 类）。
后端主动推日志：SniperUI.appendLog(line) / setRunning(bool) 等（见 ui/app.js）。
"""
import os
import sys
import json
import re
import time
import threading
import subprocess

SDIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SDIR)

SCRIPTS_FILE = os.path.join(SDIR, "scripts.json")
ACTIVE_FILE = os.path.join(SDIR, "active_script.txt")
LOG_FILE = os.path.join(SDIR, "bot_run.log")

import config  # 纯常量，无第三方依赖

# ---- 依赖缺失时，用图形消息框提示（用 pythonw 无控制台时也能看到）----
def _gui_alert(msg):
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("生死狙击 AI 助手", msg)
        root.destroy()
    except Exception:
        # 实在弹不出框，退回打印（此时多半有控制台）
        print(msg)

try:
    import webview
except ImportError:
    _gui_alert("缺少 pywebview 组件。\n请先在本项目目录双击 setup.bat 安装依赖，再重新打开软件。")
    raise

try:
    import requests  # 仅用于环境自检（已在 requirements 中）
except ImportError:
    requests = None


class Api:
    def __init__(self):
        self.proc = None
        self.running = False
        self.logs = []          # 日志环形缓冲
        self.log_lock = threading.Lock()
        self._total = 0         # 已推送日志总数（前端轮询的游标基准）
        self.last_opts = {}
        self.reader = None
        self._stopped_by_user = False

    # ---------------- 日志 ----------------
    def _push(self, line):
        with self.log_lock:
            self.logs.append(line)
            self._total += 1
            if len(self.logs) > 2000:
                self.logs.pop(0)
        # 注意：此处【不再】调用 webview evaluate_js 主动推日志——
        # 实测/高度怀疑该调用每行触发一次会把助手窗口激活到前台，
        # 导致刚点开的房间列表立刻失焦弹「点击游戏画面继续操作」遮罩。
        # 现改为前端每 0.4s 轮询 get_new_logs 拉增量（页面内调用不激活窗口）。
        # 同时打印到本进程 stdout（从 VSCode 终端运行 app.py 时就能直接看到）
        try:
            print(line, flush=True)
        except Exception:
            pass

    def get_new_logs(self, since=0):
        """前端轮询：返回序号大于 since 的日志行。"""
        with self.log_lock:
            total = self._total
            if since >= total:
                return {"lines": [], "next": total}
            start = max(0, len(self.logs) - (total - since))
            return {"lines": list(self.logs[start:]), "next": total}

    def _reader(self):
        for raw in iter(self.proc.stdout.readline, ''):
            line = raw.rstrip('\n')
            if line:
                self._push(line)
        try:
            self.proc.wait()
        except Exception:
            pass
        rc = self.proc.returncode
        if self._stopped_by_user:
            self._push("■ 已手动停止。")
        elif rc:
            self._push("■ 进程异常退出（返回码 %s）。请检查上方报错；常见原因：缺少依赖、游戏窗口未找到、或 lobby_calib.json 坐标不准。" % rc)
        else:
            self._push("■ 进程已正常结束。")
        self.running = False
        try:
            webview.windows[0].evaluate_js("SniperUI.setRunning(false)")
        except Exception:
            pass

    # ---------------- 控制 ----------------
    def start(self, opts=None):
        if self.proc and self.proc.poll() is None:
            return {"ok": True, "msg": "已在运行"}
        opts = opts or {}
        self.last_opts = opts
        self._stopped_by_user = False
        # 每次启动先清空上次的日志文件（bot_run.log），便于只看本轮。
        # 注意：日志落盘现在由 auto_lobby.py 自身的 _Tee 完成（命令行直跑也能留档），
        # 这里只负责清空 + 写入启动横幅。
        try:
            with open(LOG_FILE, "w", encoding="utf-8") as lf:
                lf.write(time.strftime("[%m-%d %H:%M:%S] ") + "启动\n")
        except Exception:
            pass
        # 绑定：脚本可指定自己的运行程序（program），不指定则跑主程序 main.py。
        # 自定义程序只透传它认识的参数（目前只有 --dry），避免把视觉大模型相关
        # 参数（--model-url / --prompt …）传给 argparse 不认识它们的脚本而报错。
        program = opts.get("program") or "main.py"
        prog_path = os.path.join(SDIR, program)
        if not os.path.exists(prog_path):
            self._push("❌ 找不到程序文件：%s（请检查 scripts.json 里该脚本的 program 字段）" % program)
            return {"ok": False, "msg": "程序文件不存在: " + program}
        self._push("▶ 即将启动：%s%s（工作目录 %s）" % (program, " [dry-run]" if opts.get("dry") else "", SDIR))
        # -u 关闭子进程 stdout 缓冲，确保实时日志立刻推到界面终端
        # （管道默认块缓冲会让人误以为"点开始没反应"）
        cmd = [sys.executable, "-u", program]
        if program != "main.py":
            if opts.get("dry"):
                cmd += ["--dry"]
        else:
            if opts.get("model_url"):
                cmd += ["--model-url", str(opts["model_url"])]
            if opts.get("model"):
                cmd += ["--model", str(opts["model"])]
            if opts.get("window_title"):
                cmd += ["--window-title", str(opts["window_title"])]
            if opts.get("confidence") not in (None, ""):
                cmd += ["--confidence", str(opts["confidence"])]
            if opts.get("loop_interval") not in (None, ""):
                cmd += ["--loop-interval", str(opts["loop_interval"])]
            if opts.get("auto_execute"):
                cmd += ["--auto"]
            else:
                cmd += ["--no-auto"]
            if opts.get("hold_fire"):
                cmd += ["--hold-fire"]
            if opts.get("openai_compat"):
                cmd += ["--openai-compat"]
            if opts.get("prompt"):
                cmd += ["--prompt", str(opts["prompt"])]

        # 强制子进程 stdout/stderr 用 UTF-8，避免 Windows 管道默认 GBK 导致中文乱码
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        flags = 0
        if sys.platform == "win32":
            flags = 0x08000000  # CREATE_NO_WINDOW：避免弹出黑框
        try:
            self.proc = subprocess.Popen(
                cmd, cwd=SDIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                bufsize=1, creationflags=flags, env=env,
            )
        except Exception as e:
            self._push("❌ 启动失败：%s" % e)
            return {"ok": False, "msg": "启动失败: " + str(e)}
        self.running = True
        self.reader = threading.Thread(target=self._reader, daemon=True)
        self.reader.start()
        return {"ok": True, "msg": "已启动"}

    def stop(self):
        self._stopped_by_user = True
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.running = False
        return {"ok": True, "msg": "已停止"}

    def restart(self, opts=None):
        self.stop()
        import time
        time.sleep(0.5)
        return self.start(opts or self.last_opts)

    def status(self):
        return bool(self.running and self.proc and self.proc.poll() is None)

    def get_logs(self):
        with self.log_lock:
            return list(self.logs)

    def quit(self):
        self.stop()
        try:
            webview.windows[0].destroy()
        except Exception:
            pass

    def set_on_top(self, on):
        """窗口置顶开关（on=True 始终置顶 / False 取消）。"""
        try:
            import ctypes
            from ctypes import wintypes
            u32 = ctypes.windll.user32
            # 显式声明参数类型：否则 64 位窗口句柄会被按 32 位截断，报 err=1400 无效句柄
            proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            u32.EnumWindows.argtypes = [proto, wintypes.LPARAM]
            u32.IsWindowVisible.argtypes = [wintypes.HWND]
            u32.IsWindowVisible.restype = wintypes.BOOL
            u32.IsWindow.argtypes = [wintypes.HWND]
            u32.IsWindow.restype = wintypes.BOOL
            u32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            u32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
            u32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND,
                                         ctypes.c_int, ctypes.c_int,
                                         ctypes.c_int, ctypes.c_int, wintypes.UINT]
            u32.SetWindowPos.restype = wintypes.BOOL

            pid = os.getpid()
            found = []

            def cb(hwnd, lparam):
                wpid = wintypes.DWORD(0)
                u32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
                if wpid.value == pid and u32.IsWindowVisible(hwnd):
                    buf = ctypes.create_unicode_buffer(128)
                    u32.GetWindowTextW(hwnd, buf, 128)
                    if "生死狙击" in buf.value:
                        found.append(hwnd)
                return True

            u32.EnumWindows(proto(cb), 0)
            if not found:
                return {"ok": False, "msg": "找不到本软件窗口(枚举为空)"}
            hwnd = found[0]
            if not u32.IsWindow(hwnd):
                return {"ok": False, "msg": "句柄无效 hwnd=%s" % (hwnd,)}
            ok = u32.SetWindowPos(hwnd,
                                  wintypes.HWND(-1 if on else -2),  # TOPMOST / NOTOPMOST
                                  0, 0, 0, 0,
                                  0x0001 | 0x0002 | 0x0010)  # NOSIZE|NOMOVE|NOACTIVATE
            if not ok:
                return {"ok": False,
                        "msg": "SetWindowPos失败 err=%d" % ctypes.GetLastError()}
            return {"ok": True, "title": "ok"}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    # ---------------- 配置 ----------------
    def get_config(self):
        return {
            "model_url": config.VISION_BASE_URL,
            "model": config.VISION_MODEL,
            "window_title": config.GAME_WINDOW_TITLE,
            "confidence": config.CONFIDENCE_THRESHOLD,
            "loop_interval": config.LOOP_INTERVAL,
            "auto_execute": config.AUTO_EXECUTE,
            "hold_fire": config.HOLD_FIRE,
            "openai_compat": config.USE_OPENAI_COMPAT,
        }

    def save_config(self, data):
        try:
            path = os.path.join(SDIR, "config.py")
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()

            def set_var(name, value):
                nonlocal text
                pat = re.compile(r"^(\s*%s\s*=\s*)(.*?)(\s*#.*)?$" % re.escape(name), re.M)
                text = pat.sub(lambda m: m.group(1) + value + "\n", text, count=1)

            def q(s):
                return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'

            if "model_url" in data and data["model_url"] != "":
                set_var("VISION_BASE_URL", q(data["model_url"]))
            if "model" in data and data["model"] != "":
                set_var("VISION_MODEL", q(data["model"]))
            if "window_title" in data and data["window_title"] != "":
                set_var("GAME_WINDOW_TITLE", q(data["window_title"]))
            if "confidence" in data and data["confidence"] != "":
                set_var("CONFIDENCE_THRESHOLD", str(float(data["confidence"])))
            if "loop_interval" in data and data["loop_interval"] != "":
                set_var("LOOP_INTERVAL", str(float(data["loop_interval"])))
            if "auto_execute" in data:
                set_var("AUTO_EXECUTE", "True" if data["auto_execute"] else "False")
            if "hold_fire" in data:
                set_var("HOLD_FIRE", "True" if data["hold_fire"] else "False")
            if "openai_compat" in data:
                set_var("USE_OPENAI_COMPAT", "True" if data["openai_compat"] else "False")

            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            # 重载模块，使 get_config 立即反映新值
            import importlib
            importlib.reload(config)
            return {"ok": True, "msg": "已保存"}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    # ---------------- 脚本列表 ----------------
    def get_scripts(self):
        scripts = []
        if os.path.exists(SCRIPTS_FILE):
            try:
                with open(SCRIPTS_FILE, "r", encoding="utf-8") as f:
                    scripts = json.load(f)
                if not isinstance(scripts, list):
                    scripts = []
            except Exception:
                scripts = []
        active = ""
        if os.path.exists(ACTIVE_FILE):
            try:
                with open(ACTIVE_FILE, "r", encoding="utf-8") as f:
                    active = f.read().strip()
            except Exception:
                active = ""
        return {"scripts": scripts, "active": active}

    def save_scripts(self, scripts):
        try:
            scripts = scripts or []
            with open(SCRIPTS_FILE, "w", encoding="utf-8") as f:
                json.dump(scripts, f, ensure_ascii=False, indent=2)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    def set_active_script(self, sid):
        try:
            with open(ACTIVE_FILE, "w", encoding="utf-8") as f:
                f.write(str(sid or ""))
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    # ---------------- 环境自检 ----------------
    def check_env(self):
        res = {"python": False, "main_py": False, "ollama": False, "model": False}
        # Python
        res["python"] = os.path.exists(sys.executable)
        # 主程序
        res["main_py"] = os.path.exists(os.path.join(SDIR, "main.py"))
        # Ollama 服务
        base = getattr(config, "VISION_BASE_URL", "http://localhost:11434/api/chat")
        tags_url = base.replace("/api/chat", "/api/tags") if "/api/chat" in base else base.rstrip("/") + "/api/tags"
        if requests is None:
            res["ollama"] = False
            return res
        try:
            r = requests.get(tags_url, timeout=3)
            res["ollama"] = r.status_code == 200
            if res["ollama"]:
                models = [m.get("name", "") for m in r.json().get("models", [])]
                res["model"] = getattr(config, "VISION_MODEL", "") in models
        except Exception:
            res["ollama"] = False
        return res


def main():
    api = Api()
    webview.create_window(
        "生死狙击 AI 助手",
        os.path.join(SDIR, "ui", "index.html"),
        js_api=api,
        width=1180, height=720,
        min_size=(420, 300),
    )
    webview.start()


if __name__ == "__main__":
    main()
