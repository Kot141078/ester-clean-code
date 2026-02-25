# -*- coding: utf-8 -*-
"""rutes/meta_rutes_alias.po - alias routes for meta-tests and bandit."""
from __future__ import annotations
from typing import Any, Dict
from flask import jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
try:
    from flask_jwt_extended import jwt_required  # type: ignore
except Exception:
    def jwt_required():
        def deco(fn):
            return fn
        return deco

# Flexible imports for ester/modules layouts
try:
    from ester.modules.meta import trials  # type: ignore
    from ester.modules.meta import bandit  # type: ignore
    from ester.modules.judge.adapters import DummyAdapter, ExternalProcessAdapter, HTTPAdapter  # type: ignore
except Exception:
    from modules.meta import trials
    from modules.meta import bandit
    from modules.judge.adapters import DummyAdapter, ExternalProcessAdapter, HTTPAdapter

def register_meta_routes(app, url_prefix: str = "/meta"):
    base = url_prefix.rstrip("/")
    ep = (base or "/").strip("/").replace("/", "_")

    def _mk_adapter(payload: Dict[str, Any]):
        kind = str(payload.get("adapter") or "dummy").lower()
        if kind == "dummy":
            return DummyAdapter()
        if kind == "external":
            cmd = payload.get("cmd")
            if not cmd:
                raise ValueError("cmd required for adapter=external")
            import shlex
            return ExternalProcessAdapter(shlex.split(cmd))
        if kind == "http":
            url = payload.get("url")
            if not url:
                raise ValueError("url required for adapter=http")
            return HTTPAdapter(url)
        raise ValueError("unknown adapter")

    @app.get(f"{base}/trials", endpoint=f"{ep}_trials_list")
    @jwt_required()
    def meta_trials_list():
        return jsonify({"items": trials.list_specs()})

    @app.post(f"{base}/trials", endpoint=f"{ep}_trials_create")
    @jwt_required()
    def meta_trials_create():
        data = request.get_json(silent=True) or {}
        tid = str(data.get("id") or "").strip()
        spec = data.get("spec") or {}
        if not tid:
            return jsonify({"ok": False, "error": "id required"}), 400
        out = trials.create_spec(tid, spec)
        return jsonify(out)

    @app.get(f"{base}/trials/<tid>", endpoint=f"{ep}_trials_get")
    @jwt_required()
    def meta_trials_get(tid: str):
        spec = trials.get_spec(tid)
        if spec is None:
            return jsonify({"ok": False, "error": "not found"}), 404
        return jsonify({"id": tid, "spec": spec})

    @app.post(f"{base}/trials/<tid>/run", endpoint=f"{ep}_trials_run")
    @jwt_required()
    def meta_trials_run(tid: str):
        data = request.get_json(silent=True) or {}
        try:
            adapter = _mk_adapter(data)
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400
        task = data.get("task") or {}
        config = data.get("config") or {}
        out = trials.run_episode(tid, adapter=adapter, task=task, config=config)
        return jsonify(out)

    @app.get(f"{base}/bandit/<name>/arms", endpoint=f"{ep}_bandit_arms")
    @jwt_required()
    def meta_bandit_arms(name: str):
        return jsonify({"name": name, "arms": bandit.list_arms(name)})

    @app.post(f"{base}/bandit/<name>/pull", endpoint=f"{ep}_bandit_pull")
    @jwt_required()
    def meta_bandit_pull(name: str):
        data = request.get_json(silent=True) or {}
        algo = str(data.get("algo") or "ucb1").lower()
        step = int(data.get("step") or 1)
        if algo == "ucb1":
            arm = bandit.pull_ucb1(name, step=step)
        elif algo == "thompson":
            arm = bandit.pull_thompson(name)
        else:
            return jsonify({"ok": False, "error": "unknown algo"}), 400
        return jsonify({"ok": True, "arm": arm})

    @app.post(f"{base}/bandit/<name>/update", endpoint=f"{ep}_bandit_update")
    @jwt_required()
    def meta_bandit_update(name: str):
        data = request.get_json(silent=True) or {}
        arm_id = str(data.get("arm_id") or "")
        reward = float(data.get("reward") or 0.0)
        thr = float(data.get("threshold") or 0.5)
        out = bandit.update(name, arm_id=arm_id, reward=reward, threshold=thr)
        code = 200 if out.get("ok") else 400
        return jsonify(out), code

    @app.post(f"{base}/bandit/<name>/stage", endpoint=f"{ep}_bandit_stage")
    @jwt_required()
    def meta_bandit_stage(name: str):
        data = request.get_json(silent=True) or {}
        policy = data.get("policy") or {"name": name, "t": "staged"}
        out = bandit.stage_meta_policy(policy)
        return jsonify(out)

def register(app):
    return register_meta_routes(app)