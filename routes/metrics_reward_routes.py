# -*- coding: utf-8 -*-
"""
Marshruty RewardHub:
  GET  /metrics/meta/reward        -> summary()
  POST /metrics/meta/reward        -> update(payload)
  POST /metrics/meta/reward/reset  -> reset()
"""
from __future__ import annotations
from typing import Any, Dict
from flask import jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
from modules.auth.jwt_guard import require_jwt_or_503

# flex import RewardHub
try:
    from ester.modules.meta.reward_hub import RewardHub  # type: ignore
except Exception:
    from modules.meta.reward_hub import RewardHub

def register_metrics_reward_routes(app, url_prefix: str = "/metrics/meta"):
    base = url_prefix.rstrip("/")
    ep = (base or "/").strip("/").replace("/", "_")

    hub = RewardHub()

    @app.get(f"{base}/reward", endpoint=f"{ep}_reward_summary")
    @require_jwt_or_503()
    def reward_summary():
        return jsonify(hub.summary())

    @app.post(f"{base}/reward", endpoint=f"{ep}_reward_update")
    @require_jwt_or_503()
    def reward_update():
        data: Dict[str, Any] = request.get_json(silent=True) or {}
        out = hub.update(data)
        return jsonify(out)

    @app.post(f"{base}/reward/reset", endpoint=f"{ep}_reward_reset")
    @require_jwt_or_503()
    def reward_reset():
        return jsonify(hub.reset())

def register(app):
    return register_metrics_reward_routes(app)
