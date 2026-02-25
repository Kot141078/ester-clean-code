# routes/mvp_agents_routes.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    import yaml  # PyYAML
except Exception:
    yaml = None  # type: ignore

BP = Blueprint("mvp_agents", __name__)

# Important: leave your real agents as they are now in /mvp/agents/list.
# Below is an example that matches what you showed in the output sheet.
AGENTS: List[Dict[str, Any]] = [
    {
        "id": "director",
        "mission": "Route requests and collect response.",
        "capabilities": ["route", "plan", "merge_results", "rate_limit"],
        "risk": "medium",
    },
    {
        "id": "ops_guard",
        "mission": "Diagnostika i zdorove uzla.",
        "capabilities": ["healthcheck", "inspect_routes", "inspect_env"],
        "risk": "high",
    },
    {
        "id": "rag_researcher",
        "mission": "Dostavat relevantnyy kontekst iz pamyati/dokov.",
        "capabilities": ["retrieve", "quote", "summarize"],
        "risk": "medium",
    },
    {
        "id": "messenger",
        "mission": "Sending messages via approved channels/templates.",
        "capabilities": ["compose", "queue_outbox"],
        "risk": "high",
    },
    {
        "id": "maker_dev",
        "mission": "Draft modules + checks (without auto-application).",
        "capabilities": ["draft", "test", "diff"],
        "risk": "high",
    },
]


def _known_mvp_ids() -> List[str]:
    out: List[str] = []
    for a in AGENTS:
        i = str(a.get("id") or "").strip()
        if i:
            out.append(i)
    return out


def _issue(level: str, code: str, message: str, path: str = "") -> Dict[str, Any]:
    return {"level": level, "code": code, "message": message, "path": path}


def _as_list(v: Any) -> List[Any]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


@BP.get("/mvp/agents/health")
def health():
    return jsonify({"ok": True, "service": "mvp_agents"})


@BP.get("/mvp/agents/list")
def list_agents():
    return jsonify({"ok": True, "agents": AGENTS})


@BP.post("/mvp/agents/run")
def run_agent():
    """
    MVP-runner. Sovmestim s tvoimi testami:
      { "id": "director", "payload": {"text": "..."} }
    Aliasy:
      id | agent_id | agent
      payload | input
      goal (stroka) -> payload.text
    """
    body = request.get_json(silent=True) or {}

    agent_id = (
        str(body.get("id") or "").strip()
        or str(body.get("agent_id") or "").strip()
        or str(body.get("agent") or "").strip()
    )

    payload = body.get("payload", None)
    if payload is None:
        payload = body.get("input", None)

    if payload is None:
        goal = body.get("goal", None)
        if isinstance(goal, str) and goal.strip():
            payload = {"text": goal.strip()}
        else:
            payload = {}

    if isinstance(payload, str):
        payload = {"text": payload}

    if not isinstance(payload, dict):
        payload = {}

    known = set(_known_mvp_ids())
    if not agent_id or agent_id not in known:
        return jsonify({"ok": False, "error": "unknown_agent", "agent_id": agent_id or ""}), 400

    agent_meta = next((a for a in AGENTS if a.get("id") == agent_id), {"id": agent_id})

    # MVP behavior: echo/simulation
    return jsonify(
        {
            "ok": True,
            "agent": agent_meta,
            "input": payload,
            "output": f"[{agent_id}] received: {payload!r}",
        }
    )


# ---------------------------------------------------------------------
# API manifest (the very thing you don’t have now -> that’s why 404)
# ---------------------------------------------------------------------

