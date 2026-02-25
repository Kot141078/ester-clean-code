# -*- coding: utf-8 -*-
"""modules/vision/stream_overlay.py - nalozhenie podskazok na kadry VNC/noVNC.

Ideaya:
- Berem vneshniy PNG-kadr (for example, poluchennyy iz VNC-snimka) i risuem strelki/ramki/tekst.
- Khranim sessiyu (id -> poslednie parametry) v pamyati dlya udobstva.

API level module:
- overlay_arrow(png_b64, p_from, p_to, label) -> png_b64
- overlay_box(png_b64, box, label) -> png_b64

Primechanie:
- Modul ne podklyuchaetsya k VNC sam; on tolko risuet poverkh kadra. Kadr mozhet priyti iz lokalnogo grabbera
  ili cherez vspomogatelnuyu ruchku, esli ty delaesh skrin VNC otdelno.

MOSTY:
- Yavnyy: (Video ↔ Obyasnenie) pokazyvaem poverkh potoka “kuda smotret/zhat.”
- Skrytyy #1: (Infoteoriya ↔ UX) minimum grafiki — maximum smysla.
- Skrytyy #2: (Kibernetika ↔ Volya) ta zhe “ruka-na-ruke”, no v videostreame.

ZEMNOY ABZATs:
Simple PIL-risunok poverkh lyubogo PNG-kadra. Sovmestimo s noVNC: otdavay kadr cherez REST, poluchay obratno s overlay.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, Tuple
import base64, io
from PIL import Image, ImageDraw
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _decode(b64: str) -> Image.Image:
    data = base64.b64decode(b64)
    return Image.open(io.BytesIO(data)).convert("RGBA")

def _encode(img: Image.Image) -> str:
    bio = io.BytesIO(); img.save(bio, format="PNG")
    return base64.b64encode(bio.getvalue()).decode("ascii")

def overlay_arrow(png_b64: str, p_from: Tuple[int,int], p_to: Tuple[int,int], label: str|None=None) -> str:
    im = _decode(png_b64)
    dr = ImageDraw.Draw(im, "RGBA")
    dr.line((p_from[0], p_from[1], p_to[0], p_to[1]), fill=(64,128,255,255), width=5)
    ax, ay = p_to
    dr.polygon([(ax, ay), (ax-12, ay-6), (ax-12, ay+6)], fill=(64,128,255,255))
    if label:
        lx, ly = p_to[0]+8, p_to[1]-18
        dr.rectangle((lx, ly, lx+max(80, 12*len(label)), ly+22), fill=(64,128,255,200))
        dr.text((lx+6, ly+3), label, fill=(255,255,255,255))
    return _encode(im)

def overlay_box(png_b64: str, box: Dict[str,int], label: str|None=None) -> str:
    im = _decode(png_b64)
    dr = ImageDraw.Draw(im, "RGBA")
    x, y, w, h = box["left"], box["top"], box["width"], box["height"]
    dr.rectangle((x, y, x+w, y+h), outline=(255,64,64,255), width=4)
    if label:
        dr.rectangle((x, y-24, x+max(80, 12*len(label)), y), fill=(255,64,64,200))
        dr.text((x+6, y-20), label, fill=(255,255,255,255))
    return _encode(im)