# -*- coding: utf-8 -*-
"""modules/instructor/hud_alerts.py - HUD-alerty po latentnosti/oshibkam.

Ideaya:
- Porogovye nastroyki: p90_ms, fail_rate (dolya “oshibochnykh” sobytiy sredi poslednikh N).
- build() risuet PNG-overley: esli prevysheno - krasnaya plashka “ALERT” + taymer; inache - greenaya "OK".
- Otdelno otdaem flag allow_audio: UI mozhet igrat Beep cherez WebAudio TOLKO v brauzere (by soglasiyu).

MOSTY:
- Yavnyy: (Control ↔ Obuchenie) bystryy signal “plokho/norm”.
- Skrytyy #1: (Infoteoriya ↔ Bezopasnost) nikakogo zvuka/deystviy bez yavnogo soglasiya.
- Skrytyy #2: (Inzheneriya ↔ UX) minimalnaya nagruzka — odin prozrachnyy PNG.

ZEMNOY ABZATs:
All lokalno, bez fonovykh demonov; statistika iz zhurnala, render RGBA.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List
import http.client, json, base64, zlib, struct, time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {"p90_ms": 800, "fail_rate": 0.15, "enabled": False, "allow_audio": False}

def configure(p90_ms: int, fail_rate: float, allow_audio: bool) -> Dict[str, Any]:
    _state.update({"p90_ms": int(p90_ms), "fail_rate": float(fail_rate), "allow_audio": bool(allow_audio)})
    return status()

def enable(flag: bool) -> Dict[str, Any]:
    _state["enabled"]=bool(flag); return status()

def status() -> Dict[str, Any]:
    return {"ok": True, **_state}

def _get(path: str) -> Dict[str, Any]:
    conn=http.client.HTTPConnection("127.0.0.1",8000,timeout=10.0)
    conn.request("GET", path); r=conn.getresponse()
    t=r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _stats(n: int = 200) -> Dict[str, Any]:
    j=_get(f"/attention/journal/list?n={n}")
    items=j.get("items",[])
    # n90 latency (as in previous modules)
    lat=[]; last=None
    bad=0; total=0
    for it in items:
        ev=(it.get("event") or "").lower()
        total+=1
        if ev in ("safe_step_fail","ocr_fail","template_fail"): bad+=1
        if ev in ("iplay_input","hotkey","click","input"): last=float(it.get("ts",0.0))
        elif ev in ("ocr_ok","template_ok"):
            if last is not None:
                lat.append(max(0.0,float(it.get("ts",0.0))-last)*1000.0); last=None
    lat_sorted=sorted(lat); n=len(lat_sorted)
    p90 = lat_sorted[min(n-1, int(round(0.90*(n-1))) )] if n else 0.0
    fr = float(bad)/max(1,total)
    return {"p90": round(p90,1), "fail_rate": round(fr,3)}

def _banner(w: int, h: int, ok: bool) -> bytes:
    rows=[]
    for y in range(h):
        row=bytearray([0])
        for x in range(w):
            if ok:
                # green translucent stripe
                r,g,b,a=40,150,40,200
            else:
                r,g,b,a=180,30,30,220
            row+=bytes([r,g,b,a])
        rows.append(bytes(row))
    def chunk(t,d): 
        import zlib, struct
        return struct.pack(">I",len(d))+t+d+struct.pack(">I",zlib.crc32(t+d)&0xffffffff)
    sig=b"\x89PNG\r\n\x1a\n"; import struct as S
    ihdr=S.pack(">IIBBBBB", w,h,8,6,0,0,0)
    return sig+chunk(b"IHDR",ihdr)+chunk(b"IDAT",zlib.compress(b"".join(rows),9))+chunk(b"IEND",b"")

def build(n: int = 200) -> Dict[str, Any]:
    met=_get("/desktop/metrics/info"); w,h=int(met.get("width",1280)), int(met.get("height",720))
    st=_stats(n)
    ok = (st["p90"] <= _state["p90_ms"]) and (st["fail_rate"] <= _state["fail_rate"])
    png=_banner(w, 60, ok)  # narrow plate at the top
    b64=base64.b64encode(png).decode("ascii")
    return {"ok": True, "alert": (not ok), "metrics": st, "png_b64": b64, "allow_audio": bool(_state.get("allow_audio"))}