_DEFAULT_MANIFEST_YAML_EXAMPLE = """\
manifest_version: 1

defaults:
  default_mode: safe
  write_enabled: false # NIChEGO ne primenyaem po umolchaniyu
  allowed_risk_levels: [low, medium, high]
  preview_only: true # yavnyy flag “tolko proektirovanie”

agents:
  - id: est.dispatcher.synergy_mvp.v1
    mission: >
      Prinyat zadachu, utochnit tsel, vybrat luchshego ispolnitelya/svyazku i return:
      "kogo naznachit + pochemu + sleduyuschiy shag". Sam nichego ne menyaet.
    runtime: { kind: mvp, id: director }
    capabilities:
      endpoints:
        - POST /synergy/assign/advice
      actions:
        - rag.hybrid.search
        - mem.passport.list
        - mem.kg.stats
        -auth.roles.me
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
        -auth.roles.me
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
      help RAG.
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
      Konstruktor agentov + otchety: opisat agenta, plan, sgenerit skeleton. Lyubye apply - only through geyty.
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


@BP.get("/mvp/agents/manifest")
def manifest_info():
    # just to avoid 404 + so that OH/tests can take an example
    return jsonify(
        {
            "ok": True,
            "hint": "POST /mvp/agents/manifest/preview with {yaml, strict}",
            "known_mvp_agents": _known_mvp_ids(),
            "example_yaml": _DEFAULT_MANIFEST_YAML_EXAMPLE,
        }
    )


def _normalize_and_validate_manifest(obj: Any) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], bool]:
    issues: List[Dict[str, Any]] = []
    norm: Dict[str, Any] = {"manifest_version": None, "defaults": {}, "agents": []}

    if not isinstance(obj, dict):
        issues.append(_issue("error", "manifest_type", "root must be a mapping/object", ""))
        compiled = {
            "known_mvp_agents": _known_mvp_ids(),
            "runtime_resolution": [],
        }
        return norm, issues, compiled, False

    mv = obj.get("manifest_version", None)
    norm["manifest_version"] = mv
    if mv != 1:
        issues.append(_issue("error", "manifest_version", "manifest_version must be 1", "manifest_version"))

    defaults = obj.get("defaults") or {}
    if not isinstance(defaults, dict):
        issues.append(_issue("error", "defaults_type", "defaults must be a mapping/object", "defaults"))
        defaults = {}
    defaults.setdefault("default_mode", "safe")
    defaults.setdefault("write_enabled", False)
    defaults.setdefault("allowed_risk_levels", ["low", "medium", "high"])
    norm["defaults"] = defaults

    agents = obj.get("agents")
    if not isinstance(agents, list) or not agents:
        issues.append(_issue("error", "agents_missing", "agents must be a non-empty list", "agents"))
        agents = []

    known = set(_known_mvp_ids())
    runtime_resolution: List[Dict[str, Any]] = []

    for i, a in enumerate(agents):
        pfx = f"agents[{i}]"
        if not isinstance(a, dict):
            issues.append(_issue("error", "agent_type", "agent must be a mapping/object", pfx))
            continue

        aid = str(a.get("id") or "").strip()
        if not aid:
            issues.append(_issue("error", "agent_id_missing", "id is required", f"{pfx}.id"))
            aid = f"__missing_{i}"

        mission = a.get("mission")
        if mission is None:
            issues.append(_issue("warn", "mission_missing", "mission is recommended", f"{pfx}.mission"))
            mission = ""

        runtime = a.get("runtime") or {}
        if not isinstance(runtime, dict):
            issues.append(_issue("error", "runtime_type", "runtime must be an object", f"{pfx}.runtime"))
            runtime = {}

        rkind = str(runtime.get("kind") or "").strip()
        rid = str(runtime.get("id") or "").strip()

        if rkind != "mvp":
            issues.append(_issue("error", "runtime_kind", "runtime.kind must be 'mvp'", f"{pfx}.runtime.kind"))

        if not rid:
            issues.append(_issue("error", "runtime_id_missing", "runtime.id is required", f"{pfx}.runtime.id"))
        elif rid not in known:
            issues.append(
                _issue(
                    "error",
                    "unknown_mvp_agent",
                    f"runtime.id '{rid}' not in known MVP agents {sorted(list(known))}",
                    f"{pfx}.runtime.id",
                )
            )

        caps = a.get("capabilities") or {}
        if not isinstance(caps, dict):
            issues.append(_issue("warn", "capabilities_type", "capabilities should be an object", f"{pfx}.capabilities"))
            caps = {}
        caps.setdefault("endpoints", [])
        caps.setdefault("actions", [])
        caps["endpoints"] = _as_list(caps.get("endpoints"))
        caps["actions"] = _as_list(caps.get("actions"))

        risk = a.get("risk") or {}
        if not isinstance(risk, dict):
            issues.append(_issue("error", "risk_type", "risk must be an object", f"{pfx}.risk"))
            risk = {}
        risk.setdefault("level", "medium")
        risk.setdefault("writes", [])
        risk.setdefault("default_mode", defaults.get("default_mode", "safe"))
        risk.setdefault("gates", {})
        risk.setdefault("prohibitions", [])
        risk["writes"] = _as_list(risk.get("writes"))
        risk["prohibitions"] = _as_list(risk.get("prohibitions"))
        if not isinstance(risk.get("gates"), dict):
            issues.append(_issue("warn", "gates_type", "risk.gates should be an object", f"{pfx}.risk.gates"))
            risk["gates"] = {}

        lvl = str(risk.get("level") or "").strip()
        allowed_lvls = defaults.get("allowed_risk_levels") or ["low", "medium", "high"]
        if isinstance(allowed_lvls, list) and lvl and lvl not in allowed_lvls:
            issues.append(
                _issue(
                    "warn",
                    "risk_level_unknown",
                    f"risk.level '{lvl}' not in allowed_risk_levels {allowed_lvls}",
                    f"{pfx}.risk.level",
                )
            )

        norm_agent = {
            "id": aid,
            "mission": mission,
            "runtime": {"kind": "mvp", "id": rid},
            "capabilities": caps,
            "risk": risk,
        }
        norm["agents"].append(norm_agent)

        runtime_resolution.append(
            {
                "agent": aid,
                "runtime_kind": "mvp",
                "runtime_id": rid,
                "resolved": bool(rid and rid in known),
            }
        )

    valid = not any(x.get("level") == "error" for x in issues)
    compiled = {
        "known_mvp_agents": _known_mvp_ids(),
        "runtime_resolution": runtime_resolution,
    }
    return norm, issues, compiled, valid


@BP.post("/mvp/agents/manifest/preview")
def manifest_preview():
    body = request.get_json(silent=True) or {}
    yaml_text = body.get("yaml")
    strict = bool(body.get("strict", False))

    if not isinstance(yaml_text, str) or not yaml_text.strip():
        return jsonify({"ok": False, "error": "manifest_parse_error", "details": "yaml (string) is required"}), 400

    if yaml is None:
        return jsonify({"ok": False, "error": "manifest_parse_error", "details": "PyYAML is not installed"}), 400

    try:
        obj = yaml.safe_load(yaml_text)  # type: ignore[attr-defined]
    except Exception as e:
        return jsonify({"ok": False, "error": "manifest_parse_error", "details": str(e)}), 400

    norm, issues, compiled, valid = _normalize_and_validate_manifest(obj)

    if strict and not valid:
        return jsonify({"ok": False, "error": "manifest_validation_error", "issues": issues, "manifest": norm, "compiled": compiled}), 400

    return jsonify({"ok": True, "valid": valid, "issues": issues, "manifest": norm, "compiled": compiled})


def register(app):
    app.register_blueprint(BP)
    return True
