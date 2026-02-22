# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from modules.garage.agent_spec import AgentSpec
from modules.garage.templates import registry as templates_registry
try:
    from modules.runtime import integrity_verifier  # type: ignore
except Exception:  # pragma: no cover
    integrity_verifier = None  # type: ignore

_LOCK = threading.RLock()
_STRICT_ERR_STREAK = 0
_STRICT_DISABLED = False


def _persist_dir() -> Path:
    root = (os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _slot() -> str:
    raw = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if raw == "B" else "A"


def _env_int(name: str, default: int) -> int:
    try:
        return int(float(os.getenv(name, str(default)) or default))
    except Exception:
        return int(default)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "") or "").strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "on", "y"}


def _strict_fail_max() -> int:
    try:
        return max(1, int(os.getenv("ESTER_CAPS_STRICT_FAIL_MAX", "3") or "3"))
    except Exception:
        return 3


def _strict_enabled() -> bool:
    return bool(_slot() == "B" and (not _STRICT_DISABLED))


def _note_strict_success() -> None:
    global _STRICT_ERR_STREAK
    _STRICT_ERR_STREAK = 0


def _note_strict_exception(where: str, exc: Exception) -> Dict[str, Any]:
    global _STRICT_ERR_STREAK, _STRICT_DISABLED
    _STRICT_ERR_STREAK += 1
    if _STRICT_ERR_STREAK >= _strict_fail_max():
        _STRICT_DISABLED = True
        os.environ["ESTER_CAPS_STRICT_DISABLED"] = "1"
        os.environ["ESTER_CAPS_LAST_ROLLBACK_REASON"] = f"{where}:{exc.__class__.__name__}"
    return {
        "slot": _slot(),
        "strict_enabled": bool(_slot() == "B" and (not _STRICT_DISABLED)),
        "strict_disabled": bool(_STRICT_DISABLED),
        "strict_err_streak": int(_STRICT_ERR_STREAK),
        "strict_fail_max": int(_strict_fail_max()),
    }


