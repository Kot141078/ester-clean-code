# -*- coding: utf-8 -*-
"""routes/first_run_wizard.py - master pervogo zapuska (UI + JSON).

Route:
  • GET /first-run — HTML pages mastera
  • GET /first-run/status - JSON: khost, LM Studio, USB health
  • POST /first-run/apply - avtokonfiguratsiya: zapusk agenta + (opts.) bench

Mosty:
- Yavnyy (Kibernetika v†" UX): odin ekran Re odin refleks "Avtonastroyka".
- Skrytyy 1 (Infoteoriya v†" Protokol): ispolzuem uzhe suschestvuyuschie moduli (host_probe, lmstudio_probe, USB metrics).
- Skrytyy 2 (Logika v†" Vezopasnost): yavnyy POST dlya deystviy; bez skrytykh demonov.

Zemnoy abzats:
Polzovatel otkryvaet odnu stranitsu, nazhimaet odnu knopku – Ester sama “ponimaet” khost, startuet USB-agenta
v tekuschey sessii i (po zhelaniyu) delaet korotkiy bench lokalnogo LLM. Nikakoy golovnoy boli.
# c=a+b"""
from __future__ import annotations

import json
from typing import Any, Dict

from flask import Blueprint, Response, jsonify, render_template, request

from modules.selfmanage.host_probe import probe_host  # type: ignore
from modules.selfmanage.lmstudio_probe import probe_summary, probe_and_bench  # type: ignore
from modules.wizard.first_run import get_status, apply_autosetup  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_first_run = Blueprint("first_run", __name__)

@bp_first_run.get("/first-run")
def first_run_page() -> Response:
    return render_template("first_run_wizard.html")

@bp_first_run.get("/first-run/status")
def first_run_status():
    try:
        rep = get_status()
        return jsonify({"ok": True, **rep})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500

@bp_first_run.post("/first-run/apply")
def first_run_apply():
    """Telo request (form-data or JSON, optional):
      - bench=1 — vypolnit korotkiy bench pervoy naydennoy modeli
      - start_agent=1 — zapustit agenta “odin vopros” v fone (tekuschaya session)
      - headless=1 — ne pokazyvat notifikatsii (ENV ESTER_ZT_HEADLESS=1)"""
    try:
        is_json = request.is_json
        bench = (request.form.get("bench") if not is_json else request.json.get("bench", 0)) in ("1", 1, True, "true")
        start_agent = (request.form.get("start_agent") if not is_json else request.json.get("start_agent", 0)) in ("1", 1, True, "true")
        headless = (request.form.get("headless") if not is_json else request.json.get("headless", 0)) in ("1", 1, True, "true")
        rep = apply_autosetup(bench=bool(bench), start_agent=bool(start_agent), headless=bool(headless))
        return jsonify({"ok": True, **rep})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500

def register_first_run(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_first_run)
    if url_prefix:
        pref = Blueprint("first_run_pref", __name__, url_prefix=url_prefix)

        @pref.get("/first-run")
        def _p():
            return render_template("first_run_wizard.html")

        @pref.get("/first-run/status")
        def _ps():
            return first_run_status()

        @pref.post("/first-run/apply")
        def _pa():
            return first_run_apply()

# app.register_blueprint(pref)
# c=a+b



def register(app):
    app.register_blueprint(bp_first_run)
    return app