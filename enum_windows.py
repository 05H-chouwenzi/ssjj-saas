# -*- coding: utf-8 -*-
import pygetwindow as gw

ws = gw.getAllWindows()
print("=== 标题含 生死狙击/4399 ===")
for w in ws:
    t = w.title or ""
    if ("生死狙击" in t) or ("4399" in t):
        print(repr(t), "rect=", (w.left, w.top, w.width, w.height),
              "visible=", w.visible, "min=", getattr(w, "isMinimized", None))
print("=== 所有可见且较大的窗口 ===")
for w in ws:
    if w.visible and w.width > 300 and w.height > 200:
        print(repr((w.title or "")[:50]), (w.left, w.top, w.width, w.height))
