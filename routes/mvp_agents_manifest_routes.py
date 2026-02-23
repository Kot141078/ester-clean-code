# routes/mvp_agents_manifest_routes.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

BP = Blueprint("mvp_agents_manifest", __name__)

KNOWN_MVP_AGENTS = ["director", "ops_guard", "rag_researcher", "messenger", "maker_dev"]

DEFAULT_MANIFEST_YAML = """\
manifest_version: 1
defaults:
  default_mode: safe
  write_enabled: false
  allowed_risk_levels: [low, medium, high]

agents:
  - id: est.dispatcher.synergy_mvp.v1
    mission: >
      Prinyat zadachu, utochnit tsel, vybrat luchshego ispolnitelya (ili svyazku) i vernut:
      "kogo naznachit + pochemu + sleduyuschiy shag". Sam nichego ne menyaet (tolko chtenie/sovet).
    runtime: { kind: mvp, id: director }
    capabilities:
      endpoints:
        - POST /synergy/assign/advice
      actions:
        - rag.hybrid.search
        - mem.passport.list
        - mem.kg.stats
        - auth.roles.me
    risk:
      level: low
      writes: []
      allowed: ["read_memory", "rank_agents"]
      default_mode: safe
      gates: {}
      prohibitions:
        - "no code/file apply"
        - "no passport append"
        - "no config changes"

  - id: est.ops.health_mvp.v1
    mission: >
      Diagnostika “zhivosti”: health/metrics, statusy, limity ingest.
      Konfigi menyaet tolko po yavnomu podtverzhdeniyu.
    runtime: { kind: mvp, id: ops_guard }
    capabilities:
      endpoints:
        - GET /health
        - GET /metrics/prom
      actions:
        - ingest.guard.state
        - ingest.guard.check
        - ingest.guard.config
        - mem.kg.stats
        - auth.roles.me
    risk:
      level: medium
      writes: ["ingest_guard_config (conditional)"]
      gates:
        ingest_guard_config:
          requires: ["explicit_user_confirm"]
      default_mode: safe
      prohibitions:
        - "no code/file apply"
        - "no passport append unless explicitly asked"

  - id: est.librarian.knowledge_mvp.v1
    mission: >
      Vesti znanie: bezopasno iskat, proveryat limity ingest, predlagat fakty dlya profilea,
      pomogat RAG.
    runtime: { kind: mvp, id: rag_researcher }
    capabilities:
      actions:
        - ingest.guard.check
        - ingest.guard.state
        - rag.hybrid.search
        - mem.passport.append
        - mem.passport.list
        - mem.kg.autolink
        - mem.kg.stats
    risk:
      level: medium
      writes: ["passport (conditional)", "kg_links (conditional)"]
      gates:
        passport_append:
          requires: ["source_required", "pii_check_basic", "explicit_user_confirm"]
        kg_autolink:
          requires: ["batch_limit<=N", "reversible_metadata"]
      default_mode: safe
      prohibitions:
        - "no deletion/scrub"
        - "no code/file apply"
        - "no ingest.guard.config unless explicitly asked"

  - id: est.builder.suite_mvp.v1
    mission: >
      Konstruktor agentov + otchety: opisat agenta, plan, sgenerit skelet. Lyubye apply — tolko cherez geyty.
    runtime: { kind: mvp, id: maker_dev }
    capabilities:
      endpoints:
        - POST /thinking/act
        - POST /thinking/cascade/plan
        - POST /thinking/cascade/execute
      actions:
        - agent.builder.describe
        - agent.builder.plan.generate
        - agent.builder.scaffold.files
        - agent.builder.apply
        - report.compose.md
        - report.save.files
    risk:
      level: high
      writes: ["generated_files (preview)", "code_apply (conditional)"]
      default_mode: "preview_only + safe_dry_run"
      gates:
        apply_code_or_files:
          requires:
            - "AB_SLOT == 'A'"
            - "ESTER_AGENT_BUILDER_WRITE == '1'"
            - "preview_only == false"
      prohibitions:
        - "no silent apply"
        - "no background writers without explicit enable"
"""

