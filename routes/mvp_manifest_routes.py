# routes/mvp_manifest_routes.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from flask import Blueprint, current_app, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("mvp_manifest_routes", __name__)

# ---- Default YAML manifest (4 ester-agents -> existing MVP agents) ----
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
      Konstruktor agentov + otchety: opisat agenta, plan, sgenerit skelet.
      Lyubye apply — tolko cherez geyty.
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

# ---- In-memory “active manifest” (safe, no silent file write) ----
_STATE: Dict[str, Any] = {
    "active_yaml": None,
    "active_manifest": None,
    "applied_at": None,
    "hash": None,
    "autonomy_ticks": 0,
    "last_autonomy": None,
}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()


def _yaml_load(s: str) -> Dict[str, Any]:
    """
    Best-effort YAML load.
    Accepts JSON-as-YAML too (PyYAML can parse JSON).
    """
    try:
        import yaml  # type: ignore
    except Exception as e:
        raise RuntimeError("PyYAML not installed (pip install pyyaml)") from e

    obj = yaml.safe_load(s)
    if not isinstance(obj, dict):
        raise ValueError("manifest root must be a mapping/object")
    return obj


def _issue(level: str, code: str, message: str, path: str) -> Dict[str, str]:
    return {"level": level, "code": code, "message": message, "path": path}


def _known_mvp_agents() -> List[str]:
    # safest: call the already-registered endpoint internally (no external HTTP)
    try:
        client = current_app.test_client()
        r = client.get("/mvp/agents/list")
        if r.status_code != 200:
            return []
        j = r.get_json(silent=True) or {}
        agents = j.get("agents") or []
        out = []
        for a in agents:
            if isinstance(a, dict) and a.get("id"):
                out.append(str(a["id"]))
        return out
    except Exception:
        return []


def _normalize_and_validate(raw: Dict[str, Any]) -> Tuple[bool, List[Dict[str, str]], Dict[str, Any]]:
    issues: List[Dict[str, str]] = []

    mv = raw.get("manifest_version", None)
    if mv != 1:
        issues.append(_issue("error", "bad_manifest_version", "manifest_version must be 1", "manifest_version"))

    defaults = raw.get("defaults") or {}
    if not isinstance(defaults, dict):
        issues.append(_issue("error", "bad_defaults", "defaults must be an object", "defaults"))
        defaults = {}

    allowed_risk = defaults.get("allowed_risk_levels") or ["low", "medium", "high"]
    if not isinstance(allowed_risk, list) or not all(isinstance(x, str) for x in allowed_risk):
        issues.append(_issue("warn", "bad_allowed_risk_levels", "defaults.allowed_risk_levels should be list[str]", "defaults.allowed_risk_levels"))
        allowed_risk = ["low", "medium", "high"]

    agents = raw.get("agents")
    if not isinstance(agents, list):
        issues.append(_issue("error", "bad_agents", "agents must be a list", "agents"))
        agents = []

    known_mvp = set(_known_mvp_agents())
    runtime_resolution = []

    norm_agents: List[Dict[str, Any]] = []
    for i, a in enumerate(agents):
        path0 = f"agents[{i}]"
        if not isinstance(a, dict):
            issues.append(_issue("error", "bad_agent", "agent must be an object", path0))
            continue

        aid = str(a.get("id") or "").strip()
        if not aid:
            issues.append(_issue("error", "missing_id", "agent.id is required", f"{path0}.id"))
            continue

        mission = a.get("mission") or ""
        if not isinstance(mission, str) or not mission.strip():
            issues.append(_issue("warn", "missing_mission", "agent.mission should be non-empty string", f"{path0}.mission"))

        runtime = a.get("runtime") or {}
        if not isinstance(runtime, dict):
            issues.append(_issue("error", "bad_runtime", "agent.runtime must be an object", f"{path0}.runtime"))
            runtime = {}

        rkind = str(runtime.get("kind") or "mvp")
        rid = str(runtime.get("id") or "").strip()

        if rkind != "mvp":
            issues.append(_issue("error", "unsupported_runtime_kind", "only runtime.kind=mvp supported in MVP", f"{path0}.runtime.kind"))

        if not rid:
            issues.append(_issue("error", "missing_runtime_id", "runtime.id is required", f"{path0}.runtime.id"))

        resolved = bool(rid and (rid in known_mvp if known_mvp else True))
        if known_mvp and rid and rid not in known_mvp:
            issues.append(_issue("error", "unknown_mvp_agent", f"runtime.id '{rid}' not in /mvp/agents/list", f"{path0}.runtime.id"))

        runtime_resolution.append(
            {"agent": aid, "runtime_kind": rkind, "runtime_id": rid, "resolved": resolved}
        )

        risk = a.get("risk") or {}
        if not isinstance(risk, dict):
            issues.append(_issue("error", "bad_risk", "agent.risk must be an object", f"{path0}.risk"))
            risk = {}

        rlevel = str(risk.get("level") or "").strip().lower()
        if rlevel and rlevel not in [x.lower() for x in allowed_risk]:
            issues.append(_issue("error", "bad_risk_level", f"risk.level must be one of {allowed_risk}", f"{path0}.risk.level"))

        # minimal normalized agent
        norm_agents.append(
            {
                "id": aid,
                "mission": mission,
                "runtime": {"kind": rkind, "id": rid},
                "capabilities": a.get("capabilities") or {},
                "risk": risk,
            }
        )

    normalized = {
        "manifest_version": 1,
        "defaults": {
            "default_mode": str(defaults.get("default_mode") or "safe"),
            "write_enabled": bool(defaults.get("write_enabled", False)),
            "allowed_risk_levels": allowed_risk,
        },
        "agents": norm_agents,
    }

    valid = not any(x["level"] == "error" for x in issues)
    compiled = {
        "known_mvp_agents": sorted(list(known_mvp)) if known_mvp else [],
        "runtime_resolution": runtime_resolution,
    }
    normalized["_compiled"] = compiled  # handy internally

    return valid, issues, normalized


