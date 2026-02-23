# -*- coding: utf-8 -*-
"""
routes/admin_llm.py — UI «Lokalnye LLM (LM Studio/Ollama)V» Re JSON-ruchki.

Marshruty:
  • GET  /admin/llm         — HTML-stranitsa
  • GET  /admin/llm/list    — JSON: kandidaty Re modeli (bez bencha)
  • POST /admin/llm/bench   — JSON: mikrobench vybrannoy modeli na vybrannom BASE

Sovmestimost:
  • Drop-in: ne menyaem suschestvuyuschie kontrakty; blyuprint izolirovan.
  • R egistratsiya predpolagaetsya cherez vyzov register_admin_llm(app) (dobavim v app.py pozzhe obschim paketom).

Mosty:
  • Yavnyy (Kibernetika v†" Orkestratsiya): vidimye «myshtsy» uzla (modeli), knopka «szhat kulak» (bench).
  • Skrytyy 1 (Infoteoriya v†" UI): otdaem kompaktnyy JSON — udobno Re cheloveku, Re avtomatike.
  • Skrytyy 2 (Vayes v†" Judge): bench daet apriori dlya vesov uzla (skorost/stabilnost) bez uchastiya polzovatelya.

Zemnoy abzats:
Stranitsa — instrument tekhnika: «vizhu server — meryayu skorost — zapisyvayu profil».
Eto podgotovka k avto-raspredeleniyu zadach: tyazhelye — na bystryy uzel, legkie — na kompaktnyy.

# c=a+b
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from flask import Blueprint, Response, jsonify, render_template, request

from modules.selfmanage.lmstudio_probe import bench_model, probe_summary  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_admin_llm = Blueprint("admin_llm", __name__)

@bp_admin_llm.get("/admin/llm")
def page_admin_llm() -> Response:
    return render_template("admin_llm.html")

@bp_admin_llm.get("/admin/llm/list")
def api_llm_list():
    try:
        rep = probe_summary()
        return jsonify(rep)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500

@bp_admin_llm.post("/admin/llm/bench")
def api_llm_bench():
    try:
        base = (request.form.get("base") or request.json.get("base") if request.is_json else None or "").strip()
        model = (request.form.get("model") or request.json.get("model") if request.is_json else None or "").strip()
        timeout = float(request.form.get("timeout") or (request.json.get("timeout") if request.is_json else 2.0) or 2.0)
        if not base or not model:
            return jsonify({"ok": False, "error": "base and model are required"}), 400
        rep = bench_model(base, model, timeout=timeout)
        return jsonify({"ok": True, "base": base, "model": model, "bench": rep})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500

def register_admin_llm(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_admin_llm)
    if url_prefix:
        # optsionalnyy dubl pod prefiksom (dlya mikroshardinga UI)
        pref = Blueprint("admin_llm_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/llm")
        def _p1():
            return render_template("admin_llm.html")

        @pref.get("/admin/llm/list")
        def _p2():
            return api_llm_list()

        @pref.post("/admin/llm/bench")
        def _p3():
            return api_llm_bench()

# app.register_blueprint(pref)
# c=a+b



def register(app):
    app.register_blueprint(bp_admin_llm)
    return app