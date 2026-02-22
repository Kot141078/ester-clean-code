# -*- coding: utf-8 -*-
"""
modules/triggers/mass_tuner_weighted.py — «vzveshennyy» tyuning triggerov s uchetom karty oshibok.

Ideya:
- Poluchaem spisok triggerov (/triggers/list). Esli u template-triggera est cond.box, otsenivaem,
  skolko oshibok (iz error-heatmap) popalo v okrestnost ego tsentra.
- Chem «krasnee» oblast, tem vyshe minimalnyy threshold (min_thr) i/ili metka 'deprioritize': true.
- Dlya OCR-triggerov v «goryachey zone» — usilivaem lang (esli ukazan), dobavlyaem 'scale' iz /calibrate/status (optsionalno).

Vkhod opts:
{
  "radius": 80,             # radius okrestnosti dlya podscheta
  "penalty": 0.05,          # naskolko podnyat threshold za kazhdye 50 oshibok v okrestnosti
  "min_thr": 0.82,          # nizhnyaya granitsa dlya template
  "lang": "eng+rus",        # zhelaemyy lang dlya OCR
  "use_scale": true         # dobavit scale iz kalibrovki, esli est
}

Vykhod:
- preview(opts) -> plan pravok [{index,kind,new,reason:{hot_errors:int}}]
- apply(opts)   -> popytaetsya vyzvat /triggers/update, vernet otchet

MOSTY:
- Yavnyy: (Diagnostika ↔ Deystvie) «krasnye zony» → bolee strogie triggery.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) lokalnye, obyasnimye pravila.
- Skrytyy #2: (Kibernetika ↔ Ekspluatatsiya) metka 'deprioritize' daet podsistemam (selektoram) prostoy signal.

ZEMNOY ABZATs:
Chisto offlayn: chitaem /error/heatmap/build (ili parsim gotovyy JSON schetchikov pozzhe), /triggers/list, /calibrate/status. Kontrakty prezhnie.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import http.client, json, math
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=12.0)
    conn.request("GET", path); r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=12.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse(); t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _centroid(cond: Dict[str, Any]) -> Tuple[int,int] | None:
    b = cond.get("box")
    if isinstance(b, dict) and all(k in b for k in ("left","top","width","height")):
        return int(b["left"] + b["width"]/2), int(b["top"] + b["height"]/2)
    p = cond.get("point")
    if isinstance(p, dict) and "x" in p and "y" in p:
        return int(p["x"]), int(p["y"])
    return None

def _count_hot(radius: int) -> int:
    # poluchaem svezhie oshibki (pust sborom zaveduet suschestvuyuschaya /error/heatmap/build)
    r = _post("/error/heatmap/build", {"n": 600})
    # kartinka ne nuzhna; nam tolko kolichestvo — no dlya vesa ispolzuem obschee chislo oshibok
    return int(r.get("count", 0))

def _list_errors_points(n: int = 600) -> List[Dict[str,int]]:
    # zaberem iz zhurnala napryamuyu, chtoby imet tochki
    j = _get(f"/attention/journal/list?n={int(max(100,n))}")
    pts = []
    for it in j.get("items", []):
        ev = (it.get("event") or "").lower()
        if ev not in ("safe_step_fail","ocr_fail","template_fail"): 
            continue
        d = it.get("detail") or {}
        if isinstance(d.get("box"), dict):
            b = d["box"]; pts.append({"x": int(b["left"] + b["width"]/2), "y": int(b["top"] + b["height"]/2)})
        elif isinstance(d.get("point"), dict):
            p = d["point"]; pts.append({"x": int(p.get("x",0)), "y": int(p.get("y",0))})
    return pts

def _hot_near(cx: int, cy: int, pts: List[Dict[str,int]], radius: int) -> int:
    r2 = radius*radius; c = 0
    for p in pts:
        dx, dy = int(p["x"])-cx, int(p["y"])-cy
        if dx*dx + dy*dy <= r2: c += 1
    return c

def preview(opts: Dict[str, Any]) -> Dict[str, Any]:
    trg = _get("/triggers/list")
    pts = _list_errors_points(800)
    radius = int(opts.get("radius", 80))
    pen = float(opts.get("penalty", 0.05))   # per 50 errors
    min_thr = float(opts.get("min_thr", 0.82))
    want_lang = opts.get("lang")
    use_scale = bool(opts.get("use_scale", True))
    scale = None
    if use_scale:
        cal = _get("/calibrate/status")
        scale = cal.get("scale") or (cal.get("screen") or {}).get("scale") or None

    changes = []
    for i, t in enumerate(trg.get("triggers", [])):
        kind = (t.get("kind") or "").lower()
        cond = dict(t.get("cond") or {})
        cxy = _centroid(cond)
        if not cxy:
            continue
        hot = _hot_near(cxy[0], cxy[1], pts, radius)
        new = {}
        reason = {"hot_errors": hot}
        if kind == "template_match":
            thr = float(cond.get("threshold", 0.78))
            bump = pen * (hot / 50.0)
            target = max(min_thr, min(0.98, thr + bump))
            if target > thr:
                new["threshold"] = round(target, 3)
            if hot >= 100:
                new["deprioritize"] = True
        elif kind == "ocr_contains":
            if want_lang and cond.get("lang") != want_lang:
                new["lang"] = want_lang
            if hot >= 120:
                new["deprioritize"] = True
        if scale is not None and cond.get("scale") != scale:
            new["scale"] = scale
        if new:
            changes.append({"index": i, "kind": kind, "new": new, "reason": reason})
    return {"ok": True, "changes": changes, "opts": {"radius": radius, "penalty": pen, "min_thr": min_thr, "use_scale": use_scale}}

def apply(opts: Dict[str, Any]) -> Dict[str, Any]:
    plan = preview(opts)
    applied = []
    for ch in plan.get("changes", []):
        r = _post("/triggers/update", {"index": ch["index"], "patch": ch["new"]})
        applied.append({"index": ch["index"], "ok": bool(r.get("ok")), "response": r})
    return {"ok": True, "plan": plan, "applied": applied}