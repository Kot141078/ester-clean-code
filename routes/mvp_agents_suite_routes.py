# routes/mvp_agents_suite_routes.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, current_app, jsonify, request

from routes.mvp_agents_manifest_routes import get_active_manifest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BP = Blueprint("mvp_agents_suite", __name__)


def _pick(body: Dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in body and body[k] is not None:
            return body[k]
    return None


def _extract_agent_id(body: Dict[str, Any]) -> str:
    v = _pick(body, "agent_id", "id", "agent", "suite_agent_id")
    return (v or "").strip()


def _extract_payload(body: Dict[str, Any]) -> Dict[str, Any]:
    # allow: input:{...}, payload:{...}, text:"..."
    inp = _pick(body, "input", "payload")
    if isinstance(inp, dict):
        return inp
    txt = _pick(body, "text", "message", "query", "prompt")
    if isinstance(txt, str) and txt.strip():
        return {"text": txt.strip()}
    return {}


def _resolve_suite_agent(suite_agent_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    m = get_active_manifest()
    for a in m.get("agents", []):
        if a.get("id") == suite_agent_id:
            return a, None
    return None, "unknown_suite_agent"


def _call_mvp_agent(runtime_id: str, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], int]:
    """Calls existing POST /mvp/agents/run internally (no network).
    We use the known working schema: {"id": "<mvp_agent_id>", "payload": {...}}."""
    req = {"id": runtime_id, "payload": payload, "input": payload, "agent_id": runtime_id}
    with current_app.test_client() as c:
        r = c.post("/mvp/agents/run", json=req)
        try:
            js = r.get_json(silent=True) or {}
        except Exception:
            js = {"raw": (r.data or b"").decode("utf-8", errors="replace")}
        return bool(r.status_code < 400), js, r.status_code


@BP.post("/mvp/agents/suite/run")
def suite_run():
    body = request.get_json(silent=True) or {}
    suite_agent_id = _extract_agent_id(body)
    if not suite_agent_id:
        return jsonify({"ok": False, "error": "agent_id_required"}), 400

    payload = _extract_payload(body)
    dry_run = bool(_pick(body, "dry_run", "preview_only", "safe", "simulate") if _pick(body, "dry_run", "preview_only", "safe", "simulate") is not None else True)
    payload.setdefault("dry_run", dry_run)

    suite_agent, err = _resolve_suite_agent(suite_agent_id)
    if err:
        return jsonify({"ok": False, "error": err, "agent_id": suite_agent_id}), 400

    runtime = suite_agent.get("runtime") or {}
    runtime_id = (runtime.get("id") or "").strip()
    if not runtime_id:
        return jsonify({"ok": False, "error": "runtime_resolution_failed"}), 500

    ok, mvp_resp, status = _call_mvp_agent(runtime_id, payload)
    if not ok:
        return jsonify(
            {
                "ok": False,
                "error": "mvp_run_failed",
                "status": status,
                "suite_agent_id": suite_agent_id,
                "runtime_id": runtime_id,
                "details": mvp_resp,
            }
        ), 502

    return jsonify(
        {
            "ok": True,
            "suite_agent": {"id": suite_agent_id, "runtime": {"kind": "mvp", "id": runtime_id}},
            "input": payload,
            "mvp": mvp_resp,
        }
    )


def register(app):
    app.register_blueprint(BP)
    return True