# -*- coding: utf-8 -*-
"""
modules/vision/template_match.py — sopostavlenie shablona (template matching) po skrinshotu.

Vkhod: base64 PNG ekrana i shablona, porog [0..1], metod: 'cv2' (esli dostupen) ili 'naive' (NumPy).
Vykhod: {ok, box:{left, top, width, height}, center:{x,y}, score}

MOSTY:
- Yavnyy: (Zrenie ↔ Deystvie) nakhodim element po obraztsu i daem koordinaty dlya klika.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) determinirovannyy oflayn-algoritm, bez setey.
- Skrytyy #2: (Kibernetika ↔ Volya) obraz→koordinata→klik — pryamaya petlya upravleniya.

ZEMNOY ABZATs:
Rabotaet oflayn. Esli OpenCV net — vklyuchaetsya prostaya korrelyatsiya (medlennee, no bez vneshnikh zavisimostey).
Dlya stabilnosti luchshe ispolzovat «chetkie» malenkie shablony (logotipy/ikonki/zagolovki).

# c=a+b
"""
from __future__ import annotations
import base64, io
from typing import Dict, Any, Tuple
import numpy as np

try:
    import cv2  # type: ignore
except Exception:
    cv2 = None  # fallback

from PIL import Image
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _b64png_to_gray(b64png: str) -> np.ndarray:
    data = base64.b64decode(b64png)
    im = Image.open(io.BytesIO(data)).convert("L")
    return np.array(im, dtype=np.uint8)

def _cv2_match(screen: np.ndarray, templ: np.ndarray) -> Tuple[float, Tuple[int,int]]:
    res = cv2.matchTemplate(screen, templ, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    return float(max_val), (int(max_loc[0]), int(max_loc[1]))

def _naive_match(screen: np.ndarray, templ: np.ndarray) -> Tuple[float, Tuple[int,int]]:
    # Normirovannaya korrelyatsiya (medlennaya, no bez opencv)
    H, W = screen.shape
    h, w = templ.shape
    if h>H or w>W:
        return 0.0, (0,0)
    t = templ.astype(np.float32)
    t = (t - t.mean()) / (t.std() + 1e-6)
    best = -1.0
    best_xy = (0,0)
    # shag 4 piks po umolchaniyu dlya skorosti (mozhno umenshit)
    step = 2 if (H*W) < 2_500_000 else 4
    for y in range(0, H-h+1, step):
        win = screen[y:y+h, :]
        for x in range(0, W-w+1, step):
            s = win[:, x:x+w].astype(np.float32)
            s = (s - s.mean()) / (s.std() + 1e-6)
            score = float((s*t).mean())
            if score > best:
                best = score; best_xy = (x,y)
    return best, best_xy

def find(b64_screen: str, b64_template: str, threshold: float = 0.78) -> Dict[str, Any]:
    scr = _b64png_to_gray(b64_screen)
    tpl = _b64png_to_gray(b64_template)
    if scr.shape[0] < tpl.shape[0] or scr.shape[1] < tpl.shape[1]:
        return {"ok": False, "error": "template_bigger_than_screen"}
    if cv2 is not None:
        score, (x,y) = _cv2_match(scr, tpl)
    else:
        score, (x,y) = _naive_match(scr, tpl)
    w, h = tpl.shape[1], tpl.shape[0]
    ok = bool(score >= threshold)
    return {
        "ok": ok,
        "score": round(float(score), 4),
        "box": {"left": int(x), "top": int(y), "width": int(w), "height": int(h)},
        "center": {"x": int(x + w//2), "y": int(y + h//2)}
    }