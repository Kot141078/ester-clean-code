# -*- coding: utf-8 -*-
"""modules/vision/context_inspector.py - vizualnyy inspector konteksta (heatmap).

Name:
- Sbor koordinat iz zhurnalov: /attention/journal (arrow/box/iplay_step), /triggers (template/ocr s bbox esli est).
- Postroenie teplokarty (PNG base64) poverkh poslednego screenshota.

Faily:
- data/vision/context/last_heatmap.png
- data/vision/context/last_heatmap.json (metadannye vyborki)

MOSTY:
- Yavnyy: (Memory ↔ Vnimanie) pokazyvaem, kuda Ester “smotrela/ukazyvala”.
- Skrytyy #1: (Infoteoriya ↔ Diagnostika) “slepye zony” vidny vizualno.
- Skrytyy #2: (Kibernetika ↔ Uluchshenie) mozhno stavit novye triggery there, where “kholodno”.

ZEMNOY ABZATs:
Chistaya matematika po pikselnoy setke, bez vneshnikh lib: gaussovo razmytie svertkoy.

# c=a+b"""
from __future__ import annotations
import os, io, json, base64, math
from typing import Dict, Any, List
import http.client
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
DIR  = os.path.join(ROOT, "data", "vision", "context")
os.makedirs(DIR, exist_ok=True)
PNG = os.path.join(DIR, "last_heatmap.png")
META = os.path.join(DIR, "last_heatmap.json")

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=15.0)
    conn.request("GET", path); r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _collect(n: int = 200) -> Dict[str, Any]:
    pts: List[Dict[str,int]] = []
    # from attention magazine
    j = _get(f"/attention/journal/list?n={int(max(10,n))}")
    for it in j.get("items", []):
        det = it.get("detail") or {}
        if it.get("event") in ("playlist_step","iplay_step"):
            # grubye tsentry: iz box/strelok mogli byt
            b = det.get("box") or det.get("item",{}).get("box")
            if b and all(k in b for k in ("left","top","width","height")):
                cx = int(b["left"] + b["width"]/2); cy = int(b["top"] + b["height"]/2)
                pts.append({"x": cx, "y": cy})
        if it.get("event")=="overlay_draw":
            p = det.get("point")
            if p and "x" in p and "y" in p: pts.append({"x": int(p["x"]), "y": int(p["y"])})
    # from the list of triggers (if there is a last match box - optional)
    # let's leave it as it is; Most engines don't return boxing - skip it
    return {"pts": pts[-n:]}

def _png_from_screen() -> (bytes, int, int):
    scr = _get("/desktop/rpa/screen")
    if not scr.get("ok"): return b"", 0, 0
    b64 = scr.get("png_b64","")
    raw = base64.b64decode(b64)
    # It’s impossible to simply extract the size without PIL - render a netmap on the same dimension using an additional API?
    # fallback: sprosit razmery metrik
    met = _get("/desktop/metrics/info")
    w = int(met.get("width", 1280)); h = int(met.get("height", 720))
    return raw, w, h

def _draw_heatmap(w: int, h: int, pts: List[Dict[str,int]], radius: int = 40) -> bytes:
    # prostaya “teplota”: nakaplivaem v matritsu, zatem normiruem i nanosim tsvetovuyu shkalu (gray→alpha)
    import struct, zlib
    field = [0.0]*(w*h)
    rad2 = radius*radius
    for p in pts:
        x0, y0 = max(0,min(w-1,int(p.get("x",0)))), max(0,min(h-1,int(p.get("y",0))))
        x1, x2 = max(0, x0-radius), min(w-1, x0+radius)
        y1, y2 = max(0, y0-radius), min(h-1, y0+radius)
        for y in range(y1,y2+1):
            dy = y - y0
            for x in range(x1,x2+1):
                dx = x - x0
                d2 = dx*dx + dy*dy
                if d2 <= rad2:
                    field[y*w+x] += math.exp(-4.0*d2/float(rad2))
    mx = max(field) if field else 1.0
    # RGBA: seryy s alfoy po intensivnosti
    rows = []
    for y in range(h):
        row = bytearray([0])  # filtr None
        for x in range(w):
            v = field[y*w+x]/mx if mx>0 else 0.0
            g = int(255*v)
            a = int(200*v)
            # hue in the red-yellow range without complex maps: g channel - weak
            r = int(255*v)
            b = 0
            row += bytes([r, g//2, b, a])
        rows.append(bytes(row))
    # PNG RGBA
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t+d)&0xffffffff)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    idat = zlib.compress(b"".join(rows), 9)
    png = sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    return png

def build(n: int = 200) -> Dict[str, Any]:
    pts = _collect(n).get("pts", [])
    _, w, h = _png_from_screen()
    if w==0 or h==0:
        return {"ok": False, "error": "no_screen"}
    png = _draw_heatmap(w, h, pts)
    with open(PNG,"wb") as f: f.write(png)
    meta = {"count": len(pts), "w": w, "h": h}
    with open(META,"w",encoding="utf-8") as f: json.dump(meta, f, ensure_ascii=False, indent=2)
    b64 = base64.b64encode(png).decode("ascii")
    return {"ok": True, "png_b64": b64, **meta}