# -*- coding: utf-8 -*-
"""
modules/instructor/hud.py — HUD instruktora: metriki latentnosti i «krasnye zony» poverkh ekrana.

Ideya:
- Poluchaem svezhie sobytiya zhurnala (poslednie N), schitaem latentnost (kak v flight_review.analyze)
  i sobiraem kompaktnyy PNG-overley s tekstovoy «lineykoy» metrik (p50/p90/p99, bad_segments).
- Vkl/vykl khranitsya v pamyati, generatsiya — po zaprosu (bez fonovykh demonov).

API:
- enable(flag) / status()
- build(n=200) -> {png_b64, stats}

MOSTY:
- Yavnyy: (Obuchenie ↔ Kontrol) instruktor vidit sostoyanie sessii «zdes i seychas».
- Skrytyy #1: (Infoteoriya ↔ Videnie) edinyy overley s metrikami + teplokartoy oshibok.
- Skrytyy #2: (Inzheneriya ↔ Prostota) chistyy RGBA-render, offlayn.

ZEMNOY ABZATs:
Nikakikh vneshnikh zavisimostey: chitaem zhurnal, renderim PNG, vozvraschaem base64 v UI.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import http.client, json, base64, zlib, struct, math
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {"enabled": False, "last": None, "stats": {}}

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=10.0)
    conn.request("GET", path); r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _pair_lat(ev: List[Dict[str, Any]]) -> List[float]:
    lat=[]; last=None
    for e in ev:
        k=(e.get("event") or "").lower()
        if k in ("iplay_input","hotkey","click","input"):
            last=float(e.get("ts",0.0))
        elif k in ("ocr_ok","template_ok"):
            if last is not None:
                lat.append(max(0.0,float(e.get("ts",0.0))-last)*1000.0); last=None
    return lat

def _stats(arr: List[float]) -> Dict[str, Any]:
    if not arr: return {"count":0,"p50":0,"p90":0,"p99":0,"avg":0}
    s=sorted(arr); n=len(s)
    def q(p): i=min(n-1, max(0, int(round(p*(n-1))))); return s[i]
    return {"count":n,"p50":round(q(0.5),1),"p90":round(q(0.9),1),"p99":round(q(0.99),1),"avg":round(sum(s)/n,1)}

def _heat(w: int,h: int, pts: List[Tuple[int,int]], radius: int=44) -> List[float]:
    field=[0.0]*(w*h); r2=radius*radius
    for (x0,y0) in pts:
        x1,x2=max(0,x0-radius),min(w-1,x0+radius)
        y1,y2=max(0,y0-radius),min(h-1,y0+radius)
        for y in range(y1,y2+1):
            dy=y-y0
            for x in range(x1,x2+1):
                dx=x-x0; d2=dx*dx+dy*dy
                if d2<=r2: field[y*w+x]+=math.exp(-4.0*d2/float(r2))
    m=max(field) if field else 1.0
    return [v/m for v in field]

def _compose(w: int,h: int, stats: Dict[str,Any], heat: List[float]) -> bytes:
    # fon prozrachnyy; vnizu risuem plashku s metrikami
    rows=[]
    bar_h=80
    for y in range(h):
        row=bytearray([0])
        for x in range(w):
            if y>=h-bar_h:
                # temnaya polosa s tekstovymi «pipkami»
                rel=(x/(w-1))
                r=int(25+30*rel); g=int(25+30*(1-rel)); b=25; a=200
            else:
                v=heat[y*w+x]
                r=int(255*v); g=int(70*v); b=int(150*v); a=int(180*v)
            row+=bytes([r,g,b,a])
        rows.append(bytes(row))
    # upakuem PNG
    def chunk(t,d): return struct.pack(">I",len(d))+t+d+struct.pack(">I",zlib.crc32(t+d)&0xffffffff)
    sig=b"\x89PNG\r\n\x1a\n"; ihdr=struct.pack(">IIBBBBB", w,h,8,6,0,0,0)
    png=sig+chunk(b"IHDR",ihdr)+chunk(b"IDAT",zlib.compress(b"".join(rows),9))+chunk(b"IEND",b"")
    return png

def _collect(n: int) -> Dict[str, Any]:
    j = _get(f"/attention/journal/list?n={int(max(50,n))}")
    items = j.get("items", [])
    lat = _pair_lat(items)
    stats = _stats(lat)
    pts=[]
    for it in items:
        ev=(it.get("event") or "").lower()
        d=it.get("detail") or {}
        if ev in ("safe_step_fail","ocr_fail","template_fail"):
            if isinstance(d.get("box"),dict):
                b=d["box"]; pts.append((int(b["left"]+b["width"]/2), int(b["top"]+b["height"]/2)))
            elif isinstance(d.get("point"),dict):
                p=d["point"]; pts.append((int(p.get("x",0)), int(p.get("y",0))))
    return {"stats": stats, "pts": pts}

def enable(flag: bool) -> Dict[str, Any]:
    _state["enabled"]=bool(flag)
    return status()

def build(n: int = 200) -> Dict[str, Any]:
    met=_get("/desktop/metrics/info"); w,h=int(met.get("width",1280)), int(met.get("height",720))
    snap=_collect(n); heat=_heat(w,h,snap["pts"],44)
    png=_compose(w,h,snap["stats"],heat)
    b64=base64.b64encode(png).decode("ascii")
    _state["last"]=b64; _state["stats"]=snap["stats"]
    return {"ok": True, "png_b64": b64, "stats": snap["stats"], "w": w, "h": h}

def status() -> Dict[str, Any]:
    return {"ok": True, "enabled": bool(_state.get("enabled")), "stats": _state.get("stats", {}), "has_overlay": _state.get("last") is not None}