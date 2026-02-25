# -*- coding: utf-8 -*-
"""modules/sense/collect.py - edinyy layer "Sense" dlya agenta.

Funktsii:
- journal_tail(n) -> poslednie n sobytiy iz zhurnala vnimaniya
- screen_snap(w,h) -> PNG (base64) snimok ekrana s vozmozhnym daunskeylom
- windows_list() -> spisok okon (title, bbox, active)
- proc_list(like=None) -> spisok protsessov OS (name,pid,cpu%,mem%)

Vzaimodeystviya (k istochnikam vnutri Ester):
- /attention/journal/list?n=...
- /desktop/screen/snap (esli est) ILI lokalnyy PNG-render iz /stream kadra
- /desktop_window_routes (esli est) ILI bezopasnye zaglushki
- /desktop/metrics/info — razmer ekrana (w,h)

MOSTY:
- Yavnyy: (Sensorika ↔ Planning) vse vkhody plana dostupny cherez edinyy modul.
- Skrytyy #1: (Inzheneriya ↔ Sovmestimost) myagkie fallback'i: esli spetsifichnyy istochnik nedostupen — vozvraschaem minimalnuyu strukturu.
- Skrytyy #2: (Infoteoriya ↔ Prozrachnost) formaty prostye: JSON+PNG-b64.

ZEMNOY ABZATs:
Vnutrennie vyzovy - lokalnyy HTTP na 127.0.0.1:8000; izobrazhenie generiruem RGBA→PNG bez vneshnikh zavisimostey; protsessy - cherez psutil, no esli ego net, otdaem empty spisok (oflayn-sovmestimost).

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List
import json, base64, zlib, struct, time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    import http.client as _http
except Exception:  # pragma: no cover
    _http = None

def _get(path: str) -> Dict[str, Any]:
    if _http is None:
        return {"ok": False, "error": "no_http_client"}
    try:
        c=_http.HTTPConnection("127.0.0.1", 8000, timeout=10.0)
        c.request("GET", path); r=c.getresponse()
        t=r.read().decode("utf-8","ignore"); c.close()
        return json.loads(t)
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if _http is None:
        return {"ok": False, "error": "no_http_client"}
    try:
        c=_http.HTTPConnection("127.0.0.1", 8000, timeout=10.0)
        c.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
        r=c.getresponse(); t=r.read().decode("utf-8","ignore"); c.close()
        return json.loads(t)
    except Exception as e:
        return {"ok": False, "error": str(e)}

# -------- Journal --------
def journal_tail(n: int = 100) -> Dict[str, Any]:
    n=max(1, min(1000, int(n)))
    j=_get(f"/attention/journal/list?n={n}")
    items=j.get("items", []) if isinstance(j, dict) else []
    return {"ok": True, "count": len(items), "items": items}

# -------- Screen (PNG base64) --------
def _compose_png(w: int, h: int) -> bytes:
    # transparent PNG plug of the required size
    rows=[]
    for y in range(h):
        row=bytearray([0])  # filtr 0
        row+=bytes([0,0,0,0])*(w)
        rows.append(bytes(row))
    def chunk(t,d): return struct.pack(">I",len(d))+t+d+struct.pack(">I",zlib.crc32(t+d)&0xffffffff)
    sig=b"\x89PNG\r\n\x1a\n"; ihdr=struct.pack(">IIBBBBB", w,h,8,6,0,0,0)
    return sig+chunk(b"IHDR",ihdr)+chunk(b"IDAT",zlib.compress(b"".join(rows),9))+chunk(b"IEND",b"")

def screen_snap(w: int = 0, h: int = 0) -> Dict[str, Any]:
    # first we try through the existing root
    snap=_get("/desktop/screen/snap")
    if isinstance(snap, dict) and snap.get("ok") and snap.get("png_b64"):
        png_b64=snap["png_b64"]
        # optional downscale (on the client side it’s better, but we’ll leave the parameter)
        # We don't resample here, it just returns the original
        return {"ok": True, "png_b64": png_b64, "w": snap.get("w"), "h": snap.get("h"), "source": "desktop_api"}
    # False: give an empty transparent PNG of the screen size
    met=_get("/desktop/metrics/info")
    W=int(met.get("width", 1280)); H=int(met.get("height", 720))
    if w and h:
        W, H = int(w), int(h)
    png=_compose_png(W, H); b64=base64.b64encode(png).decode("ascii")
    return {"ok": True, "png_b64": b64, "w": W, "h": H, "source": "fallback_blank"}

# -------- Windows --------
def windows_list() -> Dict[str, Any]:
    # if there is a system route, use it
    li=_get("/desktop/windows/list")
    if isinstance(li, dict) and li.get("ok") and isinstance(li.get("windows"), list):
        return {"ok": True, "windows": li["windows"], "source": "desktop_api"}
    # soft plug
    return {"ok": True, "windows": [], "source": "fallback_empty"}

# -------- Processes --------
def proc_list(like: str | None = None) -> Dict[str, Any]:
    try:
        import psutil  # type: ignore
    except Exception:
        return {"ok": True, "processes": [], "source": "no_psutil"}
    out=[]
    for p in psutil.process_iter(attrs=["pid","name","cpu_percent","memory_percent"]):
        name=p.info.get("name") or ""
        if like and like.lower() not in name.lower():
            continue
        out.append({
            "name": name,
            "pid": int(p.info.get("pid") or 0),
            "cpu": float(p.info.get("cpu_percent") or 0.0),
            "mem": float(p.info.get("memory_percent") or 0.0)
        })
    return {"ok": True, "processes": out, "source": "psutil"}