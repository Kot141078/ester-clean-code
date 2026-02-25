# -*- coding: utf-8 -*-
"""modules/desktop/auto_calibrate.py - avtokalibrovka ekrana/myshi (otsenka DPI/masshtaba).

Rezhimy:
- Quick probe: otsenivaet chastotu peremescheniya myshi (px/sec) i poluchaet metriki ekrana cherez /desktop/metrics/info.
- Manual 1cm: polzovatel vvodit, skolko pikseley zanimaet 1 sm po ekrannoy lineyke — poluchaem DPI i scale.

Khranilische:
- data/desktop/calibrate.json

API:
- quick_probe() -> {screen_w,h, mouse_px_per_sec, scale}
- set_manual(px_per_cm) -> obnovlyaet DPI/scale
- status() -> tekushee sostoyanie

MOSTY:
- Yavnyy: (Anatomiya ↔ Mekhanika) “ruka-mysh” sootnositsya s “glaz-ekran”.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) yavnye chislennye parameter snizhayut oshibki pozitsionirovaniya.
- Skrytyy #2: (Inzheneriya ↔ UX) precise scale uluchshaet shablonnyy matching i trenazhery.

ZEMNOY ABZATs:
No drayverov. Use gotovye REST-metriki i prostye vychisleniya. DPI ~ px_per_cm*2.54.

# c=a+b"""
from __future__ import annotations
import os, json, time
from typing import Dict, Any
import http.client
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
FILE = os.path.join(ROOT, "data", "desktop", "calibrate.json")
os.makedirs(os.path.dirname(FILE), exist_ok=True)

def _read() -> Dict[str, Any]:
    if not os.path.exists(FILE):
        with open(FILE,"w",encoding="utf-8") as f: json.dump({"dpi":96.0,"scale":1.0,"mouse_px_per_sec":0,"screen":{"w":1280,"h":720}}, f, ensure_ascii=False, indent=2)
    with open(FILE,"r",encoding="utf-8") as f: return json.load(f)

def _write(o: Dict[str, Any]):
    with open(FILE,"w",encoding="utf-8") as f: json.dump(o,f,ensure_ascii=False,indent=2)

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=8.0)
    conn.request("GET", path); r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False}

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=8.0)
    import json as _j
    conn.request("POST", path, body=_j.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse(); t = r.read().decode("utf-8","ignore"); conn.close()
    try: return _j.loads(t)
    except Exception: return {"ok": False}

def quick_probe() -> Dict[str, Any]:
    st = _read()
    met = _get("/desktop/metrics/info")
    w = int(met.get("width", st["screen"]["w"])); h = int(met.get("height", st["screen"]["h"]))
    # movement diagonally in the safe zone: 20 steps
    x0,y0 = int(w*0.1), int(h*0.1)
    x1,y1 = int(w*0.9), int(h*0.9)
    _post("/desktop/window/mouse_move", {"x":x0,"y":y0}); time.sleep(0.05)
    t0=time.time(); N=20
    for i in range(N):
        xi = x0 + (x1-x0)*i//(N-1)
        yi = y0 + (y1-y0)*i//(N-1)
        _post("/desktop/window/mouse_move", {"x":xi,"y":yi})
        time.sleep(0.01)
    dt = max(0.001, time.time()-t0)
    dist = ((x1-x0)**2 + (y1-y0)**2)**0.5
    pxps = dist/dt
    st["mouse_px_per_sec"] = int(pxps)
    st["screen"] = {"w": w, "h": h}
    # scale evristicheski: normiruem na etalon 96 dpi → ekrannaya diagonal ~ 24"?
    # leave rock=1.0 until manual calibration
    _write(st); return {"ok": True, **st}

def set_manual(px_per_cm: float) -> Dict[str, Any]:
    st = _read()
    try:
        pxcm = float(px_per_cm)
        dpi = pxcm * 2.54
        st["dpi"] = max(50.0, min(300.0, dpi))
        st["scale"] = st["dpi"]/96.0
        _write(st)
        return {"ok": True, **st}
    except Exception:
        return {"ok": False, "error": "bad_input"}

def status() -> Dict[str, Any]:
    return {"ok": True, **_read()}