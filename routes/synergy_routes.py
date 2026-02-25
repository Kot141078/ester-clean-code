# routes/synergy_routes.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, Tuple

from flask import Blueprint, jsonify, request

from routes.mvp_agents_manifest_routes import get_active_manifest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BP = Blueprint("synergy", __name__)


def _pick(body: Dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in body and body[k] is not None:
            return body[k]
    return None


def _score(task: str) -> Tuple[str, str, str]:
    t = task.lower()

    # ops
    if any(k in t for k in ["health", "metrics", "oshib", "tormoz", "upal", "500", "cpu", "ram", "limit", "ingest"]):
        return (
            "est.ops.health_mvp.v1",
            "Sounds like a health/metrics/limits issue - an Ops/Health agent would be best to handle it.",
            "Next step: run eat.ops.healthn_mvp.v1 in dry-run and look at the summary.",
        )

    # librarian
    if any(k in t for k in ["naydi", "po baze", "dokument", "tsit", "rag", "pamyat", "profile", "kb", "knowledge"]):
        return (
            "est.librarian.knowledge_mvp.v1",
            "The search/context/citation request is the Knovleje/Libgarian agent zone.",
            "Next step: do a hybrid search and quotes/extracts are correct.",
        )

    # builder
    if any(k in t for k in ["novyy agent", "agenta", "yaml", "manifest", "skelet", "scaffold", "kod", "apply", "plan"]):
        return (
            "est.builder.suite_mvp.v1",
            "Request for design/planning/skeletons is a Builder/Suit agent.",
            "Next step: generate YML/plan in preview_only (without appli).",
        )

    # dispatcher fallback
    return (
        "est.dispatcher.synergy_mvp.v1",
        "General/vague request - first the Dispatcher will select the executor and clarify the context.",
        "Next step: ask for clarification of the goal and suggest the best agent.",
    )


@BP.post("/synergy/assign/advice")
def assign_advice():
    body = request.get_json(silent=True) or {}
    task = _pick(body, "task", "text", "input", "message", "query", "prompt")
    if not isinstance(task, str) or not task.strip():
        return jsonify({"ok": False, "error": "task_required"}), 400

    agent_id, why, next_step = _score(task.strip())
    m = get_active_manifest()
    known = [a.get("id") for a in m.get("agents", []) if a.get("id")]

    # if manifest doesn't have that id yet, still return advice (smoke-friendly)
    return jsonify(
        {
            "ok": True,
            "task": task.strip(),
            "recommend": {"agent_id": agent_id, "present_in_manifest": (agent_id in known)},
            "why": why,
            "next": next_step,
            "known_suite_agents": known,
        }
    )


def register(app):
    app.register_blueprint(BP)
    return True