def _get_active_yaml() -> str:
    return _STATE["active_yaml"] or DEFAULT_MANIFEST_YAML


def _get_active_manifest() -> Dict[str, Any]:
    if _STATE["active_manifest"]:
        return _STATE["active_manifest"]
    # if not applied yet -> derive from default
    raw = _yaml_load(DEFAULT_MANIFEST_YAML)
    valid, issues, norm = _normalize_and_validate(raw)
    _STATE["active_yaml"] = DEFAULT_MANIFEST_YAML
    _STATE["active_manifest"] = norm
    _STATE["applied_at"] = _utc_iso()
    _STATE["hash"] = _sha256(DEFAULT_MANIFEST_YAML)
    _STATE["last_preview_issues"] = issues
    _STATE["last_preview_valid"] = valid
    return norm


@bp.get("/mvp/agents/manifest/default")
def manifest_default():
    return jsonify({"ok": True, "yaml": DEFAULT_MANIFEST_YAML})


@bp.get("/mvp/agents/manifest")
def manifest_get_active():
    m = _get_active_manifest()
    return jsonify(
        {
            "ok": True,
            "applied_at": _STATE.get("applied_at"),
            "hash": _STATE.get("hash"),
            "manifest": m,
            "yaml": _get_active_yaml(),
        }
    )


@bp.post("/mvp/agents/manifest/preview")
def manifest_preview():
    body = request.get_json(silent=True) or {}
    yaml_text = body.get("yaml")
    strict = bool(body.get("strict", False))

    if not isinstance(yaml_text, str) or not yaml_text.strip():
        return jsonify({"ok": False, "error": "yaml_required"}), 400

    try:
        raw = _yaml_load(yaml_text)
    except Exception as e:
        # parse error is always fatal
        return jsonify({"ok": False, "error": "manifest_parse_error", "details": str(e)}), 400

    valid, issues, norm = _normalize_and_validate(raw)
    compiled = norm.get("_compiled") or {}
    norm = {k: v for k, v in norm.items() if k != "_compiled"}

    if strict and not valid:
        return jsonify({"ok": False, "error": "manifest_validation_error", "issues": issues}), 400

    return jsonify(
        {
            "ok": True,
            "valid": bool(valid),
            "issues": issues,
            "manifest": norm,
            "compiled": compiled,
        }
    )


