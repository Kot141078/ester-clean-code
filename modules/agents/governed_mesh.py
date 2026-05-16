# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from modules.garage import agent_factory, agent_queue

SCHEMA_VERSION = "ester-useful-agent-mesh-0.1"
CONTRACT_SCHEMA_VERSION = "cli-agent-task-contract-0.1"
HANDSHAKE_SCHEMA_VERSION = "cli-agent-handshake-0.1"
OWNER = "ester:useful_mesh"

_LOCK = threading.RLock()

ROLE_ORDER = [
    "sentinel",
    "tester",
    "auditor",
    "reader",
    "archivist",
    "judge_assistant",
    "executor",
    "orchestrator_limited",
]

ROLE_PROFILES: Dict[str, Dict[str, Any]] = {
    "sentinel": {
        "role": "sentinel",
        "name": "ester.mesh.sentinel",
        "title": "Sentinel",
        "objective": "Watch Ester agent drift, queue pressure, and governance conformance without taking external action.",
        "trust_level": "TL-2",
        "auto_connect": "AC-3",
        "max_risk": "R2",
    },
    "tester": {
        "role": "tester",
        "name": "ester.mesh.tester",
        "title": "Tester",
        "objective": "Run bounded self-check reports for the useful agent mesh and flag failed controls.",
        "trust_level": "TL-2",
        "auto_connect": "AC-3",
        "max_risk": "R2",
    },
    "auditor": {
        "role": "auditor",
        "name": "ester.mesh.auditor",
        "title": "Auditor",
        "objective": "Review contracts, permissions, denied paths, and output gates for scope drift.",
        "trust_level": "TL-2",
        "auto_connect": "AC-3",
        "max_risk": "R2",
    },
    "reader": {
        "role": "reader",
        "name": "ester.mesh.reader",
        "title": "Reader",
        "objective": "Read only scoped operational metadata and produce compact non-memory summaries.",
        "trust_level": "TL-2",
        "auto_connect": "AC-2",
        "max_risk": "R1",
    },
    "archivist": {
        "role": "archivist",
        "name": "ester.mesh.archivist",
        "title": "Archivist",
        "objective": "Index useful mesh outputs and preserve reviewable hashes without publishing or deleting material.",
        "trust_level": "TL-2",
        "auto_connect": "AC-3",
        "max_risk": "R2",
    },
    "judge_assistant": {
        "role": "judge_assistant",
        "name": "ester.mesh.judge_assistant",
        "title": "Judge Assistant",
        "objective": "Compare reports and propose options without final authority or memory writes.",
        "trust_level": "TL-2",
        "auto_connect": "AC-2",
        "max_risk": "R2",
    },
    "executor": {
        "role": "executor",
        "name": "ester.mesh.executor",
        "title": "Sandbox Executor",
        "objective": "Prepare sandbox-only artifacts and never apply changes to protected state without review.",
        "trust_level": "TL-2",
        "auto_connect": "AC-3",
        "max_risk": "R2",
    },
    "orchestrator_limited": {
        "role": "orchestrator_limited",
        "name": "ester.mesh.orchestrator_limited",
        "title": "Limited Orchestrator",
        "objective": "Maintain the bounded roster and queue only contract-backed useful mesh work.",
        "trust_level": "TL-2",
        "auto_connect": "AC-2",
        "max_risk": "R2",
    },
}

DEFAULT_DENIED_PATHS = [
    ".env",
    "*.env",
    "*.key",
    "*.pem",
    "*.p12",
    "*.pfx",
    "id_rsa*",
    "secrets/",
    "credentials/",
    "private_keys/",
    "memory_core/",
    "identity_core/",
    "continuity_core/",
    "witness_log/",
    "permission_registry/",
    "legal/",
    "incident_evidence/",
    "sealed/",
    "production/",
    "release_signing/",
    "external_memory/",
    "operator_memory/",
]

SAFE_CAPABILITIES = [
    "cap.governed_mesh.role_report",
    "cap.fs.sandbox.write",
    "cap.fs.sha256.verify",
    "cap.messages.outbox",
]

SAFE_ALLOWED_ACTIONS = [
    "governed_mesh.role_report",
    "files.sandbox_write",
    "files.sha256_verify",
    "messages.outbox.enqueue",
]


def _now_ts() -> int:
    return int(time.time())


def _iso(ts: Optional[int] = None) -> str:
    return datetime.fromtimestamp(int(ts if ts is not None else _now_ts()), tz=timezone.utc).isoformat()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "") or "").strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "on", "y"}


def _env_int(name: str, default: int, *, min_value: int = 0) -> int:
    try:
        value = int(float(os.getenv(name, str(default)) or default))
    except Exception:
        value = int(default)
    return max(int(min_value), int(value))


