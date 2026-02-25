# -*- coding: utf-8 -*-
"""routes/computer_use_routes.py - plany deystviy na PK bez opasnykh said-effektov.

MOSTY:
- Yavnyy: (UI/Plaginy ↔ Plan) POST /computer/run - formirouet plan vypolneniya zadachi.
- Skrytyy #1: (Mysl ↔ RPA) esli est desktop_agent - integratsiya vozmozhna, no ne obyazatelna.
- Skrytyy #2: (Bezopasnost ↔ Politiki) ne vypolnyaet komandy napriamuyu; only plan/kvitantsiya.

ZEMNOY ABZATs:
This is “list route” dlya kompyutera: what sdelat, v kakom poryadke, chem proverit - bez slepykh klikov ot imeni polzovatelya.

# c=a+b"""
from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("computer_use_routes", __name__, url_prefix="/computer")

# Let's try to detect desktop_agent (optional)
try:
    from modules.agents import desktop_agent as _desktop  # type: ignore
    _HAVE_DESKTOP = True
except Exception:
    _desktop = None  # type: ignore
    _HAVE_DESKTOP = False

_SAFE_TASKS = {"open_url", "search_text", "summarize_clipboard"}

def _san_url(u: str) -> str:
    u = (u or "").strip()
    if not re.match(r"^https?://", u, flags=re.I):
        u = "https://" + u
    return u

@bp.post("/run")
def api_run():
    d: Dict[str, Any] = request.get_json(silent=True) or {}
    task = str(d.get("task") or "").strip().lower()
    args = d.get("args") or {}
    if not task:
        return jsonify({"ok": False, "error": "task required"}), 400

    # only “safe” tasks; everything else is like a plan without execution
    plan: List[Dict[str, Any]] = []
    if task == "open_url":
        url = _san_url(str(args.get("url") or ""))
        if not url:
            return jsonify({"ok": False, "error": "url required"}), 400
        plan.append({"do": "open_browser", "with": {"url": url}})
    elif task == "search_text":
        q = str(args.get("q") or "").strip()
        plan.extend([
            {"do": "open_browser", "with": {"url": "https://www.google.com/"}},
            {"do": "type", "with": {"text": q}},
            {"do": "enter"},
        ])
    elif task == "summarize_clipboard":
        plan.append({"do": "read_clipboard"})
        plan.append({"do": "summarize"})
    else:
        plan.append({"do": "analyze_task", "with": {"task": task, "args": args}})
        plan.append({"do": "ask_confirmation"})

    ticket = {
        "id": str(uuid.uuid4()),
        "task": task,
        "args": args,
        "safe": task in _SAFE_TASKS,
        "have_desktop_agent": _HAVE_DESKTOP,
        "plan": plan,
        "status": "planned",
    }
    return jsonify({"ok": True, "ticket": ticket})

def register(app):
    app.register_blueprint(bp)

# finalnaya stroka
# c=a+b