@bp.post("/mvp/agents/manifest/apply")
def manifest_apply():
    """
    Safe apply:
    - default target=memory (no file writes)
    - target=file writes only if you explicitly request it
    """
    body = request.get_json(silent=True) or {}
    yaml_text = body.get("yaml")
    strict = bool(body.get("strict", False))
    target = (request.args.get("target") or "memory").strip().lower()

    if not isinstance(yaml_text, str) or not yaml_text.strip():
        return jsonify({"ok": False, "error": "yaml_required"}), 400

    # reuse preview validation
    try:
        raw = _yaml_load(yaml_text)
    except Exception as e:
        return jsonify({"ok": False, "error": "manifest_parse_error", "details": str(e)}), 400

    valid, issues, norm = _normalize_and_validate(raw)
    compiled = norm.get("_compiled") or {}
    norm = {k: v for k, v in norm.items() if k != "_compiled"}

    if strict and not valid:
        return jsonify({"ok": False, "error": "manifest_validation_error", "issues": issues}), 400

    # apply in memory
    _STATE["active_yaml"] = yaml_text
    _STATE["active_manifest"] = norm
    _STATE["applied_at"] = _utc_iso()
    _STATE["hash"] = _sha256(yaml_text)
    _STATE["last_preview_issues"] = issues
    _STATE["last_preview_valid"] = valid

    # optional file write
    saved_path = None
    if target == "file":
        # only if explicitly asked
        out_dir = os.path.join(os.getcwd(), "data")
        os.makedirs(out_dir, exist_ok=True)
        saved_path = os.path.join(out_dir, "mvp_agents_manifest_active.yaml")
        with open(saved_path, "w", encoding="utf-8") as f:
            f.write(yaml_text)

    return jsonify(
        {
            "ok": True,
            "valid": bool(valid),
            "issues": issues,
            "hash": _STATE["hash"],
            "applied_at": _STATE["applied_at"],
            "target": target,
            "saved_path": saved_path,
            "compiled": compiled,
        }
    )


@bp.post("/mvp/agents/suite/run")
def suite_run():
    """
    Run ester-agent by id using active manifest mapping -> /mvp/agents/run
    Contract (loose):
      { "agent": "est.ops.health_mvp.v1", "text": "....", "payload": {...}, "dry_run": true }
    """
    body = request.get_json(silent=True) or {}
    agent = (body.get("agent") or body.get("id") or body.get("agent_id") or "").strip()
    text = body.get("text") or body.get("task") or body.get("input") or ""
    payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
    dry_run = bool(body.get("dry_run", True))
    consent = bool(body.get("consent", False))

    if not agent:
        return jsonify({"ok": False, "error": "agent_required"}), 400

    manifest = _get_active_manifest()
    agents = manifest.get("agents") or []
    entry = None
    for a in agents:
        if isinstance(a, dict) and a.get("id") == agent:
            entry = a
            break
    if not entry:
        return jsonify({"ok": False, "error": "unknown_suite_agent", "agent": agent}), 400

    risk = entry.get("risk") or {}
    risk_level = str(risk.get("level") or "").lower()

    # Safety: high-risk runs default to dry_run unless explicit consent
    if risk_level == "high" and not consent:
        dry_run = True

    runtime = entry.get("runtime") or {}
    rid = str(runtime.get("id") or "").strip()
    if not rid:
        return jsonify({"ok": False, "error": "bad_runtime_mapping", "agent": agent}), 400

    # Bridge into existing MVP run endpoint (your current contract: {id, payload})
    bridge_payload = dict(payload)
    if isinstance(text, str) and text.strip():
        bridge_payload.setdefault("text", text.strip())
    bridge_payload.setdefault("dry_run", dry_run)

    client = current_app.test_client()
    r = client.post("/mvp/agents/run", json={"id": rid, "payload": bridge_payload})
    try:
        j = r.get_json(silent=True)
    except Exception:
        j = None

    return jsonify(
        {
            "ok": True,
            "suite_agent": agent,
            "runtime_id": rid,
            "dry_run": dry_run,
            "consent": consent,
            "mvp_status": r.status_code,
            "mvp_response": j,
        }
    )