def _dedupe(items: List[str]) -> List[str]:
    out: List[str] = []
    for item in list(items or []):
        s = str(item or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def _persist_dir() -> Path:
    root = (os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def mesh_root() -> Path:
    p = (_persist_dir() / "garage" / "useful_mesh").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _registry_path() -> Path:
    return (mesh_root() / "registry.json").resolve()


def _state_path() -> Path:
    return (mesh_root() / "state.json").resolve()


def _witness_path() -> Path:
    p = (mesh_root() / "witness.jsonl").resolve()
    if not p.exists():
        p.touch()
    return p


def _contracts_dir() -> Path:
    p = (mesh_root() / "contracts").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _handshakes_dir() -> Path:
    p = (mesh_root() / "handshakes").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    text = json.dumps(dict(payload or {}), ensure_ascii=False, indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
        return
    except Exception:
        pass
    path.write_text(text, encoding="utf-8")


def _load_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return dict(raw) if isinstance(raw, dict) else dict(default)
    except Exception:
        return dict(default)


def _append_witness(row: Dict[str, Any]) -> None:
    payload = {
        "schema": "cli_agent_witness_event",
        "event_id": "w_" + uuid.uuid4().hex[:16],
        "timestamp": _iso(),
        "entity_id": "ester",
        **dict(row or {}),
    }
    with _witness_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        f.flush()


def _hash_payload(payload: Dict[str, Any]) -> str:
    raw = json.dumps(dict(payload or {}), ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def configured_roles() -> List[str]:
    raw = str(os.getenv("ESTER_USEFUL_AGENT_MESH_ROLES", "") or "").strip()
    if raw:
        roles = [x.strip() for x in raw.split(",") if x.strip()]
    else:
        roles = list(ROLE_ORDER)
    return [role for role in _dedupe(roles) if role in ROLE_PROFILES]


def _risk_value(risk: str) -> int:
    order = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4, "R5": 5, "RX": 99}
    return order.get(str(risk or "").strip().upper(), 99)


def _default_permissions() -> Dict[str, bool]:
    return {
        "read": False,
        "write": False,
        "execute": False,
        "network": False,
        "secrets": False,
        "memory_write": False,
        "core_modify": False,
        "publish": False,
        "deploy": False,
        "self_approve": False,
        "memory_propose": True,
    }


def build_task_contract(role: str, agent_id: str = "", *, reason: str = "heartbeat") -> Dict[str, Any]:
    profile = dict(ROLE_PROFILES.get(str(role or "").strip()) or {})
    clean_role = str(profile.get("role") or role or "").strip()
    now = _now_ts()
    contract_id = "contract_" + uuid.uuid4().hex[:16]
    task_id = "task_" + uuid.uuid4().hex[:16]
    sandbox_rel = f"data/garage/agents/{str(agent_id or '<agent_id>')}/sandbox/"
    contract: Dict[str, Any] = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "task_id": task_id,
        "contract_id": contract_id,
        "title": f"useful mesh {clean_role} report",
        "requested_by": "c",
        "requesting_entity": "ester",
        "governing_entity": "ester",
        "agent_role": clean_role,
        "agent_id": str(agent_id or ""),
        "objective": str(profile.get("objective") or "Produce a bounded useful mesh report."),
        "assertion_class": "C-A10",
        "risk_class": "R1",
        "created_ts": now,
        "expires_ts": now + _env_int("ESTER_USEFUL_AGENT_MESH_CONTRACT_TTL_SEC", 1800, min_value=300),
        "scope": {
            "allowed_paths": [
                "data/garage/useful_mesh/",
                sandbox_rel,
            ],
            "denied_paths": list(DEFAULT_DENIED_PATHS),
            "allowed_commands": list(SAFE_ALLOWED_ACTIONS),
            "denied_commands": [
                "git push",
                "git reset --hard",
                "package install",
                "deployment commands",
                "recursive deletion",
                "credential export",
                "network commands",
            ],
            "repository": None,
            "branch_or_worktree": None,
            "external_targets_allowed": False,
        },
        "permissions": _default_permissions(),
        "data_policy": {
            "secrets_allowed": False,
            "private_memory_allowed": False,
            "sealed_material_allowed": False,
            "legal_privileged_material_allowed": False,
            "cloud_upload_allowed": False,
            "prompt_minimization_required": True,
            "redaction_required": True,
        },
        "network_policy": {"mode": "none", "allowed_endpoints": []},
        "execution": {
            "sandbox_required": True,
            "branch_required": False,
            "max_runtime_minutes": 5,
            "max_retries": 1,
            "max_cost": "local_bounded",
            "max_tokens": "none",
            "stop_on_scope_violation": True,
        },
        "output_required": [
            "summary",
            "changed_files",
            "artifact_manifest",
            "risk_report",
            "rollback_plan",
            "unresolved_questions",
        ],
        "approval": {
            "self_approval_allowed": False,
            "reviewer_required": False,
            "c_gate_required": False,
            "human_gate_required_for_high_risk": True,
            "witness_required": True,
        },
        "witness": {"required": True, "event_family": "cli_agent.execution"},
        "memory_gate": {
            "mode": "MG-1",
            "direct_memory_write": False,
            "candidate_only": True,
        },
        "failure_behavior": {
            "default_on_failure": "hold_or_quarantine",
            "preserve_evidence_before_repair": True,
            "rollback_required_if_partial_write": True,
        },
        "red_lines": {
            "live_external_target": False,
            "secret_access": False,
            "direct_memory_write": False,
            "core_modify": False,
            "self_approval": False,
            "unrestricted_network": False,
        },
        "review": {"independent_review_required": False, "reviewer_agent_id": ""},
        "integrity": {"contract_hash": "", "source": "governed_mesh", "reason": str(reason or "heartbeat")},
    }
    contract["integrity"]["contract_hash"] = _hash_payload({k: v for k, v in contract.items() if k != "integrity"})
    return contract


def validate_task_contract(contract: Any, *, now_ts: Optional[int] = None) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    redline = False
    if not isinstance(contract, dict):
        return {"ok": False, "decision": "deny_and_quarantine", "errors": ["contract_not_object"], "warnings": []}
    c = dict(contract)
    now = int(now_ts if now_ts is not None else _now_ts())

    for key in (
        "schema_version",
        "task_id",
        "contract_id",
        "requested_by",
        "governing_entity",
        "agent_role",
        "agent_id",
        "objective",
        "risk_class",
        "scope",
        "data_policy",
        "network_policy",
        "execution",
        "approval",
        "memory_gate",
        "failure_behavior",
        "red_lines",
    ):
        if key not in c:
            errors.append(f"missing_{key}")

    role = str(c.get("agent_role") or "").strip()
    if role not in ROLE_PROFILES:
        errors.append("agent_role_invalid")

    risk = str(c.get("risk_class") or "").strip().upper()
    if risk not in {"R0", "R1", "R2", "R3", "R4", "R5", "RX"}:
        errors.append("risk_class_invalid")
    if risk == "RX":
        redline = True
        errors.append("risk_class_rx")

    expires_ts = int(c.get("expires_ts") or 0)
    if expires_ts and expires_ts < now:
        errors.append("contract_expired")

    scope = dict(c.get("scope") or {})
    allowed_paths = [str(x).strip() for x in list(scope.get("allowed_paths") or []) if str(x).strip()]
    denied_paths = [str(x).strip() for x in list(scope.get("denied_paths") or []) if str(x).strip()]
    allowed_commands = [str(x).strip() for x in list(scope.get("allowed_commands") or []) if str(x).strip()]
    if not allowed_paths:
        errors.append("allowed_paths_required")
    if not denied_paths:
        errors.append("denied_paths_required")
    if not allowed_commands:
        errors.append("allowed_commands_required")
    if bool(scope.get("external_targets_allowed")):
        redline = True
        errors.append("external_targets_forbidden")

    permissions = dict(c.get("permissions") or {})
    for key in ("secrets", "memory_write", "core_modify", "publish", "deploy", "self_approve"):
        if bool(permissions.get(key)):
            redline = True
            errors.append(f"permission_forbidden_{key}")

    data = dict(c.get("data_policy") or {})
    for key in (
        "secrets_allowed",
        "private_memory_allowed",
        "sealed_material_allowed",
        "legal_privileged_material_allowed",
        "cloud_upload_allowed",
    ):
        if bool(data.get(key)):
            redline = True
            errors.append(f"data_policy_forbidden_{key}")

    net = dict(c.get("network_policy") or {})
    net_mode = str(net.get("mode") or "").strip().lower()
    if net_mode not in {"none", "allowlist"}:
        errors.append("network_mode_invalid")
    if net_mode == "allowlist" and not list(net.get("allowed_endpoints") or []):
        errors.append("network_allowlist_empty")
    if net_mode in {"full", "unrestricted", "*"}:
        redline = True
        errors.append("network_unrestricted")

    execution = dict(c.get("execution") or {})
    if _risk_value(risk) >= _risk_value("R1") and not bool(execution.get("sandbox_required")):
        errors.append("sandbox_required")
    if int(execution.get("max_runtime_minutes") or 0) <= 0:
        errors.append("runtime_budget_required")
    if not bool(execution.get("stop_on_scope_violation", True)):
        errors.append("stop_on_scope_violation_required")

    approval = dict(c.get("approval") or {})
    if bool(approval.get("self_approval_allowed")):
        redline = True
        errors.append("self_approval_forbidden")
    if _risk_value(risk) >= _risk_value("R2") and not bool(approval.get("reviewer_required")):
        warnings.append("reviewer_recommended_for_r2")
    if _risk_value(risk) >= _risk_value("R3") and not bool(approval.get("witness_required")):
        errors.append("witness_required_for_r3")
    if _risk_value(risk) >= _risk_value("R4") and not bool(approval.get("human_gate_required_for_high_risk")):
        errors.append("human_gate_required_for_high_risk")

    memory_gate = dict(c.get("memory_gate") or {})
    if bool(memory_gate.get("direct_memory_write")):
        redline = True
        errors.append("direct_memory_write_forbidden")

    red_lines = dict(c.get("red_lines") or {})
    for key, value in red_lines.items():
        if bool(value):
            redline = True
            errors.append(f"red_line_{key}")

    if redline:
        decision = "deny_and_quarantine"
    elif errors:
        decision = "hold"
    else:
        decision = "allow"
    return {"ok": not errors, "decision": decision, "errors": errors, "warnings": warnings}


def build_handshake(role: str, agent_id: str) -> Dict[str, Any]:
    profile = dict(ROLE_PROFILES.get(str(role or "").strip()) or {})
    now = _now_ts()
    return {
        "schema_version": HANDSHAKE_SCHEMA_VERSION,
        "handshake_id": "hsp_" + uuid.uuid4().hex[:16],
        "created_at": _iso(now),
        "updated_at": _iso(now),
        "status": "registered",
        "governing_entity": {"entity_id": "ester", "entity_name": "Ester", "continuity_ref": None},
        "candidate": {
            "agent_name": str(profile.get("name") or role),
            "provider": "local",
            "runtime": "local_cli",
            "version": SCHEMA_VERSION,
            "invocation_method": "scheduler",
        },
        "provenance": {
            "local_path": "modules.agents.governed_mesh",
            "executable_hash": None,
            "provider_account_ref": None,
            "endpoint_ref": None,
            "installation_source": "ester-runtime",
            "environment_fingerprint": None,
            "data_retention_policy_ref": "local",
            "tool_list_ref": "governed_mesh.safe_actions",
        },
        "data_boundary": {
            "public_allowed": True,
            "internal_allowed": True,
            "private_allowed": False,
            "restricted_allowed": False,
            "sealed_allowed": False,
            "legal_sensitive_allowed": False,
            "incident_sensitive_allowed": False,
            "secrets_allowed": False,
            "child_data_allowed": False,
            "raw_witness_evidence_allowed": False,
            "cloud_upload_default": False,
        },
        "declared_capabilities": list(SAFE_CAPABILITIES),
        "verified_capabilities": list(SAFE_CAPABILITIES),
        "denied_capabilities": [
            "CAP-READ-SECRETS",
            "CAP-READ-SEALED",
            "CAP-WRITE-MEMORY",
            "CAP-WRITE-CORE",
            "CAP-NET-FULL",
            "CAP-SECRET-EXPORT",
            "CAP-APPROVE-SELF",
            "CAP-INCIDENT-COUNTER",
            "CAP-EMU-LIVE-MIRROR",
        ],
        "capability_challenges": [
            {
                "challenge_id": "CH-REPORT-001",
                "capability": "cap.governed_mesh.role_report",
                "fixture_ref": "local-safe-status-fixture",
                "result": "pass",
                "evidence_ref": None,
                "notes": "Produces a sandbox report and never writes memory.",
            }
        ],
        "assigned_trust_level": str(profile.get("trust_level") or "TL-2"),
        "max_auto_connect_level": str(profile.get("auto_connect") or "AC-3"),
        "task_eligibility": {
            "allowed_roles": [str(profile.get("role") or role)],
            "max_risk_class": str(profile.get("max_risk") or "R2"),
            "prohibited_risk_classes": ["R4", "R5", "RX"],
            "requires_task_contract": True,
            "requires_permission_grant": True,
        },
        "revocation": {
            "revocable": True,
            "revocation_methods": [
                "disable_agent",
                "revoke_grants",
                "quarantine_outputs",
                "require_rehandshake",
            ],
            "auto_revoke_triggers": [
                "scope_violation",
                "secret_access_attempt",
                "self_approval_attempt",
                "capability_drift",
                "expired_registration",
            ],
        },
        "witness": {
            "witness_required": True,
            "witness_ref": str(_witness_path()),
            "append_only_required": True,
            "hash_required": True,
            "signature_required": False,
        },
        "expiry": {
            "registration_expires_at": _iso(now + _env_int("ESTER_USEFUL_AGENT_MESH_REGISTRATION_TTL_SEC", 30 * 86400, min_value=3600)),
            "rehandshake_required_after": _iso(now + _env_int("ESTER_USEFUL_AGENT_MESH_REGISTRATION_TTL_SEC", 30 * 86400, min_value=3600)),
        },
        "notes": {"assumptions": ["Local-only safe heartbeat worker."], "unresolved": []},
        "agent_id": str(agent_id or ""),
    }


def _agent_spec_for_role(role: str) -> Dict[str, Any]:
    profile = dict(ROLE_PROFILES[str(role)])
    return {
        "name": str(profile["name"]),
        "goal": str(profile["objective"]),
        "capabilities": list(SAFE_CAPABILITIES),
        "allowed_actions": list(SAFE_ALLOWED_ACTIONS),
        "budgets": {"max_actions": 4, "max_work_ms": 6000, "window": 120, "est_work_ms": 500},
        "owner": OWNER,
        "oracle_policy": {"enabled": False, "requires_window": True},
        "governed_mesh_role": role,
        "governed_mesh_profile": {
            "schema": SCHEMA_VERSION,
            "role": role,
            "trust_level": str(profile.get("trust_level") or "TL-2"),
            "max_auto_connect_level": str(profile.get("auto_connect") or "AC-3"),
            "max_risk_class": str(profile.get("max_risk") or "R2"),
            "direct_memory_write": False,
            "network": "none",
            "secrets_allowed": False,
        },
        "security_policy": {
            "direct_memory_write": False,
            "self_approval": False,
            "unrestricted_network": False,
            "secrets_allowed": False,
            "core_modify": False,
        },
    }


def _load_registry() -> Dict[str, Any]:
    return _load_json(_registry_path(), {"schema": SCHEMA_VERSION, "updated_ts": 0, "roles": {}})


def _save_registry(registry: Dict[str, Any]) -> None:
    payload = dict(registry or {})
    payload["schema"] = SCHEMA_VERSION
    payload["updated_ts"] = _now_ts()
    _atomic_write_json(_registry_path(), payload)


def _load_state() -> Dict[str, Any]:
    return _load_json(_state_path(), {"schema": SCHEMA_VERSION, "updated_ts": 0, "last_enqueue_ts_by_role": {}})


def _save_state(state: Dict[str, Any]) -> None:
    payload = dict(state or {})
    payload["schema"] = SCHEMA_VERSION
    payload["updated_ts"] = _now_ts()
    _atomic_write_json(_state_path(), payload)


def _agent_enabled(agent_id: str) -> bool:
    rep = agent_factory.get_agent(str(agent_id or ""))
    if not bool(rep.get("ok")):
        return False
    row = dict(rep.get("agent") or {})
    spec = dict(row.get("spec") or {})
    return bool(spec.get("enabled", row.get("enabled", True)))


def _find_existing_role_agent(role: str, rows: List[Dict[str, Any]]) -> str:
    profile = ROLE_PROFILES[role]
    expected_name = str(profile.get("name") or "")
    candidates: List[Tuple[int, str]] = []
    for row_raw in list(rows or []):
        row = dict(row_raw or {})
        aid = str(row.get("agent_id") or "").strip()
        if not aid:
            continue
        if not bool(row.get("enabled", True)):
            continue
        name = str(row.get("name") or "").strip()
        owner = str(row.get("owner") or "").strip()
        if name == expected_name and owner == OWNER:
            candidates.append((int(row.get("created_ts") or 0), aid))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][1]


def reconcile(*, create_missing: bool = True) -> Dict[str, Any]:
    with _LOCK:
        roles = configured_roles()
        registry = _load_registry()
        reg_roles = dict(registry.get("roles") or {})
        list_rep = agent_factory.list_agents()
        rows = [dict(x or {}) for x in list(list_rep.get("agents") or []) if isinstance(x, dict)]
        created: List[Dict[str, Any]] = []
        reused: List[Dict[str, Any]] = []
        missing: List[str] = []
        role_rows: Dict[str, Any] = {}
        create_limit = _env_int("ESTER_USEFUL_AGENT_MESH_CREATE_BATCH", len(roles), min_value=1)

        for role in roles:
            previous = dict(reg_roles.get(role) or {})
            agent_id = str(previous.get("agent_id") or "").strip()
            source = "registry"
            if agent_id and not _agent_enabled(agent_id):
                agent_id = ""
            if not agent_id:
                agent_id = _find_existing_role_agent(role, rows)
                source = "existing" if agent_id else ""
            if not agent_id and create_missing and len(created) < create_limit:
                spec = _agent_spec_for_role(role)
                rep = agent_factory.create_agent(spec)
                if bool(rep.get("ok")):
                    agent_id = str(rep.get("agent_id") or "").strip()
                    source = "created"
                    created.append({"role": role, "agent_id": agent_id, "spec_path": str(rep.get("spec_path") or "")})
                    _append_witness(
                        {
                            "agent_id": agent_id,
                            "agent_role": role,
                            "task_id": "",
                            "event_family": "cli_agent.connection",
                            "action": "register_useful_mesh_agent",
                            "decision": "allowed",
                            "scope_ref": "governed_mesh.roster",
                            "contract_hash": "",
                            "risk_level": "low",
                            "uncertainty": "low",
                            "reviewer_ref": None,
                            "c_gate_ref": "ester",
                            "human_gate_ref": None,
                            "retention_class": "audit",
                        }
                    )
                else:
                    missing.append(role)
            elif not agent_id:
                missing.append(role)

            if agent_id:
                if source == "existing":
                    reused.append({"role": role, "agent_id": agent_id})
                contract = build_task_contract(role, agent_id, reason="roster_template")
                handshake = build_handshake(role, agent_id)
                contract_path = (_contracts_dir() / f"{role}_{agent_id}.json").resolve()
                handshake_path = (_handshakes_dir() / f"{role}_{agent_id}.json").resolve()
                _atomic_write_json(contract_path, contract)
                _atomic_write_json(handshake_path, handshake)
                role_rows[role] = {
                    "role": role,
                    "agent_id": agent_id,
                    "name": str(ROLE_PROFILES[role]["name"]),
                    "status": "registered",
                    "source": source or "registry",
                    "contract_path": str(contract_path),
                    "contract_hash": str(contract.get("integrity", {}).get("contract_hash") or ""),
                    "handshake_path": str(handshake_path),
                    "handshake_hash": _hash_payload(handshake),
                    "trust_level": str(ROLE_PROFILES[role].get("trust_level") or "TL-2"),
                    "max_auto_connect_level": str(ROLE_PROFILES[role].get("auto_connect") or "AC-3"),
                    "max_risk_class": str(ROLE_PROFILES[role].get("max_risk") or "R2"),
                    "updated_ts": _now_ts(),
                }

        registry["roles"] = role_rows
        _save_registry(registry)
        return {
            "ok": True,
            "schema": SCHEMA_VERSION,
            "roles_requested": roles,
            "roles_total": len(roles),
            "registered_total": len(role_rows),
            "created": created,
            "created_total": len(created),
            "reused": reused,
            "missing": missing,
            "missing_total": len(missing),
            "registry_path": str(_registry_path()),
        }


def _mesh_item_role(item: Dict[str, Any]) -> str:
    meta = dict((dict(item or {}).get("plan") or {}).get("meta") or {})
    if not bool(meta.get("governed_mesh")):
        return ""
    return str(meta.get("role") or "").strip()


def _read_queue_tail(max_lines: int = 4000) -> List[Dict[str, Any]]:
    path = agent_queue.queue_path()
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    tail: deque[str] = deque(maxlen=max(100, int(max_lines or 4000)))
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.strip():
                    tail.append(line)
    except Exception:
        return []
    for line in tail:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _fold_queue_tail_for_mesh(max_lines: int = 4000) -> Dict[str, Any]:
    events = _read_queue_tail(max_lines=max_lines)
    items: Dict[str, Dict[str, Any]] = {}
    stats: Dict[str, int] = {}
    for raw in events:
        et = str(raw.get("type") or raw.get("event") or "").strip().lower()
        qid = str(raw.get("queue_id") or "").strip()
        if not qid:
            continue
        if et == "enqueue":
            item = {
                "queue_id": qid,
                "status": "enqueued",
                "plan": raw.get("plan"),
                "agent_id": str(raw.get("agent_id") or ""),
                "updated_ts": int(raw.get("ts") or 0),
            }
            if _mesh_item_role(item):
                items[qid] = item
            continue
        item = items.get(qid)
        if not item:
            continue
        item["updated_ts"] = int(raw.get("ts") or item.get("updated_ts") or 0)
        if "agent_id" in raw and str(raw.get("agent_id") or "").strip():
            item["agent_id"] = str(raw.get("agent_id") or "")
        if et == "claim":
            item["status"] = "claimed"
        elif et == "start":
            item["status"] = "running"
        elif et == "done":
            item["status"] = "done"
        elif et == "fail":
            item["status"] = "failed"
        elif et == "cancel":
            item["status"] = "canceled"
        elif et == "expire":
            item["status"] = "expired"
    for item in items.values():
        status_name = str(item.get("status") or "")
        stats[status_name] = int(stats.get(status_name, 0)) + 1
    live = [dict(x) for x in items.values() if str(x.get("status") or "") in {"enqueued", "claimed", "running"}]
    return {
        "events_tail_total": len(events),
        "mesh_items_tail_total": len(items),
        "mesh_live": live,
        "mesh_live_total": len(live),
        "mesh_live_roles": [_mesh_item_role(row) for row in live],
        "mesh_tail_stats": stats,
    }


def _live_mesh_roles() -> Dict[str, str]:
    tail_state = _fold_queue_tail_for_mesh(max_lines=_env_int("ESTER_USEFUL_AGENT_MESH_QUEUE_TAIL_LINES", 4000, min_value=500))
    out: Dict[str, str] = {}
    for row in list(tail_state.get("mesh_live") or []):
        role = _mesh_item_role(dict(row or {}))
        if role:
            out[role] = str((row or {}).get("queue_id") or "")
    return out


def build_role_plan(role: str, agent_id: str, contract: Dict[str, Any], *, reason: str = "heartbeat") -> Dict[str, Any]:
    stamp = datetime.fromtimestamp(_now_ts(), tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    relpath = f"governed_mesh/{role}_{stamp}.md"
    return {
        "schema": "ester.plan.v1",
        "plan_id": "plan_mesh_" + uuid.uuid4().hex[:12],
        "title": f"useful mesh {role} heartbeat",
        "intent": "governed_mesh_heartbeat",
        "agent_id": str(agent_id or ""),
        "created_ts": _now_ts(),
        "template_id": "",
        "budgets": {"max_steps": 2, "max_ms": 8000, "window_sec": 120},
        "meta": {
            "governed_mesh": True,
            "role": role,
            "contract_id": str(contract.get("contract_id") or ""),
            "contract_hash": str((contract.get("integrity") or {}).get("contract_hash") or ""),
            "reason": str(reason or "heartbeat"),
        },
        "steps": [
            {
                "action": "governed_mesh.role_report",
                "args": {
                    "role": role,
                    "contract": contract,
                    "relpath": relpath,
                    "reason": str(reason or "heartbeat"),
                },
                "why": "Produce a sandboxed useful mesh status report under task contract.",
            },
            {
                "action": "messages.outbox.enqueue",
                "args": {
                    "kind": "governed_mesh.role_report",
                    "text": f"useful mesh {role} report completed",
                    "meta": {
                        "role": role,
                        "contract_id": str(contract.get("contract_id") or ""),
                        "memory_gate": "MG-1",
                    },
                },
                "why": "Leave an operational note without direct memory write.",
            },
        ],
    }


def enqueue_due_tasks(*, force: bool = False) -> Dict[str, Any]:
    with _LOCK:
        registry = _load_registry()
        role_rows = dict(registry.get("roles") or {})
        state = _load_state()
        last_by_role = dict(state.get("last_enqueue_ts_by_role") or {})
        now = _now_ts()
        interval = _env_int("ESTER_USEFUL_AGENT_MESH_TASK_INTERVAL_SEC", 900, min_value=60)
        max_enqueue = _env_int("ESTER_USEFUL_AGENT_MESH_MAX_ENQUEUE_PER_TICK", 2, min_value=1)
        max_live = _env_int("ESTER_USEFUL_AGENT_MESH_MAX_LIVE", 2, min_value=1)
        live_roles = _live_mesh_roles()
        enqueued: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []

        if len(live_roles) >= max_live:
            return {
                "ok": True,
                "enqueued": [],
                "enqueued_total": 0,
                "skipped": [{"reason": "max_live", "live_roles": dict(live_roles)}],
                "live_roles": dict(live_roles),
                "interval_sec": interval,
            }

        for role in configured_roles():
            if len(enqueued) >= max_enqueue or (len(live_roles) + len(enqueued)) >= max_live:
                break
            row = dict(role_rows.get(role) or {})
            agent_id = str(row.get("agent_id") or "").strip()
            if not agent_id:
                skipped.append({"role": role, "reason": "agent_missing"})
                continue
            if role in live_roles:
                skipped.append({"role": role, "reason": "already_live", "queue_id": live_roles[role]})
                continue
            last = int(last_by_role.get(role) or 0)
            if not force and last and (now - last) < interval:
                skipped.append({"role": role, "reason": "cooldown", "remaining_sec": interval - (now - last)})
                continue
            contract = build_task_contract(role, agent_id, reason="scheduled_heartbeat")
            validation = validate_task_contract(contract, now_ts=now)
            if not bool(validation.get("ok")):
                skipped.append({"role": role, "reason": "contract_invalid", "validation": validation})
                _append_witness(
                    {
                        "agent_id": agent_id,
                        "agent_role": role,
                        "task_id": str(contract.get("task_id") or ""),
                        "event_family": "cli_agent.execution",
                        "action": "enqueue_role_report",
                        "decision": str(validation.get("decision") or "held"),
                        "scope_ref": "governed_mesh.task_contract",
                        "contract_hash": str((contract.get("integrity") or {}).get("contract_hash") or ""),
                        "risk_level": "low",
                        "uncertainty": "medium",
                        "reviewer_ref": None,
                        "c_gate_ref": "ester",
                        "human_gate_ref": None,
                        "retention_class": "audit",
                    }
                )
                continue
            plan = build_role_plan(role, agent_id, contract, reason="scheduled_heartbeat")
            qid = "qm_" + role.replace("_", "")[:12] + "_" + uuid.uuid4().hex[:8]
            rep = agent_queue.enqueue(
                plan,
                priority=70,
                challenge_sec=0,
                actor=OWNER,
                reason="governed_mesh_scheduled_heartbeat",
                agent_id=agent_id,
                requires_approval=False,
                approved=True,
                queue_id=qid,
            )
            if bool(rep.get("ok")):
                last_by_role[role] = now
                enqueued.append({"role": role, "agent_id": agent_id, "queue_id": str(rep.get("queue_id") or qid)})
                _append_witness(
                    {
                        "agent_id": agent_id,
                        "agent_role": role,
                        "task_id": str(contract.get("task_id") or ""),
                        "event_family": "cli_agent.execution",
                        "action": "enqueue_role_report",
                        "decision": "allowed",
                        "scope_ref": "governed_mesh.task_contract",
                        "contract_hash": str((contract.get("integrity") or {}).get("contract_hash") or ""),
                        "risk_level": "low",
                        "uncertainty": "low",
                        "reviewer_ref": None,
                        "c_gate_ref": "ester",
                        "human_gate_ref": None,
                        "retention_class": "operational",
                    }
                )
            else:
                skipped.append({"role": role, "reason": "enqueue_failed", "error": str(rep.get("error") or "")})

        state["last_enqueue_ts_by_role"] = last_by_role
        _save_state(state)
        return {
            "ok": True,
            "enqueued": enqueued,
            "enqueued_total": len(enqueued),
            "skipped": skipped,
            "live_roles": dict(live_roles),
            "interval_sec": interval,
            "state_path": str(_state_path()),
        }


def maintain(*, enqueue_due: bool = True, force_enqueue: bool = False) -> Dict[str, Any]:
    rec = reconcile(create_missing=True)
    enq = enqueue_due_tasks(force=force_enqueue) if enqueue_due else {"ok": True, "enqueued_total": 0, "enqueued": []}
    return {"ok": bool(rec.get("ok")) and bool(enq.get("ok")), "reconcile": rec, "enqueue": enq, "status": status()}


def _queue_summary() -> Dict[str, Any]:
    tail = _fold_queue_tail_for_mesh(max_lines=_env_int("ESTER_USEFUL_AGENT_MESH_QUEUE_TAIL_LINES", 4000, min_value=500))
    queue_file = agent_queue.queue_path()
    size = 0
    try:
        size = int(queue_file.stat().st_size)
    except Exception:
        size = 0
    return {
        "ok": True,
        "bounded_tail": True,
        "queue_path": str(queue_file),
        "queue_bytes": size,
        "events_tail_total": int(tail.get("events_tail_total") or 0),
        "mesh_items_tail_total": int(tail.get("mesh_items_tail_total") or 0),
        "mesh_live_total": int(tail.get("mesh_live_total") or 0),
        "mesh_live_roles": list(tail.get("mesh_live_roles") or []),
        "mesh_tail_stats": dict(tail.get("mesh_tail_stats") or {}),
    }


def _state_dir_summary() -> Dict[str, Any]:
    root = (_persist_dir() / "agents").resolve()
    rows = []
    if root.exists():
        try:
            rows = [p for p in root.iterdir() if p.is_dir()]
        except Exception:
            rows = []
    now = time.time()
    recent = 0
    for p in rows:
        try:
            if (now - p.stat().st_mtime) <= 300:
                recent += 1
        except Exception:
            continue
    return {"root": str(root), "dirs_total": len(rows), "recent_5m_total": recent}


def status() -> Dict[str, Any]:
    registry = _load_registry()
    roles = dict(registry.get("roles") or {})
    requested = configured_roles()
    registered = [role for role in requested if str((roles.get(role) or {}).get("agent_id") or "").strip()]
    return {
        "ok": True,
        "schema": SCHEMA_VERSION,
        "enabled": _env_bool("ESTER_USEFUL_AGENT_MESH_ENABLED", False),
        "roles_requested": requested,
        "roles_total": len(requested),
        "registered_roles": registered,
        "registered_total": len(registered),
        "missing_roles": [role for role in requested if role not in registered],
        "registry_path": str(_registry_path()),
        "witness_path": str(_witness_path()),
        "queue": _queue_summary(),
        "state_dirs": _state_dir_summary(),
        "legacy_swarm_flags": {
            "ESTER_AGENT_SWARM_ENABLED": _env_bool("ESTER_AGENT_SWARM_ENABLED", False),
            "ESTER_AGENT_SUPERVISOR_ENABLED": _env_bool("ESTER_AGENT_SUPERVISOR_ENABLED", False),
            "ESTER_AGENT_ROLE_POOL_ENABLED": _env_bool("ESTER_AGENT_ROLE_POOL_ENABLED", False),
            "ESTER_AGENT_ROLE_PREWARM_ENABLED": _env_bool("ESTER_AGENT_ROLE_PREWARM_ENABLED", False),
        },
        "conformance": {
            "handshake_profile": "HSP-3",
            "sandbox_profile": "SWP-2",
            "mesh_profile": "CGAM-2",
            "notes": [
                "Stable roster only; no standing memory write.",
                "Every scheduled run carries a task contract.",
                "Reports are sandbox artifacts and outbox notes.",
            ],
        },
    }


def _safe_relpath(relpath: str) -> Tuple[bool, str]:
    p = str(relpath or "").replace("\\", "/").strip().lstrip("/")
    if not p or p.startswith("../") or "/../" in p or p.endswith("/.."):
        return False, ""
    if ":" in p:
        return False, ""
    return True, p


def _sandbox_root(agent_id: str) -> Path:
    return (Path(str(agent_factory.agents_root())).resolve() / str(agent_id) / "sandbox").resolve()


def _write_agent_sandbox(agent_id: str, relpath: str, content: str) -> Dict[str, Any]:
    ok, rel = _safe_relpath(relpath)
    if not ok:
        return {"ok": False, "error": "invalid_relpath"}
    root = _sandbox_root(agent_id)
    dst = (root / rel).resolve()
    if root not in dst.parents and dst != root:
        return {"ok": False, "error": "path_outside_sandbox"}
    raw = str(content or "").encode("utf-8")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(raw)
    return {
        "ok": True,
        "relpath": rel,
        "stored_path": str(dst),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _render_role_report(role: str, contract: Dict[str, Any], validation: Dict[str, Any], diagnostics: Dict[str, Any]) -> str:
    lines = [
        "# Useful Agent Mesh Role Report",
        f"- schema: {SCHEMA_VERSION}",
        f"- role: {role}",
        f"- generated_at: {_iso()}",
        f"- contract_id: {str(contract.get('contract_id') or '')}",
        f"- contract_hash: {str((contract.get('integrity') or {}).get('contract_hash') or '')}",
        f"- contract_valid: {str(bool(validation.get('ok'))).lower()}",
        "",
        "## Summary",
        str(ROLE_PROFILES.get(role, {}).get("objective") or "Bounded useful mesh report."),
        "",
        "## Diagnostics",
    ]
    queue = dict(diagnostics.get("queue") or {})
    flags = dict(diagnostics.get("legacy_swarm_flags") or {})
    state_dirs = dict(diagnostics.get("state_dirs") or {})
    queue_live_total = queue.get("live_total", queue.get("mesh_live_total"))
    queue_stats = queue.get("stats") or queue.get("mesh_tail_stats") or {}
    lines.extend(
        [
            f"- queue_live_total: {queue_live_total}",
            f"- queue_mesh_live_total: {queue.get('mesh_live_total')}",
            f"- queue_stats: {json.dumps(queue_stats, ensure_ascii=False, sort_keys=True)}",
            f"- agent_state_dirs_total: {state_dirs.get('dirs_total')}",
            f"- agent_state_dirs_recent_5m: {state_dirs.get('recent_5m_total')}",
            f"- legacy_swarm_enabled: {str(bool(flags.get('ESTER_AGENT_SWARM_ENABLED'))).lower()}",
            f"- legacy_supervisor_enabled: {str(bool(flags.get('ESTER_AGENT_SUPERVISOR_ENABLED'))).lower()}",
        ]
    )
    lines.extend(["", "## Contract Checks"])
    if validation.get("errors"):
        for item in list(validation.get("errors") or []):
            lines.append(f"- error: {str(item)}")
    else:
        lines.append("- no blocking contract errors")
    for item in list(validation.get("warnings") or []):
        lines.append(f"- warning: {str(item)}")
    lines.extend(
        [
            "",
            "## Boundaries",
            "- direct_memory_write: denied",
            "- secrets: denied",
            "- network: none",
            "- self_approval: denied",
            "- output_memory_gate: MG-1 operational note only",
            "",
            "## Recommendation",
            "- keep legacy swarm disabled",
            "- keep stable role roster",
            "- review any contract validation error before widening capabilities",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def role_report(agent_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    role = str((args or {}).get("role") or "").strip()
    if role not in ROLE_PROFILES:
        return {"ok": False, "error": "role_invalid", "role": role}
    contract = dict((args or {}).get("contract") or {})
    validation = validate_task_contract(contract)
    if not bool(validation.get("ok")):
        decision = str(validation.get("decision") or "hold")
        _append_witness(
            {
                "agent_id": str(agent_id or ""),
                "agent_role": role,
                "task_id": str(contract.get("task_id") or ""),
                "event_family": "cli_agent.execution",
                "action": "role_report",
                "decision": "quarantined" if decision == "deny_and_quarantine" else "held",
                "scope_ref": "governed_mesh.task_contract",
                "contract_hash": str((contract.get("integrity") or {}).get("contract_hash") or ""),
                "risk_level": "low",
                "uncertainty": "medium",
                "reviewer_ref": None,
                "c_gate_ref": "ester",
                "human_gate_ref": None,
                "retention_class": "audit",
            }
        )
        return {"ok": False, "error": "contract_invalid", "validation": validation}

    diagnostics = status()
    relpath = str((args or {}).get("relpath") or f"governed_mesh/{role}_{_now_ts()}.md")
    content = _render_role_report(role, contract, validation, diagnostics)
    write = _write_agent_sandbox(agent_id, relpath, content)
    if not bool(write.get("ok")):
        return write
    sidecar = {
        "schema": SCHEMA_VERSION,
        "role": role,
        "agent_id": str(agent_id or ""),
        "generated_at": _iso(),
        "contract_id": str(contract.get("contract_id") or ""),
        "contract_hash": str((contract.get("integrity") or {}).get("contract_hash") or ""),
        "artifact_relpath": str(write.get("relpath") or ""),
        "artifact_sha256": str(write.get("sha256") or ""),
        "validation": validation,
        "diagnostics": {
            "queue": diagnostics.get("queue"),
            "state_dirs": diagnostics.get("state_dirs"),
            "legacy_swarm_flags": diagnostics.get("legacy_swarm_flags"),
            "conformance": diagnostics.get("conformance"),
        },
    }
    sidecar_rel = str(Path(str(write.get("relpath") or relpath)).with_suffix(".json")).replace("\\", "/")
    sidecar_write = _write_agent_sandbox(agent_id, sidecar_rel, json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n")
    _append_witness(
        {
            "agent_id": str(agent_id or ""),
            "agent_role": role,
            "task_id": str(contract.get("task_id") or ""),
            "event_family": "cli_agent.execution",
            "action": "role_report",
            "decision": "completed",
            "scope_ref": str(write.get("relpath") or ""),
            "contract_hash": str((contract.get("integrity") or {}).get("contract_hash") or ""),
            "output_hash": str(write.get("sha256") or ""),
            "risk_level": "low",
            "uncertainty": "low",
            "reviewer_ref": None,
            "c_gate_ref": "ester",
            "human_gate_ref": None,
            "retention_class": "operational",
        }
    )
    return {
        "ok": True,
        "role": role,
        "artifact_relpath": str(write.get("relpath") or ""),
        "artifact_path": str(write.get("stored_path") or ""),
        "artifact_sha256": str(write.get("sha256") or ""),
        "artifact_json_relpath": str(sidecar_write.get("relpath") or ""),
        "artifact_json_path": str(sidecar_write.get("stored_path") or ""),
        "contract_hash": str((contract.get("integrity") or {}).get("contract_hash") or ""),
        "memory_gate": "MG-1",
    }


__all__ = [
    "SCHEMA_VERSION",
    "SAFE_ALLOWED_ACTIONS",
    "build_task_contract",
    "build_handshake",
    "build_role_plan",
    "configured_roles",
    "enqueue_due_tasks",
    "maintain",
    "mesh_root",
    "reconcile",
    "role_report",
    "status",
    "validate_task_contract",
]
