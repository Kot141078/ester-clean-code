# -*- coding: utf-8 -*-
"""
modules/thinking/director.py — «zhivoy rezhisser» nad missiyami/ekranami.

Ideya:
- Derzhim «sessiyu rezhissera»: chat-istoriyu, tekuschiy plan shagov, indeks.
- Generatsiya shagov: uproschennyy planer (reyuz mentor_planner), plyus on-the-fly vstavki po replike.
- Overlei/vypolnenie: poverkh mentor_routes (+ vision overlay i rpa/act).

API (cherez routes/director_routes.py):
- POST /director/start {"topic":"pokazhi kak polzovatsya notepad"} -> session_id, steps
- POST /director/chat  {"session":"id","text":"..."} -> reply, suggestions
- POST /director/suggest {"session":"id"} -> candidate step (click/type/info/focus)
- POST /director/apply   {"session":"id","step":{...}} -> steps++
- POST /director/overlay {"session":"id","index":0,"template_b64"?:...}
- POST /director/run     {"session":"id","index":0}

Khranilische: v pamyati protsessa (legkovesno); serializatsiya ne trebuetsya.

MOSTY:
- Yavnyy: (Rech ↔ Plan ↔ Zrenie/Deystvie) operator govorit — rezhisser podstraivaet shagi i tut zhe pokazyvaet/vypolnyaet.
- Skrytyy #1: (Infoteoriya ↔ Kibernetika) live-tsikl: «vopros → shag → podsvetka → deystvie → reviziya».
- Skrytyy #2: (Logika ↔ Memory) chat-istoriya vliyaet na generiruemye shagi (prostye pravila).

ZEMNOY ABZATs:
Oflayn-realizatsiya: bez LLM-zavisimosti, pravilami. V lyuboy moment mozhno «Suggest→Apply» novyy shag i tut zhe ego podsvetit/vypolnit.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import uuid, re, time

from modules.thinking.mentor_planner import plan_from_request
from modules.ops.window_ops import send_hotkey

_SESS: Dict[str, Dict[str, Any]] = {}

def _new_session(topic: str) -> Dict[str, Any]:
    sid = str(uuid.uuid4())
    base = plan_from_request(topic)
    steps = list(base.get("steps", []))
    _SESS[sid] = {"id": sid, "topic": topic, "chat": [], "steps": steps, "ts": int(time.time())}
    return _SESS[sid]

def start(topic: str) -> Dict[str, Any]:
    s = _new_session(topic)
    return {"ok": True, "session": s["id"], "steps": s["steps"]}

def _ensure(sid: str) -> Dict[str, Any]:
    s = _SESS.get(sid)
    if not s:
        s = _new_session("pusto")
    return s

def chat(sid: str, text: str) -> Dict[str, Any]:
    s = _ensure(sid)
    s["chat"].append({"role":"user","text":text})
    # Prostaya reaktsiya: ischem klyuchi i gotovim predlozheniya
    sug = []
    t = text.lower()
    if re.search(r"(sokhran|save)", t):
        sug.append({"type":"click","title":"Save (CTRL+S)","action":{"type":"hotkey","seq":"CTRL+S"}})
    if re.search(r"(esche|dobav|add|more)", t):
        sug.append({"type":"info","title":"Poyasnenie","hint":"Mozhno dobavit podskazku dlya polzovatelya"})
    if re.search(r"(pechat|vvedi|type)", t):
        sug.append({"type":"type","title":"Vvod teksta","action":{"type":"rpa.type","text":"Esche odna stroka."}})
    return {"ok": True, "suggestions": sug, "turn": len(s["chat"])}

def suggest(sid: str) -> Dict[str, Any]:
    s = _ensure(sid)
    # evristika: esli notepad v teme — predlozhit «CTRL+S»
    if "notepad" in s.get("topic","").lower() or "bloknot" in s.get("topic","").lower():
        return {"ok": True, "step": {"type":"click","title":"Save","action":{"type":"hotkey","seq":"CTRL+S"}}}
    return {"ok": True, "step": {"type":"info","title":"Podskazka","hint":"Sdelayte skrinshot i proverte verkhnee menyu."}}

def apply(sid: str, step: Dict[str, Any]) -> Dict[str, Any]:
    s = _ensure(sid)
    s["steps"].append(step)
    return {"ok": True, "count": len(s["steps"])}

# --- Overlay/Run: ispolzuem uzhe suschestvuyuschie ruchki /mentor/overlay i /desktop/* ---
import http.client, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=5.0)
    conn.request("GET", path)
    r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=10.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def overlay(sid: str, index: int, template_b64: Optional[str], threshold: float) -> Dict[str, Any]:
    s = _ensure(sid)
    if index < 0 or index >= len(s["steps"]):
        return {"ok": False, "error": "bad_index"}
    step = dict(s["steps"][index])
    if template_b64:
        step["template_b64"] = template_b64
        step["threshold"] = threshold
    return _post("/mentor/overlay", {"step": step})

def run(sid: str, index: int) -> Dict[str, Any]:
    s = _ensure(sid)
    if index < 0 or index >= len(s["steps"]):
        return {"ok": False, "error": "bad_index"}
    step = s["steps"][index]
    t = (step.get("type") or "").lower()
    if t == "focus":
        return _post("/mentor/exec", {"step": step})
    if t == "type":
        return _post("/mentor/exec", {"step": step})
    if t == "click":
        act = step.get("action") or {}
        if act.get("type") == "hotkey" and act.get("seq"):
            ok = send_hotkey(act["seq"])
            return {"ok": bool(ok)}
        return _post("/mentor/exec", {"step": step})
    if t == "info":
        return {"ok": True}
    return {"ok": False, "error": "unknown_step"}