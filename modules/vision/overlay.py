# -*- coding: utf-8 -*-
"""modules/vision/overlay.py - otrisovka podskazok poverkh screenshota.

Funktsii:
- draw_box_label(screen_b64, box, label) -> overlay_b64
- draw_arrow(screen_b64, p_from, p_to, label?) -> overlay_b64

MOSTY:
- Yavnyy: (Zrenie ↔ Obyasnenie) chto/kuda nazhat — vidno na skrine.
- Skrytyy #1: (Infoteoriya ↔ UX) minimalnaya grafika → maximum yasnosti.
- Skrytyy #2: (Anatomiya ↔ Psikhologiya) strelka/ramka kak “nastavnik u plecha”.

ZEMNOY ABZATs:
Obychnyy PIL, lokalno, bez vneshnikh zavisimostey. Legkoe i bystroe nalozhenie.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, Tuple
import base64, io
from PIL import Image, ImageDraw, ImageFont
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _png_to_img(b64png: str) -> Image.Image:
    data = base64.b64decode(b64png)
    return Image.open(io.BytesIO(data)).convert("RGBA")

def _img_to_b64(img: Image.Image) -> str:
    out = io.BytesIO(); img.save(out, format="PNG"); return base64.b64encode(out.getvalue()).decode("ascii")

def draw_box_label(screen_b64: str, box: Dict[str,int], label: str) -> str:
    im = _png_to_img(screen_b64)
    dr = ImageDraw.Draw(im, "RGBA")
    x, y, w, h = box["left"], box["top"], box["width"], box["height"]
    dr.rectangle((x, y, x+w, y+h), outline=(255, 64, 64, 255), width=4)
    dr.rectangle((x, y-24, x+max(80, 12*len(label)), y), fill=(255,64,64,200))
    dr.text((x+6, y-20), label, fill=(255,255,255,255))
    return _img_to_b64(im)

def draw_arrow(screen_b64: str, p_from: Tuple[int,int], p_to: Tuple[int,int], label: str|None=None) -> str:
    im = _png_to_img(screen_b64)
    dr = ImageDraw.Draw(im, "RGBA")
    dr.line((p_from[0], p_from[1], p_to[0], p_to[1]), fill=(64,128,255,255), width=5)
    # strelka
    ax, ay = p_to
    dr.polygon([(ax, ay), (ax-12, ay-6), (ax-12, ay+6)], fill=(64,128,255,255))
    if label:
        lx, ly = p_to[0]+8, p_to[1]-18
        dr.rectangle((lx, ly, lx+max(80, 12*len(label)), ly+22), fill=(64,128,255,200))
        dr.text((lx+6, ly+3), label, fill=(255,255,255,255))
    return _img_to_b64(im)