# -*- coding: utf-8 -*-
"""modules/replay/flight_review.py - “razbor poletov”: analiz i repley s podsvetkoy latentnosti.

Vkhod (events):
[
  {"ts": 1700000000.123, "kind":"input","desc":"CTRL+S"},
  {"ts": 1700000000.456, "kind":"ocr_ok","desc":"Save"},
  {"ts": 1700000001.000, "kind":"template_fail","box":{...}}
]

Funktsii:
- analyze(events) -> agregaty: lat_ms mezhdu input→oklik (ocr_ok/template_ok), raspredelenie, “krasnye” khvosty, korotkiy otchet.
- overlay(events) -> base64-PNG podsvetka place s plotnym “fail” (ispolzuem prostuyu teplovuyu masku).
- replay(events, speed=1.0) -> “sukhoy” spisok shagov vosproizvedeniya (ts_rel, hint), bez pobochnykh effektov.

MOSTY:
- Yavnyy: (Infoteoriya ↔ Kachestvo) schitaem latentnost i pokazyvaem problemnye zony.
- Skrytyy #1: (Kibernetika ↔ Obuchenie) “repley” daet material dlya instruktora.
- Skrytyy #2: (Inzheneriya ↔ Videnie) overlay ispolzuet tot zhe mekhanizm heatmap, no iz lokalnogo buffera.

ZEMNOY ABZATs:
Nikakikh vneshnikh zavisimostey; tolko arifmetika i lokalnyy PNG-render.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import math, base64, zlib, struct
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _pair_lat(events: List[Dict[str, Any]]) -> List[float]:
    lat = []
    last_inp = None
    for e in events:
        k = (e.get("kind") or "").lower()
        if k in ("input","hotkey","click"):
            last_inp = float(e.get("ts",0.0))
        elif k in ("ocr_ok","template_ok"):
            if last_inp is not None:
                lat.append(max(0.0, float(e.get("ts",0.0))-last_inp)*1000.0)
                last_inp = None
    return lat

def _stats(arr: List[float]) -> Dict[str, Any]:
    if not arr: return {"count":0,"p50":0,"p90":0,"p99":0,"avg":0}
    s = sorted(arr); n=len(s)
    def q(p): 
        i = min(n-1, max(0, int(round(p*(n-1)))))
        return s[i]
    return {"count":n,"p50":round(q(0.50),1),"p90":round(q(0.90),1),"p99":round(q(0.99),1),"avg":round(sum(s)/n,1)}

def analyze(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    lat = _pair_lat(events)
    bad = [x for x in lat if x>800.0]
    return {"ok": True, "lat_ms": lat, "stats": _stats(lat), "bad_segments": len(bad)}

def _accum(w: int, h: int, pts: List[Tuple[int,int]], r: int) -> List[float]:
    field=[0.0]*(w*h); r2=r*r
    for (x0,y0) in pts:
        x1,x2=max(0,x0-r),min(w-1,x0+r)
        y1,y2=max(0,y0-r),min(h-1,y0+r)
        for y in range(y1,y2+1):
            dy=y-y0
            for x in range(x1,x2+1):
                dx=x-x0; d2=dx*dx+dy*dy
                if d2<=r2: field[y*w+x]+=math.exp(-4.0*d2/float(r2))
    mx=max(field) if field else 1.0
    return [v/mx for v in field]

def overlay(events: List[Dict[str, Any]], w: int = 1280, h: int = 720) -> Dict[str, Any]:
    pts=[]
    for e in events:
        if (e.get("kind") or "").lower() in ("template_fail","ocr_fail","safe_step_fail"):
            d=e.get("box") or e.get("point") or {}
            if "left" in d and "width" in d and "top" in d and "height" in d:
                pts.append((int(d["left"]+d["width"]/2), int(d["top"]+d["height"]/2)))
            elif "x" in d and "y" in d:
                pts.append((int(d["x"]), int(d["y"])))
    acc=_accum(w,h,pts,46)
    rows=[]
    for y in range(h):
        row=bytearray([0])
        for x in range(w):
            v=acc[y*w+x]
            r=int(255*v); g=int(60*v); b=int(140*v); a=int(200*v)
            row+=bytes([r,g,b,a])
        rows.append(bytes(row))
    def chunk(t,d): return struct.pack(">I",len(d))+t+d+struct.pack(">I",zlib.crc32(t+d)&0xffffffff)
    sig=b"\x89PNG\r\n\x1a\n"; ihdr=struct.pack(">IIBBBBB", w,h,8,6,0,0,0)
    png=sig+chunk(b"IHDR",ihdr)+chunk(b"IDAT",zlib.compress(b"".join(rows),9))+chunk(b"IEND",b"")
    return {"ok": True, "png_b64": base64.b64encode(png).decode("ascii")}

def replay(events: List[Dict[str, Any]], speed: float = 1.0) -> Dict[str, Any]:
    if not events: return {"ok": True, "steps": []}
    t0=float(events[0].get("ts",0.0))
    out=[]
    for e in events:
        ts_rel=max(0.0,(float(e.get("ts",0.0))-t0))/max(0.1,float(speed))
        out.append({"ts_rel": round(ts_rel,3), "hint": f"{e.get('kind','')} — {e.get('desc','')}"})
    return {"ok": True, "steps": out}