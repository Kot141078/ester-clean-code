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
            "Pokhozhe na problemu so zdorovem/metrikami/limitami — luchshe vsego spravitsya Ops/Health agent.",
            "Sleduyuschiy shag: zapusti est.ops.health_mvp.v1 v dry-run i posmotri svodku.",
        )

    # librarian
    if any(k in t for k in ["naydi", "po baze", "dokument", "tsit", "rag", "pamyat", "profile", "kb", "knowledge"]):
        return (
            "est.librarian.knowledge_mvp.v1",
            "Zapros pro poisk/kontekst/tsitirovanie — eto zona Knowledge/Librarian agenta.",
            "Sleduyuschiy shag: sdelay hybrid search i verni tsitaty/vyzhimku.",
        )

    # builder
    if any(k in t for k in ["novyy agent", "agenta", "yaml", "manifest", "skelet", "scaffold", "kod", "apply", "plan"]):
        return (
            "est.builder.suite_mvp.v1",
            "Zapros pro konstruirovanie/planirovanie/skelety — eto Builder/Suite agent.",
            "Sleduyuschiy shag: sgeneriruy YAML/plan v preview_only (bez apply).",
        )

    # dispatcher fallback
    return (
        "est.dispatcher.synergy_mvp.v1",
        "Obschiy/neyasnyy zapros — snachala Dispatcher vyberet ispolnitelya i utochnit kontekst.",
        "Sleduyuschiy shag: poprosi utochnenie tseli i predlozhi luchshego agenta.",
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