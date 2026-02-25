# -*- coding: utf-8 -*-
"""modules/thinking/recorder.py - “REC→PLAY”: zapis RPA-deystviy v sessiyu i eksport v workflow.

Stsenariy:
- start(session_id) — start zapis (sozdaet data/workflows/records/<session>.json)
- append(session_id, action) — add step: {"type":"click|type|hotkey|ocr_click|open|macro", ...}
- stop(session_id) — zavershaet zapis
- export_to_workflow(session_id, name) — build JSON workflow {name, steps:[{macro,args,...}]}

Sootvetstvie deystviy → workflow-steps:
- open(app) -> macro "open_portal_and_type" s empty text or spets. "open_app" esli est
- click(x,y) -> macro "click_xy"
- type(text) -> macro "type_text"
- hotkey(seq) -> macro "send_hotkey"
- ocr_click(needle,lang) -> macro "click_text"

(Note: makrosy dolzhny suschestvovat v modules.thinking.rpa_macros, kak vvodilos ranee.)

MOSTY:
- Yavnyy: (Memory ↔ Deystvie) zapis deystviy polzovatelya prevraschaetsya v vosproizvodimyy plan.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) unifikatsiya sobytiy k slovaryu makrosov.
- Skrytyy #2: (Kibernetika ↔ Obuchenie) bystroe “snachala rukami → potom robot.”

ZEMNOY ABZATs:
Faylovoe khranilische, oflayn. Minimal formaty JSON - something easy to proveryat i redaktirovat.

# c=a+b"""
from __future__ import annotations
import os, json, time
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
REC_DIR = os.path.join(ROOT, "data", "workflows", "records")
os.makedirs(REC_DIR, exist_ok=True)

def _path(session_id: str) -> str:
    return os.path.join(REC_DIR, f"{session_id}.json")

def start(session_id: str) -> Dict[str, Any]:
    if not session_id:
        return {"ok": False, "error": "session_required"}
    p = _path(session_id)
    if os.path.exists(p):
        return {"ok": False, "error": "session_exists"}
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"session": session_id, "ts": int(time.time()), "events": []}, f, ensure_ascii=False, indent=2)
    return {"ok": True, "path": p}

def append(session_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    p = _path(session_id)
    if not os.path.exists(p):
        return {"ok": False, "error": "no_session"}
    with open(p, "r", encoding="utf-8") as f:
        obj = json.load(f)
    ev = dict(event); ev["ts"] = int(time.time())
    obj["events"].append(ev)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return {"ok": True, "count": len(obj["events"])}

def stop(session_id: str) -> Dict[str, Any]:
    p = _path(session_id)
    if not os.path.exists(p):
        return {"ok": False, "error": "no_session"}
    return {"ok": True}

def export_to_workflow(session_id: str, name: str) -> Dict[str, Any]:
    p = _path(session_id)
    if not os.path.exists(p):
        return {"ok": False, "error": "no_session"}
    with open(p, "r", encoding="utf-8") as f:
        obj = json.load(f)
    steps: List[Dict[str, Any]] = []
    for ev in obj.get("events", []):
        t = ev.get("type")
        if t == "open":
            steps.append({"macro": "open_portal_and_type", "args": {"app": ev.get("app",""), "text": ev.get("text","")}})
        elif t == "click":
            steps.append({"macro": "click_xy", "args": {"x": int(ev.get("x",0)), "y": int(ev.get("y",0))}})
        elif t == "type":
            steps.append({"macro": "type_text", "args": {"text": ev.get("text","")}})
        elif t == "hotkey":
            steps.append({"macro": "send_hotkey", "args": {"seq": ev.get("seq","")}})
        elif t == "ocr_click":
            steps.append({"macro": "click_text", "args": {"needle": ev.get("needle",""), "lang": ev.get("lang","eng+rus")}})
        elif t == "macro":
            steps.append({"macro": ev.get("name",""), "args": ev.get("args",{})})
    spec = {"name": name, "steps": steps}
    # sokhranit v data/workflows/<name>.json — ispolzuem save_workflow
    try:
        from modules.thinking.rpa_workflows import save_workflow
        save_workflow(name, spec)
        return {"ok": True, "workflow": name, "steps": len(steps)}
    except Exception as e:
        return {"ok": False, "error": f"save_failed:{e}"}