_ACTIVE: Dict[str, Any] = {
    "yaml": None,
    "manifest": None,
    "applied_at": None,
    "persist": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _issue(level: str, code: str, message: str, path: str = "") -> Dict[str, str]:
    return {"level": level, "code": code, "message": message, "path": path}


def _parse_yaml(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if yaml is None:
        return None, "pyyaml_missing"
    try:
        obj = yaml.safe_load(text) or {}
        if not isinstance(obj, dict):
            return None, "yaml_root_not_mapping"
        return obj, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _validate_manifest(obj: Dict[str, Any]) -> Tuple[bool, List[Dict[str, str]], Dict[str, Any]]:
    issues: List[Dict[str, str]] = []
    norm: Dict[str, Any] = {}

    mv = obj.get("manifest_version", None)
    if mv != 1:
        issues.append(_issue("error", "bad_manifest_version", "manifest_version must be 1", "manifest_version"))
    norm["manifest_version"] = 1

    defaults = obj.get("defaults") or {}
    if not isinstance(defaults, dict):
        issues.append(_issue("warn", "defaults_not_object", "defaults should be an object", "defaults"))
        defaults = {}
    norm["defaults"] = defaults

    agents = obj.get("agents") or []
    if not isinstance(agents, list):
        issues.append(_issue("error", "agents_not_list", "agents must be a list", "agents"))
        agents = []
    norm_agents: List[Dict[str, Any]] = []

    for i, a in enumerate(agents):
        pfx = f"agents[{i}]"
        if not isinstance(a, dict):
            issues.append(_issue("error", "agent_not_object", "agent must be an object", pfx))
            continue

        aid = (a.get("id") or "").strip()
        if not aid:
            issues.append(_issue("error", "agent_id_required", "agent.id is required", f"{pfx}.id"))

        mission = a.get("mission") or ""
        if not isinstance(mission, str):
            issues.append(_issue("warn", "mission_not_string", "mission should be string", f"{pfx}.mission"))
            mission = str(mission)

        runtime = a.get("runtime") or {}
        if not isinstance(runtime, dict):
            issues.append(_issue("error", "runtime_not_object", "runtime must be an object", f"{pfx}.runtime"))
            runtime = {}
        rkind = (runtime.get("kind") or "").strip()
        rid = (runtime.get("id") or "").strip()
        if rkind != "mvp":
            issues.append(_issue("error", "runtime_kind", "runtime.kind must be 'mvp'", f"{pfx}.runtime.kind"))
        if not rid:
            issues.append(_issue("error", "runtime_id_required", "runtime.id is required", f"{pfx}.runtime.id"))
        elif rid not in KNOWN_MVP_AGENTS:
            issues.append(_issue("warn", "unknown_mvp_agent", f"unknown mvp runtime id: {rid}", f"{pfx}.runtime.id"))

        caps = a.get("capabilities") or {}
        if not isinstance(caps, dict):
            issues.append(_issue("warn", "capabilities_not_object", "capabilities should be object", f"{pfx}.capabilities"))
            caps = {}

        risk = a.get("risk") or {}
        if not isinstance(risk, dict):
            issues.append(_issue("warn", "risk_not_object", "risk should be object", f"{pfx}.risk"))
            risk = {}
        level = (risk.get("level") or "").strip()
        if not level:
            issues.append(_issue("warn", "risk_level_missing", "risk.level missing", f"{pfx}.risk.level"))

        norm_agents.append(
            {
                "id": aid,
                "mission": mission,
                "runtime": {"kind": "mvp", "id": rid},
                "capabilities": caps,
                "risk": risk,
            }
        )

    norm["agents"] = norm_agents
    valid = not any(x["level"] == "error" for x in issues)
    return valid, issues, norm


def get_active_manifest() -> Dict[str, Any]:
    # always return something usable
    if _ACTIVE.get("manifest"):
        return _ACTIVE["manifest"]
    obj, _ = _parse_yaml(DEFAULT_MANIFEST_YAML)
    if not obj:
        return {"manifest_version": 1, "defaults": {}, "agents": []}
    _, _, norm = _validate_manifest(obj)
    return norm


@BP.get("/mvp/agents/manifest/default")
def manifest_default():
    return jsonify({"ok": True, "yaml": DEFAULT_MANIFEST_YAML})


@BP.get("/mvp/agents/manifest")
def manifest_get():
    if _ACTIVE.get("manifest"):
        return jsonify(
            {
                "ok": True,
                "active": True,
                "applied_at": _ACTIVE.get("applied_at"),
                "persist": _ACTIVE.get("persist"),
                "manifest": _ACTIVE.get("manifest"),
            }
        )
    # fallback
    return jsonify({"ok": True, "active": False, "manifest": get_active_manifest()})


@BP.post("/mvp/agents/manifest/preview")
def manifest_preview():
    body = request.get_json(silent=True) or {}
    text = body.get("yaml")
    strict = bool(body.get("strict", False))

    if not isinstance(text, str) or not text.strip():
        return jsonify({"ok": False, "error": "yaml_required"}), 400

    obj, perr = _parse_yaml(text)
    if obj is None:
        if strict:
            return jsonify({"ok": False, "error": "manifest_parse_error", "details": perr}), 400
        return jsonify(
            {
                "ok": True,
                "valid": False,
                "issues": [_issue("error", "manifest_parse_error", str(perr or "parse_error"), "yaml")],
                "manifest": None,
                "compiled": {"known_mvp_agents": KNOWN_MVP_AGENTS, "runtime_resolution": []},
            }
        )

    valid, issues, norm = _validate_manifest(obj)

    compiled = {
        "known_mvp_agents": KNOWN_MVP_AGENTS,
        "runtime_resolution": [
            {
                "agent": a["id"],
                "runtime_kind": a["runtime"]["kind"],
                "runtime_id": a["runtime"]["id"],
                "resolved": (a["runtime"]["id"] in KNOWN_MVP_AGENTS),
            }
            for a in norm.get("agents", [])
        ],
    }

    if strict and not valid:
        return jsonify({"ok": False, "error": "manifest_validation_error", "issues": issues}), 400

    return jsonify({"ok": True, "valid": bool(valid), "issues": issues, "manifest": norm, "compiled": compiled})


@BP.post("/mvp/agents/manifest/apply")
def manifest_apply():
    body = request.get_json(silent=True) or {}
    text = body.get("yaml") or DEFAULT_MANIFEST_YAML
    strict = bool(body.get("strict", False))
    persist = (request.args.get("persist") or body.get("persist") or "memory").strip()

    obj, perr = _parse_yaml(text)
    if obj is None:
        return jsonify({"ok": False, "error": "manifest_parse_error", "details": perr}), 400

    valid, issues, norm = _validate_manifest(obj)
    if strict and not valid:
        return jsonify({"ok": False, "error": "manifest_validation_error", "issues": issues}), 400
    if not valid:
        return jsonify({"ok": False, "error": "manifest_invalid", "issues": issues}), 400

    _ACTIVE["yaml"] = text
    _ACTIVE["manifest"] = norm
    _ACTIVE["applied_at"] = _now_iso()
    _ACTIVE["persist"] = persist

    return jsonify({"ok": True, "applied": True, "persist": persist, "issues": issues, "manifest": norm})


def register(app):
    app.register_blueprint(BP)
    return True