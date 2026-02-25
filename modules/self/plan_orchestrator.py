# -*- coding: utf-8 -*-
"""modules/self/plan_orchestrator.py - volevoy planirovschik: iz tseli v nabor shagov (bez polomki starykh kontraktov).

API:
  • make_plan(goal:str, constraints:dict|None=None) -> dict
  • execute(plan:dict, safe:bool=True) -> dict

Mosty:
- Yavnyy: (Volya ↔ Deystviya) svyazyvaet tsel s zaregistrirovannymi actions i dostupnymi routami.
- Skrytyy #1: (Infoteoriya ↔ Poisk) vklyuchaet uzel “rasshirit kontekst” pri nekhvatke znaniy.
- Skrytyy #2: (Kibernetika ↔ Kontrol) safe/dry-run po umolchaniyu i A/B slot ne dayut “perestaratsya”.

Zemnoy abzats:
Eto dispetcher: “what sdelat, v kakom poryadke, chem imenno” - i vozmozhnost vypolnit bezopasno/po shagam.

# c=a+b"""
from __future__ import annotations

import os
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PLAN_AB = (os.getenv("SELF_PLAN_AB","A") or "A").upper()

def _have_route(path: str) -> bool:
    try:
        from flask import current_app
        for r in current_app.url_map.iter_rules():
            if str(r) == path:
                return True
    except Exception:
        pass
    return False

def make_plan(goal: str, constraints: Dict[str, Any] | None = None) -> Dict[str, Any]:
    g = (goal or "").lower()
    steps: List[Dict[str, Any]] = []
    # prostye evristiki vybora instrumentov
    need_video = any(k in g for k in ("video","video","youtube","rutube","videorolik"))
    need_search = any(k in g for k in ("nayti","search","iskat","poisk","istochniki"))
    # 1) if you need to search, add a context expander
    if _have_route("/thinking/web_context/expand") and (need_search or "kontekst" in g):
        steps.append({"kind":"web_context.expand", "endpoint":"/thinking/web_context/expand", "body":{"q":goal, "k":5, "autofetch": False}})
    # 2) if the video is a universal video ingest
    if _have_route("/ingest/video/universal/fetch") and need_video:
        steps.append({"kind":"video.ingest", "endpoint":"/ingest/video/universal/fetch", "body":{"url":"<REQUIRED>", "want":{"subs":True,"summary":True,"meta":True}}})
        if _have_route("/video/index/build"):
            steps.append({"kind":"video.index", "endpoint":"/video/index/build", "body":{"dump":"<FROM_PREV>"}})
        if _have_route("/video/qa/search"):
            steps.append({"kind":"video.qa", "endpoint":"/video/qa/search", "body":{"q":goal, "k":5,"scope":{"dump":"<FROM_PREV>"}}})
    # 3) general memory/reflection
    if _have_route("/thinking/reflection/enqueue"):
        steps.append({"kind":"reflect.enqueue", "endpoint":"/thinking/reflection/enqueue", "body":{"item":{"text":goal, "meta":{"importance":0.7}}}})
    return {"ok": True, "goal": goal, "steps": steps, "ab": PLAN_AB}

def execute(plan: Dict[str, Any], safe: bool = True) -> Dict[str, Any]:
    if PLAN_AB == "B":
        safe = True
    res = []
    for st in plan.get("steps") or []:
        ep = st.get("endpoint")
        body = st.get("body") or {}
        if safe:
            res.append({"step": st, "status":"dry-run"})
            continue
        try:
            import requests, os
            base = os.getenv("ESTER_BASE_URL", "http://127.0.0.1:8000")
            r = requests.post(base + ep, json=body, timeout=12)
            ok = (r.status_code == 200)
            res.append({"step": st, "status":"ok" if ok else f"error {r.status_code}", "resp": (r.json() if ok else r.text[:400])})
        except Exception as e:
            res.append({"step": st, "status":"exception", "error": str(e)})
    return {"ok": True, "results": res}