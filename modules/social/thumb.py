# -*- coding: utf-8 -*-
"""modules/social/thumb.py - generatsiya izobrazheniy prevyu (PNG pri nalichii Pillow, inache SVG).

Mosty:
- Yavnyy: (Titul ↔ Kartinka) poluchaem zagruzochnuyu oblozhku s chitaemym zagolovkom.
- Skrytyy #1: (Inzheneriya ↔ Degradatsiya) esli net Pillow — sozdaem SVG, prigodnyy k konvertatsii.
- Skrytyy #2: (Studiya ↔ Sotskit) napryamuyu ispolzuetsya kit.build.

Zemnoy abzats:
Kak bystro narisovat oblozhku markerom na liste - tolko fayl, kotoryy mozhno zagruzit.

# c=a+b"""
from __future__ import annotations
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def make_thumbnail(title: str, dst_dir: str, size: str|None=None)->str:
    os.makedirs(dst_dir, exist_ok=True)
    size=size or (os.getenv("THUMB_DEFAULT_SIZE","1280x720"))
    try:
        w,h = [int(x) for x in size.lower().split("x")]
    except Exception:
        w,h=1280,720
    # Attempt to PNG via Pilov
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
        img=Image.new("RGB",(w,h),(17,24,39))
        d=ImageDraw.Draw(img)
        try:
            fnt=ImageFont.truetype("arial.ttf", int(h*0.08))
        except Exception:
            fnt=ImageFont.load_default()
        text=title[:60]
        tw,th=d.textsize(text, font=fnt)
        d.rectangle([(40, h//2 - th - 20),(w-40, h//2 + th + 40)], fill=(12,18,28))
        d.text(( (w-tw)//2, (h-th)//2 ), text, font=fnt, fill=(235,242,255))
        path=os.path.join(dst_dir,"thumb.png")
        img.save(path, format="PNG")
        return path
    except Exception:
        # SVG follbek
        path=os.path.join(dst_dir,"thumb.svg")
        tt=title.replace("&","&amp;").replace("<","&lt;")
        open(path,"w",encoding="utf-8").write(f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}'><rect width='100%' height='100%' fill='#111827'/><text x='50' y='{h//2}' fill='#e5e7eb' font-size='{int(h*0.08)}' font-family='Arial'>{tt}</text></svg>")
        return path
# c=a+b