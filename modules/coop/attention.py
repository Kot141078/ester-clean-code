# -*- coding: utf-8 -*-
"""modules/coop/attention.py - “ochki vnimaniya” dlya kooperativa.

Ideaya:
- Veduschiy publikuet “kuda smotret/zhat” (strelka/boks).
- Lokalno otrisovyvaem poverkh tekuschego skrina; parallelno rassylaem peers cherez /peer/proxy.
- Istoriya poslednikh N tochek v pamyati (dlya povtornoy otrisovki).

API:
- set_arrow(p_from, p_to, label, broadcast=True) -> {overlay_b64, peers:[...]}
- set_box(box, label, broadcast=True) -> {overlay_b64, peers:[...]}

MOSTY:
- Yavnyy: (Orkestratsiya ↔ Zrenie) vse vidyat odnu tsel.
- Skrytyy #1: (Infoteoriya ↔ UX) minimum simvolov — maximum smysla.
- Skrytyy #2: (Kibernetika ↔ Bezopasnost) yavnoe deystvie lidera, prozrachnyy sled.

ZEMNOY ABZATs:
All vyzovy - cherez suschestvuyuschie /desktop/rpa/screen i /stream/overlay/* + /peer/proxy. Nikakikh novykh demonov.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import http.client, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_HISTORY: List[Dict[str, Any]] = []

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=5.0)
    conn.request("GET", path)
    r = conn.getresponse(); t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=10.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse(); t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _broadcast_png(peers: List[str], kind: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    res = []
    for host in peers:
        try:
            res.append(_post("/peer/proxy", {"host": host, "path": f"/stream/overlay/{kind}", "payload": payload}))
        except Exception as e:
            res.append({"ok": False, "error": str(e)})
    return res

def set_arrow(p_from: Tuple[int,int], p_to: Tuple[int,int], label: str, peers: List[str], broadcast: bool=True) -> Dict[str, Any]:
    scr = _get("/desktop/rpa/screen")
    if not scr.get("ok"): return {"ok": False, "error":"screen_failed"}
    payload = {"png_b64": scr["png_b64"], "from": [int(p_from[0]),int(p_from[1])], "to":[int(p_to[0]),int(p_to[1])], "label": label}
    ov = _post("/stream/overlay/arrow", payload)
    _HISTORY.insert(0, {"type":"arrow","payload":payload}); _HISTORY[:] = _HISTORY[:50]
    peers_res = _broadcast_png(peers, "arrow", payload) if broadcast and peers else []
    return {"ok": True, "overlay_b64": ov.get("png_b64"), "peers": peers_res}

def set_box(box: Dict[str,int], label: str, peers: List[str], broadcast: bool=True) -> Dict[str, Any]:
    scr = _get("/desktop/rpa/screen")
    if not scr.get("ok"): return {"ok": False, "error":"screen_failed"}
    payload = {"png_b64": scr["png_b64"], "box": {"left":int(box["left"]),"top":int(box["top"]),"width":int(box["width"]),"height":int(box["height"])}, "label": label}
    ov = _post("/stream/overlay/box", payload)
    _HISTORY.insert(0, {"type":"box","payload":payload}); _HISTORY[:] = _HISTORY[:50]
    peers_res = _broadcast_png(peers, "box", payload) if broadcast and peers else []
    return {"ok": True, "overlay_b64": ov.get("png_b64"), "peers": peers_res}

def history() -> Dict[str, Any]:
    return {"ok": True, "items": list(_HISTORY)}