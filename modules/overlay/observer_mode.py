# -*- coding: utf-8 -*-
"""
modules/overlay/observer_mode.py — «rezhim nablyudatelya»: myagkie podskazki i teplovaya podsvetka,
bez vypolneniya deystviy (read-only).

Ideya:
- Stroim kombinirovannuyu kartu (context + error) i vozvraschaem poluprozrachnyy RGBA-overley (base64).
- enable/disable — sostoyanie v pamyati. Nikakikh «postoyannykh» khukov.
- Otrisovka podskazok: goryachie zony (oshibki) — malinovaya maska; zony vnimaniya — zhelto-krasnaya.
- Otdelno otdaem «hints» — massiv tekstovykh podskazok (kuda nazhat / chto proverit).

API:
- build_overlay(n_ctx=200, n_err=300) -> {png_b64, hints[]}
- enable(flag:bool) / status()

MOSTY:
- Yavnyy: (Memory ↔ Vnimanie) podskazyvaem, no ne vmeshivaemsya (volya polzovatelya pervichna).
- Skrytyy #1: (Infoteoriya ↔ UX) vizualnoe summirovanie konteksta i oshibok.
- Skrytyy #2: (Kibernetika ↔ Bezopasnost) nulevoy pobochnyy effekt — tolko podsvetka.

ZEMNOY ABZATs:
Offlayn RGBA bez vneshnikh bibliotek. Vneshniy mir vidit tolko PNG base64 i «vkl/vykl».

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List
import http.client, json, base64, math, zlib, struct
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {"enabled": False, "last_overlay": None, "hints": []}

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=12.0)
    conn.request("GET", path); r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _list_points_from_journal(n: int, kinds: List[str]) -> List[Dict[str,int]]:
    j = _get(f"/attention/journal/list?n={int(max(50,n))}")
    pts: List[Dict[str,int]] = []
    for it in j.get("items", []):
        ev = (it.get("event") or "").lower()
        if ev not in kinds: 
            continue
        d = it.get("detail") or {}
        if isinstance(d.get("box"), dict):
            b = d["box"]; pts.append({"x": int(b["left"]+b["width"]/2), "y": int(b["top"]+b["height"]/2)})
        elif isinstance(d.get("point"), dict):
            p = d["point"]; pts.append({"x": int(p.get("x",0)), "y": int(p.get("y",0))})
    return pts

def _paint(w: int, h: int, pts: List[Dict[str,int]], radius: int, color: str) -> List[int]:
    # vozvraschaet akkumulyator znacheniy (0..1) dlya odnogo sloya
    field = [0.0]*(w*h); r2 = radius*radius
    for p in pts:
        x0 = max(0, min(w-1, int(p.get("x",0)))); y0 = max(0, min(h-1, int(p.get("y",0))))
        x1,x2 = max(0,x0-radius), min(w-1,x0+radius)
        y1,y2 = max(0,y0-radius), min(h-1,y0+radius)
        for y in range(y1,y2+1):
            dy = y-y0
            for x in range(x1,x2+1):
                dx = x-x0; d2=dx*dx+dy*dy
                if d2<=r2: field[y*w+x]+=math.exp(-4.0*d2/float(r2))
    mx = max(field) if field else 1.0
    return [v/mx for v in field]

def _compose(w: int, h: int, ctx: List[float], err: List[float]) -> bytes:
    rows=[]
    for y in range(h):
        row = bytearray([0])
        for x in range(w):
            i = y*w+x
            c = ctx[i]; e = err[i]
            # Smeshivanie: kontekst — zhelto-krasnyy, oshibki — malinovo-fioletovyy poverkh
            r = int(255*max(c*0.8, e))           # krasnyy usilen oshibkami
            g = int(200*c)                        # zelenyy — tolko kontekst
            b = int(150*e)                        # siniy — tolko oshibki
            a = int(180*min(1.0, c+e*1.2))        # alfa — kombinirovannaya
            row += bytes([r,g,b,a])
        rows.append(bytes(row))
    def chunk(t,d): return struct.pack(">I",len(d))+t+d+struct.pack(">I",zlib.crc32(t+d)&0xffffffff)
    sig=b"\x89PNG\r\n\x1a\n"; ihdr=struct.pack(">IIBBBBB", w,h,8,6,0,0,0)
    return sig+chunk(b"IHDR",ihdr)+chunk(b"IDAT",zlib.compress(b"".join(rows),9))+chunk(b"IEND",b"")

def build_overlay(n_ctx: int = 200, n_err: int = 300) -> Dict[str, Any]:
    met = _get("/desktop/metrics/info")
    w,h = int(met.get("width",1280)), int(met.get("height",720))
    ctx_pts = _list_points_from_journal(n_ctx, ["overlay_draw","iplay_step","playlist_step"])
    err_pts = _list_points_from_journal(n_err, ["safe_step_fail","ocr_fail","template_fail"])
    ctx_field = _paint(w,h,ctx_pts, radius=42, color="ctx")
    err_field = _paint(w,h,err_pts, radius=50, color="err")
    png = _compose(w,h,ctx_field,err_field)
    b64 = base64.b64encode(png).decode("ascii")
    hints = []
    if err_pts:
        hints.append("Izbegay krasnykh pyaten: tam chasche promakhi raspoznavaniya.")
    if ctx_pts:
        hints.append("Zheltye oblasti — nedavnie tseli vnimaniya; nachni s nikh.")
    _state["last_overlay"] = b64
    _state["hints"] = hints
    return {"ok": True, "png_b64": b64, "hints": hints, "w": w, "h": h}

def enable(flag: bool) -> Dict[str, Any]:
    _state["enabled"] = bool(flag)
    return status()

def status() -> Dict[str, Any]:
    return {"ok": True, "enabled": bool(_state.get("enabled")), "has_overlay": _state.get("last_overlay") is not None, "hints": list(_state.get("hints", []))}