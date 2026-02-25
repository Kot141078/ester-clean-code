# -*- coding: utf-8 -*-
"""modules/vision/error_heatmap.py - teplokarta oshibok raspoznavaniya.

Sources:
- /attention/journal/list — sobytiya: 'safe_step_fail', 'ocr_fail', 'template_fail'
  (ozhidayutsya polya detail.box {left,top,width,height} or detail.point {x,y} - esli net, sobytie propuskaem).
- /desktop/metrics/info — razmery ekrana dlya rendera.

Vykhod:
- data/vision/error/heatmap.png (base64 on request)
- data/vision/error/heatmap.json (statistika)

MOSTY:
- Yavnyy: (Memory ↔ Diagnostika) kontsentratsiya promakhov na ekrane.
- Skrytyy #1: (Infoteoriya ↔ Uluchshenie) dannye dlya tyuninga triggerov (nizhe — mass_tuner).
- Skrytyy #2: (Kibernetika ↔ Kontrol) help razmeschat podskazki/kursor vne “krasnykh zon”.

ZEMNOY ABZATs:
Chistyy offlayn-render RGBA (kak v kontekstnoy karte), tolko istochniki - oshibki.

# c=a+b"""
from __future__ import annotations
import os, json, base64, math, zlib, struct
from typing import Dict, Any, List
import http.client
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
DIR  = os.path.join(ROOT, "data", "vision", "error")
os.makedirs(DIR, exist_ok=True)
PNG = os.path.join(DIR, "heatmap.png")
META= os.path.join(DIR, "heatmap.json")

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=15.0)
    conn.request("GET", path); r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _collect(n: int = 300) -> List[Dict[str,int]]:
    pts: List[Dict[str,int]] = []
    j = _get(f"/attention/journal/list?n={int(max(20,n))}")
    for it in (j.get("items") or []):
        ev = (it.get("event") or "").lower()
        if ev not in ("safe_step_fail","ocr_fail","template_fail"): 
            continue
        d = it.get("detail") or {}
        if isinstance(d.get("box"), dict):
            b = d["box"]
            if all(k in b for k in ("left","top","width","height")):
                pts.append({"x": int(b["left"] + b["width"]/2), "y": int(b["top"] + b["height"]/2)})
        elif isinstance(d.get("point"), dict):
            p = d["point"]; pts.append({"x": int(p.get("x",0)), "y": int(p.get("y",0))})
    return pts[-n:]

def _png(w: int, h: int, pts: List[Dict[str,int]], radius: int = 42) -> bytes:
    field = [0.0]*(w*h); r2 = radius*radius
    for p in pts:
        x0 = max(0, min(w-1, int(p.get("x",0)))); y0 = max(0, min(h-1, int(p.get("y",0))))
        x1,x2 = max(0,x0-radius), min(w-1,x0+radius)
        y1,y2 = max(0,y0-radius), min(h-1,y0+radius)
        for y in range(y1,y2+1):
            dy = y-y0
            for x in range(x1,x2+1):
                dx = x-x0; d2 = dx*dx+dy*dy
                if d2<=r2: field[y*w+x]+=math.exp(-4.0*d2/float(r2))
    mx = max(field) if field else 1.0
    rows=[]
    for y in range(h):
        row=bytearray([0])
        for x in range(w):
            v = field[y*w+x]/mx if mx>0 else 0.0
            # red-violet color for errors
            r = int(255*v); g = int(50*v); b = int(120*v); a = int(220*v)
            row += bytes([r,g,b,a])
        rows.append(bytes(row))
    def chunk(t,d): return struct.pack(">I",len(d))+t+d+struct.pack(">I",zlib.crc32(t+d)&0xffffffff)
    sig=b"\x89PNG\r\n\x1a\n"
    ihdr=struct.pack(">IIBBBBB", w,h,8,6,0,0,0)
    return sig+chunk(b"IHDR",ihdr)+chunk(b"IDAT",zlib.compress(b"".join(rows),9))+chunk(b"IEND",b"")

def build(n: int = 300) -> Dict[str, Any]:
    met = _get("/desktop/metrics/info")
    w, h = int(met.get("width",1280)), int(met.get("height",720))
    pts  = _collect(n)
    pngb = _png(w,h,pts)
    with open(PNG,"wb") as f: f.write(pngb)
    with open(META,"w",encoding="utf-8") as f: json.dump({"count":len(pts),"w":w,"h":h}, f, ensure_ascii=False, indent=2)
    return {"ok": True, "count": len(pts), "w": w, "h": h, "png_b64": base64.b64encode(pngb).decode("ascii")}