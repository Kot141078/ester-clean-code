# -*- coding: utf-8 -*-
"""
routes/admin_judge_ab.py — UI/REST podskazok A/B dlya Judge (overlay-fayl).

Marshruty:
  • GET  /admin/judge/ab           — HTML-stranitsa
  • GET  /admin/judge/ab/suggest   — JSON-podskazki (bench optsionalen: ?bench=1)
  • POST /admin/judge/ab/apply     — zapisat overlay-fayl (put iz ENV ili form)

Sovmestimost:
  • Drop-in: ne trogaem Judge, ne menyaem kontrakty; sozdaem ryadom fayl podskazok.
  • Put fayla — ESTER_JUDGE_SLOTS_PATH (defolt ~/.ester/judge_slots.json).

Mosty:
  • Yavnyy (Kibernetika v†" Orkestratsiya): rekomendatsiya v†' yavnoe primenenie (po nazhatiyu).
  • Skrytyy 1 (Infoteoriya v†" Kontrakty): JSON-overlay — minimalnyy kanal integratsii.
  • Skrytyy 2 (Vayes v†" Vezopasnost): slotB — «eksperiment», slotA — opornyy.

Zemnoy abzats:
Stranitsa pozvolyaet uvidet, chto «zhelezo i modeli» predlagayut kak A/B, i sokhranit eto v fayl,
kotoryy mozhet podkhvatit storozh/skript perezagruzki Judge. Esli storozha net — fayl prosto lezhit.

# c=a+b
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from flask import Blueprint, Response, jsonify, render_template, request

from modules.judge.ab_suggest import build_suggestion, save_overlay, suggestion_to_dict  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_admin_judge_ab = Blueprint("admin_judge_ab", __name__)

@bp_admin_judge_ab.get("/admin/judge/ab")
def page_admin_judge_ab() -> Response:
    return render_template("admin_judge_ab.html")

@bp_admin_judge_ab.get("/admin/judge/ab/suggest")
def api_ab_suggest():
    bench = request.args.get("bench") in ("1", "true", "yes", "on")
    try:
        s = build_suggestion(bench=bench)
        return jsonify({"ok": True, "suggestion": suggestion_to_dict(s)})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500

@bp_admin_judge_ab.post("/admin/judge/ab/apply")
def api_ab_apply():
    try:
        is_json = request.is_json
        out = (request.form.get("out") if not is_json else request.json.get("out")) or os.getenv("ESTER_JUDGE_SLOTS_PATH") or ""
        bench = (request.form.get("bench") if not is_json else request.json.get("bench", 0)) in ("1", 1, True, "true")
        s = build_suggestion(bench=bench)
        fn = save_overlay(s, path=out if out else None)
        return jsonify({"ok": True, "saved_to": fn, "suggestion": suggestion_to_dict(s)})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500

def register_admin_judge_ab(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_admin_judge_ab)
    if url_prefix:
        pref = Blueprint("admin_judge_ab_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/judge/ab")
        def _p():
            return render_template("admin_judge_ab.html")

        @pref.get("/admin/judge/ab/suggest")
        def _ps():
            return api_ab_suggest()

        @pref.post("/admin/judge/ab/apply")
        def _pa():
            return api_ab_apply()

# app.register_blueprint(pref)
# c=a+b



def register(app):
    app.register_blueprint(bp_admin_judge_ab)
    return app