def _clean_list(raw: Any) -> List[str]:
    out: List[str] = []
    for row in list(raw or []):
        s = str(row or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def _hash_list(values: List[str]) -> str:
    src = json.dumps(sorted(_clean_list(values)), ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    import hashlib

    return hashlib.sha256(src).hexdigest()


def _known_action_ids() -> set[str]:
    out: set[str] = set()
    try:
        from modules.thinking import action_registry

        if hasattr(action_registry, "list_action_ids") and callable(action_registry.list_action_ids):
            out.update(str(x).strip() for x in list(action_registry.list_action_ids() or []) if str(x).strip())
    except Exception:
        pass
    return out


def _journal_policy(
    *,
    allowed: bool,
    reason_code: str,
    reason: str,
    metadata: Dict[str, Any],
) -> None:
    try:
        from modules.volition import journal as volition_journal
    except Exception:
        return
    row = {
        "id": "vol_manual_" + uuid.uuid4().hex,
        "ts": int(time.time()),
        "chain_id": str((metadata or {}).get("chain_id") or ""),
        "step": "agent.create",
        "actor": str((metadata or {}).get("actor") or "ester"),
        "intent": "agent_create",
        "action_kind": "agent.create",
        "needs": ["agent.create"],
        "allowed": bool(allowed),
        "reason_code": str(reason_code or ("ALLOW" if allowed else "DENY")),
        "reason": str(reason or ""),
        "slot": _slot(),
        "metadata": dict(metadata or {}),
        "action_id": "agent.create",
        "decision": ("allow" if allowed else "deny"),
        "policy_hit": "agent.create",
        "duration_ms": 0,
    }
    try:
        volition_journal.append(row)
    except Exception:
        return


def resolve_allowlist_for_spec(spec: Any, *, slot_override: str = "") -> Dict[str, Any]:
    src = dict(spec or {})
    slot = str(slot_override or _slot()).strip().upper()
    strict = bool(slot == "B")

    template_id = str(src.get("template_id") or "").strip()
    allowed_input = _clean_list(src.get("allowed_actions") or [])
    caps_requested = _clean_list(src.get("capabilities_effective") or src.get("capabilities") or [])

    warnings: List[str] = []
    source = "legacy"
    computed: List[str] = []
    caps_base: List[str] = []
    caps_effective: List[str] = []

    from modules.thinking import action_registry

    if template_id:
        tpl = templates_registry.get_template(template_id)
        if not isinstance(tpl, dict) or (not tpl):
            return {"ok": False, "error": "template_not_found", "error_code": "TEMPLATE_NOT_FOUND"}
        caps_base = _clean_list(tpl.get("capabilities") or [])
        if caps_base:
            source = "template.capabilities"
            if caps_requested:
                invalid_caps = [x for x in caps_requested if x not in caps_base]
                if invalid_caps:
                    if strict:
                        return {
                            "ok": False,
                            "error": "capability_escalation",
                            "error_code": "CAPABILITY_ESCALATION",
                            "details": {"invalid_capabilities": invalid_caps},
                        }
                    warnings.append("capabilities_clamped")
                    caps_effective = [x for x in caps_requested if x in caps_base]
                    if not caps_effective:
                        caps_effective = list(caps_base)
                else:
                    caps_effective = list(caps_requested)
            else:
                caps_effective = list(caps_base)
            op = dict(src.get("oracle_policy") or {})
            enable_oracle = bool(op.get("enabled")) or bool(op.get("allow_remote"))
            enable_comm = bool((dict(src.get("comm_policy") or {})).get("enabled"))
            caps_effective, disabled_caps = templates_registry.capability_policy_filter(
                caps_effective,
                enable_oracle=enable_oracle,
                enable_comm=enable_comm,
            )
            if disabled_caps:
                warnings.append("capabilities_disabled_by_policy")
            try:
                computed = templates_registry.resolve_allowed_actions(caps_effective, registry=action_registry)
            except Exception as exc:
                if strict:
                    return {
                        "ok": False,
                        "error": "capabilities_invalid",
                        "error_code": "CAPABILITIES_INVALID",
                        "details": {"detail": str(exc)},
                    }
                warnings.append("capabilities_invalid_slot_a")
                computed = []
        else:
            source = "template.legacy"
            try:
                legacy = templates_registry.render_spec(
                    template_id,
                    {
                        "enable_oracle": bool((dict(src.get("oracle_policy") or {})).get("enabled"))
                        or bool((dict(src.get("oracle_policy") or {})).get("allow_remote")),
                        "enable_comm": bool((dict(src.get("comm_policy") or {})).get("enabled")),
                    },
                )
                computed = _clean_list(legacy.get("allowed_actions") or [])
            except Exception as exc:
                return {
                    "ok": False,
                    "error": "template_resolve_failed",
                    "error_code": "TEMPLATE_RESOLVE_FAILED",
                    "details": {"detail": str(exc)},
                }
    elif caps_requested:
        source = "raw.capabilities"
        try:
            computed = templates_registry.resolve_allowed_actions(caps_requested, registry=action_registry)
            caps_effective = list(caps_requested)
        except Exception as exc:
            if strict:
                return {
                    "ok": False,
                    "error": "capabilities_invalid",
                    "error_code": "CAPABILITIES_INVALID",
                    "details": {"detail": str(exc)},
                }
            warnings.append("capabilities_invalid_slot_a")
            computed = []
    else:
        source = "legacy"

    if strict:
        if not (template_id or caps_effective):
            return {"ok": False, "error": "authority_missing", "error_code": "AUTHORITY_MISSING"}
        final_allow = list(computed)
        if allowed_input:
            warnings.append("allowed_actions_ignored_slot_b")
    else:
        if computed:
            if allowed_input:
                clamped = [x for x in allowed_input if x in set(computed)]
                if len(clamped) != len(allowed_input):
                    warnings.append("allowed_actions_clamped")
                final_allow = clamped if clamped else list(computed)
            else:
                final_allow = list(computed)
        else:
            known = _known_action_ids()
            final_allow = [x for x in allowed_input if (x in known)]
            if len(final_allow) != len(allowed_input):
                warnings.append("allowed_actions_unknown_clamped")

    final_allow = _clean_list(final_allow)
    if not final_allow:
        return {"ok": False, "error": "allowlist_empty", "error_code": "ALLOWLIST_EMPTY", "warnings": warnings}
    return {
        "ok": True,
        "slot": slot,
        "source": source,
        "template_id": template_id,
        "capabilities_base": list(caps_base),
        "capabilities_effective": list(caps_effective),
        "allowed_actions": list(final_allow),
        "warnings": list(_clean_list(warnings)),
    }


def _garage_root() -> Path:
    raw = (os.getenv("GARAGE_ROOT") or "").strip()
    if raw:
        base = Path(raw)
        if not base.is_absolute():
            base = (Path.cwd() / base).resolve()
    else:
        base = (_persist_dir() / "garage").resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base


def agents_root() -> Path:
    p = (_garage_root() / "agents").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _index_path() -> Path:
    p = (agents_root() / "index.json").resolve()
    if not p.exists():
        init_payload = json.dumps({"agents": {}, "updated_ts": int(time.time())}, ensure_ascii=False, indent=2)
        try:
            p.write_text(init_payload, encoding="utf-8")
        except Exception:
            pass
    return p


def _events_path() -> Path:
    p = (agents_root() / "events.jsonl").resolve()
    if not p.exists():
        p.touch()
    return p


def _load_index() -> Dict[str, Any]:
    p = _index_path()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("bad_index")
    except Exception:
        raw = {"agents": {}, "updated_ts": int(time.time())}
    raw.setdefault("agents", {})
    if not isinstance(raw["agents"], dict):
        raw["agents"] = {}
    raw.setdefault("updated_ts", int(time.time()))
    return raw


def _save_index(index: Dict[str, Any]) -> None:
    p = _index_path()
    payload = json.dumps(dict(index or {}), ensure_ascii=False, indent=2)
    tmp = p.with_suffix(".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(p)
        return
    except Exception:
        pass
    try:
        p.write_text(payload, encoding="utf-8")
    except Exception:
        return


def _append_event(event: Dict[str, Any]) -> None:
    line = json.dumps(dict(event or {}), ensure_ascii=False)
    with _events_path().open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def _agent_folder(agent_id: str) -> Path:
    p = (agents_root() / str(agent_id)).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _spec_path(agent_id: str) -> Path:
    return (_agent_folder(agent_id) / "spec.json").resolve()


def _write_spec_trusted(
    agent_id: str,
    spec_path: Path,
    payload: Dict[str, Any],
    *,
    chain_id: str,
    reason: str,
    actor: str = "ester",
) -> Dict[str, Any]:
    if integrity_verifier is not None and hasattr(integrity_verifier, "trusted_spec_write"):
        try:
            rep = integrity_verifier.trusted_spec_write(
                str(agent_id or ""),
                str(spec_path),
                dict(payload or {}),
                chain_id=str(chain_id or ""),
                reason=str(reason or ""),
                actor=str(actor or "ester"),
            )
            if isinstance(rep, dict):
                return rep
        except Exception as exc:
            return {"ok": False, "error": "spec_write_failed", "error_code": "SPEC_WRITE_FAILED", "detail": str(exc)}
    try:
        spec_path.write_text(json.dumps(dict(payload or {}), ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "spec_path": str(spec_path)}
    except Exception as exc:
        return {"ok": False, "error": "spec_write_failed", "error_code": "SPEC_WRITE_FAILED", "detail": str(exc)}


def _load_spec(agent_id: str) -> Dict[str, Any]:
    sp = _spec_path(agent_id)
    if not sp.exists():
        return {}
    try:
        raw = json.loads(sp.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except Exception:
        return {}
    return {}


def create_agent(spec: Any) -> Dict[str, Any]:
    raw_spec = dict(spec or {})
    strict = bool(_strict_enabled())
    integrity_warnings: List[str] = []
    if integrity_verifier is not None and hasattr(integrity_verifier, "precheck_create"):
        try:
            irep = integrity_verifier.precheck_create(
                str(raw_spec.get("template_id") or ""),
                action="agent.create",
            )
            if isinstance(irep, dict):
                if not bool(irep.get("ok")):
                    return {
                        "ok": False,
                        "error": str(irep.get("error") or "integrity_tamper"),
                        "error_code": str(irep.get("error_code") or "INTEGRITY_TAMPER"),
                        "reason_code": str(irep.get("reason_code") or ""),
                        "details": {
                            "integrity": dict(irep.get("integrity") or {}),
                            "slot": str(irep.get("slot") or ""),
                            "enforced": bool(irep.get("enforced")),
                        },
                    }
                integrity_warnings = [str(x) for x in list(irep.get("warnings") or []) if str(x).strip()]
        except Exception:
            integrity_warnings = []

    try:
        auth = resolve_allowlist_for_spec(raw_spec, slot_override=("B" if strict else "A"))
    except Exception as exc:
        if strict:
            status = _note_strict_exception("agent_factory.create_agent", exc)
            if bool(status.get("strict_enabled")):
                return {"ok": False, "error": "authority_resolve_failed", "detail": str(exc), "strict_status": status}
            auth = resolve_allowlist_for_spec(raw_spec, slot_override="A")
            auth.setdefault("warnings", [])
            auth["warnings"] = _clean_list(list(auth.get("warnings") or []) + ["slot_b_auto_rollback"])
        else:
            return {"ok": False, "error": "authority_resolve_failed", "detail": str(exc)}

    if not bool(auth.get("ok")):
        _journal_policy(
            allowed=False,
            reason_code=str(auth.get("error_code") or "DENY"),
            reason=str(auth.get("error") or "authority_invalid"),
            metadata={
                "policy_hit": "agent.create",
                "template_id": str(raw_spec.get("template_id") or ""),
                "capabilities": _clean_list(raw_spec.get("capabilities") or []),
                "slot": _slot(),
                "details": dict(auth.get("details") or {}),
            },
        )
        return {
            "ok": False,
            "error": str(auth.get("error") or "authority_invalid"),
            "error_code": str(auth.get("error_code") or "AUTHORITY_INVALID"),
            "details": dict(auth.get("details") or {}),
            "warnings": list(auth.get("warnings") or []),
        }

    if strict:
        _note_strict_success()

    spec_input = dict(raw_spec)
    spec_input["allowed_actions"] = list(auth.get("allowed_actions") or [])
    spec_obj = AgentSpec.from_any(spec_input)
    ok, errs = spec_obj.validate()
    if not ok:
        _journal_policy(
            allowed=False,
            reason_code="INVALID_SPEC",
            reason="invalid_spec",
            metadata={"policy_hit": "agent.create", "reasons": errs, "slot": _slot()},
        )
        return {"ok": False, "error": "invalid_spec", "reasons": errs}

    agent_id = "agent_" + uuid.uuid4().hex[:12]
    now = int(time.time())
    folder = _agent_folder(agent_id)
    spec_path = _spec_path(agent_id)
    payload = spec_obj.to_dict()
    payload.update(
        {
            "agent_id": agent_id,
            "enabled": True,
            "created_ts": now,
            "updated_ts": now,
            "folder": str(folder),
            "template_id": str(auth.get("template_id") or raw_spec.get("template_id") or ""),
            "capabilities_effective": list(auth.get("capabilities_effective") or []),
            "capabilities_base": list(auth.get("capabilities_base") or []),
            "allowed_actions_hash": _hash_list(list(auth.get("allowed_actions") or [])),
            "capabilities_hash": _hash_list(list(auth.get("capabilities_effective") or [])),
            "authority_source": str(auth.get("source") or ""),
            "authority_warnings": list(auth.get("warnings") or []),
        }
    )

    with _LOCK:
        write_rep = _write_spec_trusted(
            agent_id,
            spec_path,
            payload,
            chain_id="chain_agent_create_" + agent_id,
            reason="agent.create",
            actor="ester",
        )
        if not bool(write_rep.get("ok")):
            return {
                "ok": False,
                "error": str(write_rep.get("error") or "spec_write_failed"),
                "error_code": str(write_rep.get("error_code") or "SPEC_WRITE_FAILED"),
                "detail": str(write_rep.get("detail") or ""),
            }

        idx = _load_index()
        agents = dict(idx.get("agents") or {})
        agents[agent_id] = {
            "agent_id": agent_id,
            "name": payload.get("name"),
            "owner": payload.get("owner"),
            "goal": payload.get("goal"),
            "enabled": True,
            "folder": str(folder),
            "spec_path": str(spec_path),
            "template_id": payload.get("template_id"),
            "capabilities_effective": list(payload.get("capabilities_effective") or []),
            "allowed_actions_hash": str(payload.get("allowed_actions_hash") or ""),
            "created_ts": now,
            "updated_ts": now,
        }
        idx["agents"] = agents
        idx["updated_ts"] = now
        _save_index(idx)
        _append_event({"ts": now, "event": "create", "agent_id": agent_id, "name": payload.get("name")})

    warnings = [str(x) for x in list(auth.get("warnings") or []) if str(x).strip()]
    for w in integrity_warnings:
        if w not in warnings:
            warnings.append(w)
    _journal_policy(
        allowed=True,
        reason_code=("ALLOW_CLAMP" if warnings else "ALLOW"),
        reason=("created_with_clamp" if warnings else "created"),
        metadata={
            "policy_hit": "agent.create",
            "agent_id": agent_id,
            "template_id": payload.get("template_id"),
            "capabilities_effective": list(payload.get("capabilities_effective") or []),
            "allowed_actions": list(payload.get("allowed_actions") or []),
            "allowed_actions_hash": str(payload.get("allowed_actions_hash") or ""),
            "warnings": warnings,
            "slot": _slot(),
        },
    )

    return {
        "ok": True,
        "agent_id": agent_id,
        "folder": str(folder),
        "spec_path": str(spec_path),
        "spec": payload,
        "warnings": warnings,
    }


def list_agents() -> Dict[str, Any]:
    with _LOCK:
        idx = _load_index()
        rows = []
        for aid, row in sorted((idx.get("agents") or {}).items()):
            item = dict(row or {})
            if not item.get("spec_path"):
                item["spec_path"] = str(_spec_path(aid))
            rows.append(item)
    return {"ok": True, "total": len(rows), "agents": rows, "root": str(agents_root())}


def get_agent(agent_id: str) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not aid:
        return {"ok": False, "error": "agent_id_required"}
    with _LOCK:
        idx = _load_index()
        row = dict((idx.get("agents") or {}).get(aid) or {})
    if not row:
        return {"ok": False, "error": "agent_not_found", "agent_id": aid}
    spec = _load_spec(aid)
    row["spec"] = spec
    return {"ok": True, "agent": row}


def disable_agent(agent_id: str, reason: str = "") -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not aid:
        return {"ok": False, "error": "agent_id_required"}
    now = int(time.time())
    with _LOCK:
        idx = _load_index()
        agents = dict(idx.get("agents") or {})
        row = dict(agents.get(aid) or {})
        if not row:
            return {"ok": False, "error": "agent_not_found", "agent_id": aid}
        row["enabled"] = False
        row["updated_ts"] = now
        agents[aid] = row
        idx["agents"] = agents
        idx["updated_ts"] = now
        _save_index(idx)

        spec = _load_spec(aid)
        if spec:
            spec["enabled"] = False
            spec["updated_ts"] = now
            spec["disabled_reason"] = str(reason or "")
            try:
                _write_spec_trusted(
                    aid,
                    _spec_path(aid),
                    spec,
                    chain_id="chain_agent_disable_" + aid,
                    reason=("agent.disable:" + str(reason or "manual_disable")),
                    actor="ester",
                )
            except Exception:
                pass
        _append_event(
            {"ts": now, "event": "disable", "agent_id": aid, "reason": str(reason or "manual_disable")}
        )

    canceled = 0
    try:
        from modules.garage import agent_queue

        qrep = agent_queue.cancel_for_agent(aid, actor="system", reason="agent_disabled")
        if bool(qrep.get("ok")):
            canceled = int(qrep.get("canceled") or 0)
    except Exception:
        pass

    return {"ok": True, "agent_id": aid, "enabled": False, "canceled": int(canceled)}


def _is_smoke_like_agent(row: Dict[str, Any], spec: Dict[str, Any]) -> bool:
    txt = " ".join(
        [
            str(row.get("name") or ""),
            str(row.get("owner") or ""),
            str(row.get("goal") or ""),
            str(row.get("template_id") or ""),
            str(spec.get("template_id") or ""),
            str(spec.get("name") or ""),
            str(spec.get("owner") or ""),
        ]
    ).lower()
    markers = ("smoke", "tmp", "temp", "sandbox_test", "test_agent")
    return any(m in txt for m in markers)


def garage_maintenance(*, now_ts: Optional[int] = None, actor: str = "system") -> Dict[str, Any]:
    now = int(now_ts or time.time())
    if not _env_bool("ESTER_GARAGE_GC_ENABLED", True):
        return {"ok": True, "skipped": True, "reason": "gc_disabled"}

    smoke_ttl_sec = max(300, _env_int("ESTER_GARAGE_SMOKE_TTL_SEC", 6 * 3600))
    paused_heal_sec = max(60, _env_int("ESTER_GARAGE_PAUSED_HEAL_SEC", 900))
    paused_disable_sec = max(paused_heal_sec, _env_int("ESTER_GARAGE_PAUSED_DISABLE_SEC", 86400))

    with _LOCK:
        idx = _load_index()
        rows = dict(idx.get("agents") or {})

    disabled_smoke: List[str] = []
    resumed_paused: List[str] = []
    disabled_paused: List[str] = []
    skipped_paused: List[str] = []

    for aid, row_raw in rows.items():
        aid_s = str(aid or "").strip()
        if not aid_s:
            continue
        row = dict(row_raw or {})
        enabled = bool(row.get("enabled", True))
        spec = _load_spec(aid_s)

        created_ts = 0
        for key in ("created_ts", "updated_ts"):
            try:
                created_ts = int(row.get(key) or 0)
            except Exception:
                created_ts = 0
            if created_ts > 0:
                break
        age_sec = max(0, now - int(created_ts or now))

        if enabled and _is_smoke_like_agent(row, spec) and age_sec >= smoke_ttl_sec:
            rep = disable_agent(aid_s, reason="smoke_ttl_expired")
            if bool(rep.get("ok")):
                disabled_smoke.append(aid_s)
                enabled = False

        try:
            from modules.garage import agent_runner
        except Exception:
            continue

        st = dict(agent_runner.load_state(aid_s) or {})
        if not enabled:
            continue
        if str(st.get("status") or "").strip().lower() != "paused":
            continue

        try:
            stale_sec = max(0, now - int(st.get("updated_ts") or now))
        except Exception:
            stale_sec = 0
        if stale_sec < paused_heal_sec:
            continue

        resume_rep = agent_runner.resume_run(aid_s, actor=str(actor or "system"), reason="paused_autoheal")
        if bool(resume_rep.get("ok")) and bool(resume_rep.get("resumed")):
            resumed_paused.append(aid_s)
            continue

        if stale_sec >= paused_disable_sec:
            rep = disable_agent(aid_s, reason="paused_stale_auto_disable")
            if bool(rep.get("ok")):
                disabled_paused.append(aid_s)
                continue
        skipped_paused.append(aid_s)

    return {
        "ok": True,
        "now_ts": now,
        "smoke_ttl_sec": smoke_ttl_sec,
        "paused_heal_sec": paused_heal_sec,
        "paused_disable_sec": paused_disable_sec,
        "disabled_smoke": sorted(disabled_smoke),
        "resumed_paused": sorted(resumed_paused),
        "disabled_paused": sorted(disabled_paused),
        "skipped_paused": sorted(skipped_paused),
        "disabled_smoke_total": len(disabled_smoke),
        "resumed_paused_total": len(resumed_paused),
        "disabled_paused_total": len(disabled_paused),
        "skipped_paused_total": len(skipped_paused),
    }


__all__ = [
    "agents_root",
    "create_agent",
    "list_agents",
    "get_agent",
    "disable_agent",
    "resolve_allowlist_for_spec",
    "garage_maintenance",
]