@bp.post("/synergy/assign/advice")
def synergy_assign_advice():
    """
    Minimal dispatcher: pick best ester-agent for task and return "who + why + next step"
    """
    body = request.get_json(silent=True) or {}
    task = (body.get("task") or body.get("text") or body.get("input") or "").strip()
    if not task:
        return jsonify({"ok": False, "error": "task_required"}), 400

    t = task.lower()
    # heuristics
    if any(k in t for k in ["health", "metrics", "metrik", "oshib", "tormoz", "slow", "lag"]):
        pick = "est.ops.health_mvp.v1"
        why = "Pokhozhe na diagnostiku/metriki/sostoyanie."
    elif any(k in t for k in ["nayd", "poisk", "rag", "tsitat", "dok", "kb", "profile", "knowledge"]):
        pick = "est.librarian.knowledge_mvp.v1"
        why = "Pokhozhe na poisk/znaniya/RAG/tsitirovanie."
    elif any(k in t for k in ["novyy agent", "yaml", "skelet", "scaffold", "builder", "otch", "report", "manifest"]):
        pick = "est.builder.suite_mvp.v1"
        why = "Pokhozhe na sborku/manifest/chernovik agenta."
    else:
        pick = "est.dispatcher.synergy_mvp.v1"
        why = "Zadacha obschaya — snachala dispetcherizatsiya/utochnenie."

    next_step = {
        "endpoint": "POST /mvp/agents/suite/run",
        "body": {"agent": pick, "text": task, "dry_run": True},
    }
    return jsonify({"ok": True, "assigned": pick, "why": why, "next": next_step})


@bp.get("/mvp/autonomy/status")
def autonomy_status():
    """
    MVP status wrapper. Does NOT enable background autonomy by itself.
    """
    return jsonify(
        {
            "ok": True,
            "enabled": str(os.getenv("ESTER_AUTONOMY_ENABLED", "0")).strip() in ("1", "true", "True"),
            "ticks": int(_STATE.get("autonomy_ticks", 0)),
            "last": _STATE.get("last_autonomy"),
        }
    )


@bp.post("/mvp/autonomy/tick")
def autonomy_tick():
    """
    MVP tick: one step of “self-driven needs”.
    By default: produces an advice (synergy) and returns it, without forcing any dangerous action.
    """
    body = request.get_json(silent=True) or {}
    reason = (body.get("reason") or "manual_tick").strip()
    enabled = str(os.getenv("ESTER_AUTONOMY_ENABLED", "0")).strip() in ("1", "true", "True")

    _STATE["autonomy_ticks"] = int(_STATE.get("autonomy_ticks", 0)) + 1

    # Minimal: create a “need” occasionally, but only as advice (no silent execution).
    # You can later wire this into real volition/memory triggers.
    need_task = body.get("task")
    if not isinstance(need_task, str) or not need_task.strip():
        if _STATE["autonomy_ticks"] % 3 == 1:
            need_task = "U menya oshibki/tormoza — prover health/metrics i sostoyanie limitov ingest"
        else:
            need_task = "Prover, vse li ok, i esli net — predlozhi sleduyuschiy shag"

    # Call synergy advice internally
    client = current_app.test_client()
    adv = client.post("/synergy/assign/advice", json={"task": need_task})
    adv_json = adv.get_json(silent=True)

    result = {
        "ok": True,
        "enabled": enabled,
        "reason": reason,
        "task": need_task,
        "advice": adv_json,
        "note": "MVP tick returns advice only (no silent suite execution).",
        "ts": _utc_iso(),
    }
    _STATE["last_autonomy"] = result
    return jsonify(result)


def register(app):
    app.register_blueprint(bp)
    return True