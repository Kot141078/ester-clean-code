# -*- coding: utf-8 -*-
"""
routes/graph_routes.py — HTTP-obvyazka dlya DAG-orkestratora.
Podklyuchenie v app.py:
  from routes.graph_routes import bp_graph
  app.register_blueprint(bp_graph)
"""

from __future__ import annotations

import json
import threading
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from modules.graph.dag_engine import (
    DAGEngine,
    get_run_dir,
    load_plan_from_text,
    load_state,
    run_loop,
    save_state,
)

bp_graph = Blueprint("graph", __name__, url_prefix="/graph")

# R' pamyati budem khranit zapuschennye dvizhki (demo). R' prod — kak servisy/systemd.
RUNNERS: Dict[str, DAGEngine] = {}
LOCK = threading.Lock()


@bp_graph.post("/submit")
def submit():
    """
    Prinimaet YAML/JSON plan, zapuskaet v fone prostoy ranner.
    Bozvraschaet run_id.
    """
    try:
        text = request.data.decode("utf-8")
        if not text.strip():
            return jsonify({"ok": False, "error": "empty_plan"}), 400
        plan = load_plan_from_text(text)
        eng = DAGEngine(plan)
        with LOCK:
            RUNNERS[eng.run_id] = eng
        thr = threading.Thread(target=run_loop, args=(eng,), daemon=True)
        thr.start()
        return jsonify({"ok": True, "run_id": eng.run_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_graph.get("/status/<run_id>")
def status(run_id: str):
    st = load_state(run_id)
    if not st:
        return jsonify({"ok": False, "error": "unknown_run"}), 404
    include_ctx = request.args.get("include_ctx", "0") in ("1", "true", "yes")
    data: Dict[str, Any] = {"ok": True, "state": st}
    if include_ctx:
        # vernem kratkuyu svodku po vetkam (klyuchi kontekstov bez soderzhimogo)
        run_dir = get_run_dir(run_id)
        contexts = {}
        if run_dir.exists():
            for p in run_dir.glob("*.json"):
                try:
                    contexts[p.stem] = list(json.loads(p.read_text(encoding="utf-8")).keys())
                except Exception:
                    contexts[p.stem] = []
        data["contexts_index"] = contexts
    return jsonify(data)


@bp_graph.post("/human_complete")
def human_complete():
    """
    Imitatsiya otveta cheloveka:
    {
      "run_id": "...",
      "task_id": "hum_xxx",
      "result": "Odobryayu/popravki..."
    }
    """
    data = request.get_json(force=True, silent=False)
    run_id = data.get("run_id")
    task_id = data.get("task_id")
    result = data.get("result")
    if not run_id or not task_id:
        return jsonify({"ok": False, "error": "missing_fields"}), 400
    with LOCK:
        eng = RUNNERS.get(run_id)
    if not eng:
        # dvizhok mog byt v drugom protsesse — poprobuem cherez sostoyanie
        st = load_state(run_id)
        if not st:
            return jsonify({"ok": False, "error": "unknown_run"}), 404
        # vremennyy «kholodnyy» dvizhok dlya kommita rezultata
        # vosstanovim perechen uzlov iz sostoyaniya osnovnoy vetki (esli est)
        main_nodes = list((st.get("branches", {}).get("main", {}) or {}).get("nodes", {}).keys())
        eng = DAGEngine(
            {
                "run_id": run_id,
                "branch_id": "main",
                "nodes": [{"id": k} for k in main_nodes],
            }
        )
    ok = eng.on_human_completed(task_id, {"result": result})
    save_state(run_id, eng.state)
    return jsonify({"ok": ok})


@bp_graph.post("/start")
def start():
    """
    Zapusk uzhe zagruzhennogo plana po run_id (esli byl sozdan, no ne zapuschen).
    Glya sovmestimosti: /submit uzhe startuet plan, no etot endpoint ne pomeshaet.
    """
    data = request.get_json(force=True, silent=False)
    run_id = (data or {}).get("run_id")
    if not run_id:
        return jsonify({"ok": False, "error": "missing_run_id"}), 400
    with LOCK:
        eng = RUNNERS.get(run_id)
        if not eng:
            st = load_state(run_id)
            if not st:
                return jsonify({"ok": False, "error": "unknown_run"}), 404
            main_nodes = list(
                (st.get("branches", {}).get("main", {}) or {}).get("nodes", {}).keys()
            )
            eng = DAGEngine(
                {
                    "run_id": run_id,
                    "branch_id": "main",
                    "nodes": [{"id": k} for k in main_nodes],
                }
            )
            RUNNERS[run_id] = eng
    thr = threading.Thread(target=run_loop, args=(eng,), daemon=True)
    thr.start()
    return jsonify({"ok": True, "run_id": run_id})


def register(app):
    app.register_blueprint(bp_graph)
    return app
