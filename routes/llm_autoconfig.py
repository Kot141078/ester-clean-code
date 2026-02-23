# -*- coding: utf-8 -*-
"""
routes/llm_autoconfig.py - UI/REST: avtokonfig LLM.

Marshruty:
  • GET  /admin/llm/autoconfig              - HTML
  • GET  /admin/llm/autoconfig/status       - snimki detect/plan/apply/selfcheck + nastroyki
  • POST /admin/llm/autoconfig/plan         - vypolnit planirovanie seychas
  • POST /admin/llm/autoconfig/apply        - primenit (AB=B → import v Ollama)
  • POST /admin/llm/autoconfig/selfcheck    - probnyy chat
  • POST /admin/llm/autoconfig/save         - sokhranit nastroyki

Mosty:
- Yavnyy (Kibernetika ↔ UX): v odnom ekrane i vidimost, i deystviya.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): AB-rezhim otrazhen, vidny modeli po bekendam.
- Skrytyy 2 (Praktika ↔ Sovmestimost): formaty JSON te zhe, chto v modulyakh; drop-in.

Zemnoy abzats:
Panel pusko-naladki: proverit bekendy, uvidet plan importa i prozhat primenit - vse lokalno.

# c=a+b
"""
from __future__ import annotations

import json, os
from pathlib import Path
from flask import Blueprint, jsonify, render_template, request

from modules.llm.autoconfig_settings import load_llm_settings, save_llm_settings  # type: ignore
from modules.llm.autoconfig import run_detect, run_plan, run_apply, run_selfcheck  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_llm = Blueprint("llm_autoconfig", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()
STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
STATE = STATE_DIR / "llm_autoconfig_state.json"

def _load_json(p: Path):
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

@bp_llm.get("/admin/llm/autoconfig")
def page():
    return render_template("llm_autoconfig.html", ab=AB)

@bp_llm.get("/admin/llm/autoconfig/status")
def api_status():
    s = load_llm_settings()
    st = _load_json(STATE)
    return jsonify({"ok": True, "ab": AB, "settings": s, "state": st})

@bp_llm.post("/admin/llm/autoconfig/plan")
def api_plan():
    s = load_llm_settings()
    rep = run_plan(s)
    return jsonify({"ok": True, "result": rep})

@bp_llm.post("/admin/llm/autoconfig/apply")
def api_apply():
    s = load_llm_settings()
    rep = run_apply(s)
    return jsonify({"ok": True, "result": rep})

@bp_llm.post("/admin/llm/autoconfig/selfcheck")
def api_selfcheck():
    s = load_llm_settings()
    rep = run_selfcheck(s)
    return jsonify({"ok": True, "result": rep})

@bp_llm.post("/admin/llm/autoconfig/save")
def api_save():
    body = request.get_json(silent=True) or {}
    patch = {
        "enable": bool(body.get("enable", False)),
        "interval": max(60, int(body.get("interval", 900))),
        "backend": str(body.get("backend","auto")),
        "min_models": max(0, int(body.get("min_models", 1))),
        "lmstudio_port": int(body.get("lmstudio_port", 1234)),
        "ollama_port": int(body.get("ollama_port", 11434)),
        "search_paths": list(body.get("search_paths") or []),
        "prefers": list(body.get("prefers") or []),
        "test_prompt": str(body.get("test_prompt","ok")),
    }
    s = save_llm_settings(patch)
    return jsonify({"ok": True, "settings": s})

def register_llm_autoconfig(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_llm)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("llm_autoconfig_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/llm/autoconfig")
        def _p(): return page()

        @pref.get("/admin/llm/autoconfig/status")
        def _s(): return api_status()

        @pref.post("/admin/llm/autoconfig/plan")
        def _pl(): return api_plan()

        @pref.post("/admin/llm/autoconfig/apply")
        def _ap(): return api_apply()

        @pref.post("/admin/llm/autoconfig/selfcheck")
        def _sc(): return api_selfcheck()

        @pref.post("/admin/llm/autoconfig/save")
        def _sv(): return api_save()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_llm)
    return app