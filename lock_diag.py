# -*- coding: utf-8 -*-
"""锁判定分量诊断：icon 模板分 vs 亮度 std。"""
import numpy as np
from PIL import Image
import gvision as gv

CASES = [
    ('debug_frames/auto_lobby/0912-180949_33572_01_after_roomlist_click.png', [1, 3, 5]),
    ('debug_frames/auto_lobby/0912-165411_38996_01_after_roomlist_click.png', [1, 4, 6, 9, 7, 10]),
]
for path, rows in CASES:
    im = gv.to_ref(Image.open(path).convert('RGB'))
    rgb = np.asarray(im, dtype=np.float32)
    prepped = gv.prep_full(gv.gray_of(im))
    loc = gv.locate_count_col(prepped)
    cx, sc = loc[0], loc[2]
    print('==', path.split('/')[-1], 'count_x=%.0f' % cx)
    for i in rows:
        y = gv.ROW0_Y + (i - 1) * gv.ROW_H + gv._PAD[1]
        icon = gv._max_of(['lock_icon', 'lock_icon2'], prepped,
                          cx + gv.LOCK_CX_OFF * sc, y, search=5)
        std = gv.lock_std(rgb, y, cx, sc)
        print('  row%-2d icon=%.3f std=%.1f' % (i, icon, std))
