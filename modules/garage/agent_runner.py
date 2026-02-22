# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from modules.agents import plan_schema
from modules.garage import agent_factory
from modules.runtime import oracle_requests, oracle_window
from modules.thinking import action_registry
from modules.volition import journal as volition_journal
from modules.volition.journal import journal_path
from modules.volition.volition_gate import VolitionContext, get_default_gate

_LOCK = threading.RLock()
_SLOTB_DISABLED = False
_STRICT_FORBIDDEN_WARNING_CODES = {
    "unknown_step_keys",
    "unknown_plan_keys",
    "unknown_budget_keys",
}


def _slot() -> str:
    v = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if v == "B" else "A"


def _rollback_slot_a(reason: str) -> None:
    global _SLOTB_DISABLED
    with _LOCK:
        _SLOTB_DISABLED = True
    os.environ["ESTER_VOLITION_SLOT"] = "A"
    os.environ["ESTER_AGENT_RUNNER_LAST_ROLLBACK_REASON"] = str(reason or "runner_policy_violation")


def _now_ts() -> int:
    return int(time.time())


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _persist_dir() -> Path:
    root = (os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _state_path(agent_id: str) -> Path:
    p = (_persist_dir() / "agents" / str(agent_id) / "state.json").resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
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


def _default_state(agent_id: str) -> Dict[str, Any]:
    return {
        "agent_id": str(agent_id or "").strip(),
        "status": "idle",
        "current_run_id": "",
        "plan_id": "",
        "next_step_index": 0,
        "paused_reason": "",
        "pending_request_id": "",
        "last_error": "",
        "updated_ts": _now_ts(),
        "retries": {},
        "plan": {},
    }


def _sanitize_state(agent_id: str, src: Dict[str, Any]) -> Dict[str, Any]:
    st = _default_state(agent_id)
    raw = dict(src or {})
    st.update(raw)
    st["agent_id"] = str(agent_id or "").strip()

    status = str(st.get("status") or "idle").strip().lower()
    if status not in {"idle", "running", "paused", "done", "failed"}:
        status = "idle"
    st["status"] = status

    paused_reason = str(st.get("paused_reason") or "").strip().lower()
    if paused_reason not in {"", "pending_oracle", "error", "budget"}:
        paused_reason = ""
    st["paused_reason"] = paused_reason

    st["current_run_id"] = str(st.get("current_run_id") or "").strip()
    st["plan_id"] = str(st.get("plan_id") or "").strip()
    st["pending_request_id"] = str(st.get("pending_request_id") or "").strip()
    st["last_error"] = str(st.get("last_error") or "")
    st["next_step_index"] = max(0, _as_int(st.get("next_step_index"), 0))
    st["updated_ts"] = max(0, _as_int(st.get("updated_ts"), _now_ts()))

    retries: Dict[str, int] = {}
    raw_retries = dict(st.get("retries") or {})
    for k, v in raw_retries.items():
        key = str(k).strip()
        if not key:
            continue
        retries[key] = max(0, _as_int(v, 0))
    st["retries"] = retries

    plan = st.get("plan")
    if isinstance(plan, dict):
        steps = list(plan.get("steps") or [])
        if not isinstance(steps, list):
            steps = []
        st["plan"] = {"steps": [dict(x) for x in steps if isinstance(x, dict)]}
    else:
        st["plan"] = {}
    return st


def _load_state_unlocked(agent_id: str) -> Dict[str, Any]:
    p = _state_path(agent_id)
    if not p.exists():
        st = _default_state(agent_id)
        _atomic_write_json(p, st)
        return st
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("bad_state")
    except Exception:
        raw = _default_state(agent_id)
    st = _sanitize_state(agent_id, raw)
    _atomic_write_json(p, st)
    return st


def load_state(agent_id: str) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not aid:
        return _default_state("")
    with _LOCK:
        return _load_state_unlocked(aid)


def save_state(agent_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not aid:
        return _default_state("")
    with _LOCK:
        current = _load_state_unlocked(aid)
        merged = dict(current)
        for key, value in dict(state or {}).items():
            if key == "agent_id":
                continue
            merged[key] = value
        merged["updated_ts"] = _now_ts()
        st = _sanitize_state(aid, merged)
        _atomic_write_json(_state_path(aid), st)
        return st


def _run_log_path(agent_id: str) -> Path:
    root = Path(str(agent_factory.agents_root())).resolve()
    p = (root / str(agent_id) / "runs.jsonl").resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.touch()
    return p


def _append_run(agent_id: str, row: Dict[str, Any]) -> None:
    payload = dict(row or {})
    payload.setdefault("ts", _now_ts())
    line = json.dumps(payload, ensure_ascii=False)
    with _run_log_path(agent_id).open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def _emit_outbox(
    *,
    agent_id: str,
    chain_id: str,
    status: str,
    reason: str,
    action_id: str = "",
) -> None:
    try:
        from modules.companion import outbox

        text = f"[agent:{agent_id}] {status}. {reason}".strip()
        outbox.enqueue(
            kind="agent_runner.note",
            text=text,
            meta={"status": status, "reason": reason, "agent_id": agent_id},
            chain_id=chain_id,
            related_action=action_id,
        )
    except Exception:
        return


def _parse_scalar(raw: str) -> Any:
    s = str(raw or "").strip()
    if s == "":
        return ""
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in {"null", "none"}:
        return None
    if s.isdigit():
        try:
            return int(s)
        except Exception:
            return s
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s


def _parse_plan(value: Any) -> Tuple[bool, Dict[str, Any], str]:
    if isinstance(value, dict):
        plan = dict(value)
    elif isinstance(value, list):
        plan = {"steps": list(value)}
    else:
        raw = str(value or "").strip()
        if not raw:
            return False, {}, "plan_required"
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                plan = parsed
            elif isinstance(parsed, list):
                plan = {"steps": parsed}
            else:
                return False, {}, "plan_invalid_json_type"
        except Exception:
            # Minimal YAML-like parser for simple "steps" lists.
            steps: List[Dict[str, Any]] = []
            cur: Optional[Dict[str, Any]] = None
            in_args = False
            for src_line in raw.splitlines():
                line = src_line.rstrip()
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped == "steps:":
                    continue
                if stripped.startswith("- "):
                    cur = {}
                    steps.append(cur)
                    in_args = False
                    rest = stripped[2:].strip()
                    if ":" in rest:
                        k, v = rest.split(":", 1)
                        cur[str(k).strip()] = _parse_scalar(v)
                    continue
                if cur is None:
                    continue
                if stripped == "args:":
                    cur.setdefault("args", {})
                    in_args = True
                    continue
                if ":" in stripped:
                    k, v = stripped.split(":", 1)
                    key = str(k).strip()
                    if in_args:
                        args = dict(cur.get("args") or {})
                        args[key] = _parse_scalar(v)
                        cur["args"] = args
                    else:
                        cur[key] = _parse_scalar(v)
            plan = {"steps": steps}

    steps_raw = list(plan.get("steps") or [])
    steps: List[Dict[str, Any]] = []
    for row in steps_raw:
        if not isinstance(row, dict):
            continue
        action_id = str(row.get("action_id") or row.get("action") or "").strip()
        args = dict(row.get("args") or {})
        if action_id:
            item: Dict[str, Any] = {"action_id": action_id, "args": args}
            if "budgets" in row:
                item["budgets"] = dict(row.get("budgets") or {})
            steps.append(item)
    if not steps:
        return False, {}, "plan_steps_required"
    return True, {"steps": steps}, ""


def _detail(level: str, code: str, message: str, **extra: Any) -> Dict[str, Any]:
    row = {
        "level": str(level or "error"),
        "code": str(code or "invalid"),
        "message": str(message or ""),
    }
    if extra:
        row.update(dict(extra))
    return row


def _warnings_from_details(details: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for row in list(details or []):
        if str((row or {}).get("level") or "") != "warn":
            continue
        code = str((row or {}).get("code") or "").strip()
        if code and code not in out:
            out.append(code)
    return out


def _error_codes(details: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for row in list(details or []):
        if str((row or {}).get("level") or "") != "error":
            continue
        code = str((row or {}).get("code") or "").strip()
        if code and code not in out:
            out.append(code)
    return out


def _build_exec_plan(normalized_plan: Dict[str, Any], parsed_plan: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(normalized_plan or {})
    raw_steps = [dict(x) for x in list((parsed_plan or {}).get("steps") or []) if isinstance(x, dict)]
    norm_steps = [dict(x) for x in list((normalized_plan or {}).get("steps") or []) if isinstance(x, dict)]
    merged: List[Dict[str, Any]] = []
    max_len = max(len(raw_steps), len(norm_steps))
    for idx in range(max_len):
        raw = dict(raw_steps[idx]) if idx < len(raw_steps) else {}
        norm = dict(norm_steps[idx]) if idx < len(norm_steps) else {}
        action = str(norm.get("action") or raw.get("action") or raw.get("action_id") or "").strip()
        if not action:
            continue
        row: Dict[str, Any] = {"action": action, "action_id": action}
        args = norm.get("args")
        if not isinstance(args, dict):
            args = dict(raw.get("args") or {})
        row["args"] = dict(args)
        why = str(norm.get("why") or "").strip()
        if why:
            row["why"] = why
        # Slot A compatibility: keep per-step budgets for existing executor behavior.
        if isinstance(raw.get("budgets"), dict):
            row["budgets"] = dict(raw.get("budgets") or {})
        merged.append(row)
    out["steps"] = merged
    return out


def _append_plan_validate_deny(
    *,
    agent_id: str,
    run_id: str,
    plan_id: str,
    reason_code: str,
    reason: str,
    details: List[Dict[str, Any]],
    plan_hash: str,
) -> None:
    row = {
        "id": "vol_manual_" + uuid.uuid4().hex,
        "ts": int(time.time()),
        "chain_id": str(plan_id or ""),
        "step": "plan.validate",
        "actor": f"agent:{str(agent_id or '').strip()}",
        "intent": "agent_runner_plan_validate",
        "action_kind": "plan.validate",
        "needs": ["plan.validate"],
        "allowed": False,
        "reason_code": str(reason_code or "PLAN_INVALID"),
        "reason": str(reason or "plan_invalid"),
        "slot": _slot(),
        "metadata": {
            "policy_hit": "plan.validate",
            "agent_id": str(agent_id or ""),
            "run_id": str(run_id or ""),
            "plan_id": str(plan_id or ""),
            "plan_hash": str(plan_hash or ""),
            "details": list(details or [])[:16],
            "needs": ["plan.validate"],
        },
        "agent_id": str(agent_id or ""),
        "plan_id": str(plan_id or ""),
        "action_id": "plan.validate",
        "decision": "deny",
        "policy_hit": "plan.validate",
        "duration_ms": 0,
    }
    try:
        volition_journal.append(row)
    except Exception:
        return


def _append_run_step_deny(
    *,
    agent_id: str,
    run_id: str,
    plan_id: str,
    step_index: int,
    action_id: str,
    reason_code: str,
    reason: str,
    allowlist: List[str],
) -> None:
    row = {
        "id": "vol_manual_" + uuid.uuid4().hex,
        "ts": int(time.time()),
        "chain_id": str(plan_id or ""),
        "step": "agent.run.step",
        "actor": f"agent:{str(agent_id or '').strip()}",
        "intent": "agent_runner_step_enforce",
        "action_kind": str(action_id or ""),
        "needs": ["agent.run.step"],
        "allowed": False,
        "reason_code": str(reason_code or "DENY"),
        "reason": str(reason or "action_not_allowed"),
        "slot": _slot(),
        "metadata": {
            "policy_hit": "agent.run.step",
            "agent_id": str(agent_id or ""),
            "run_id": str(run_id or ""),
            "plan_id": str(plan_id or ""),
            "step_index": int(step_index or 0),
            "action_id": str(action_id or ""),
            "allowlist": [str(x) for x in list(allowlist or []) if str(x).strip()],
        },
        "agent_id": str(agent_id or ""),
        "plan_id": str(plan_id or ""),
        "step_index": int(step_index or 0),
        "action_id": str(action_id or ""),
        "decision": "deny",
        "policy_hit": "agent.run.step",
        "duration_ms": 0,
    }
    try:
        volition_journal.append(row)
    except Exception:
        return


def _append_run_quarantine_deny(
    *,
    agent_id: str,
    run_id: str,
    plan_id: str,
    reason_code: str,
    reason: str,
    event_id: str,
    severity: str,
    kind: str,
) -> None:
    row = {
        "id": "vol_manual_" + uuid.uuid4().hex,
        "ts": int(time.time()),
        "chain_id": str(plan_id or ""),
        "step": "agent.run",
        "actor": f"agent:{str(agent_id or '').strip()}",
        "intent": "agent_runner_quarantine_block",
        "action_kind": "agent.run",
        "needs": ["agent.run"],
        "allowed": False,
        "reason_code": str(reason_code or "DRIFT_QUARANTINED"),
        "reason": str(reason or "drift quarantine active"),
        "slot": _slot(),
        "metadata": {
            "policy_hit": "agent.run",
            "agent_id": str(agent_id or ""),
            "run_id": str(run_id or ""),
            "plan_id": str(plan_id or ""),
            "event_id": str(event_id or ""),
            "severity": str(severity or ""),
            "kind": str(kind or ""),
        },
        "agent_id": str(agent_id or ""),
        "plan_id": str(plan_id or ""),
        "action_id": "agent.run",
        "decision": "deny",
        "policy_hit": "agent.run",
        "duration_ms": 0,
    }
    try:
        volition_journal.append(row)
    except Exception:
        return


def _normalize_validate_plan_for_run(plan: Dict[str, Any]) -> Dict[str, Any]:
    strict = bool(plan_schema.strict_enabled())
    details: List[Dict[str, Any]] = []
    warnings: List[str] = []
    source_plan = dict(plan or {})

    try:
        norm = plan_schema.normalize_plan(source_plan)
        norm_details = list(norm.get("details") or [])
        details.extend(norm_details)
        warnings.extend(_warnings_from_details(norm_details))
        normalized = norm.get("plan")

        if not bool(norm.get("ok")):
            if strict:
                return {
                    "ok": False,
                    "error": "plan_invalid",
                    "details": details,
                    "warnings": warnings,
                    "plan": normalized,
                    "plan_hash": "",
                    "strict": strict,
                    "strict_status": plan_schema.strict_status(),
                }
            if "plan_lenient_mode" not in warnings:
                warnings.append("plan_lenient_mode")
            if normalized is None:
                normalized = source_plan

        if strict:
            forbidden = [x for x in _warnings_from_details(norm_details) if x in _STRICT_FORBIDDEN_WARNING_CODES]
            if forbidden:
                for code in forbidden:
                    details.append(
                        _detail(
                            "error",
                            code,
                            "strict schema forbids unknown keys",
                            strict=True,
                        )
                    )
                return {
                    "ok": False,
                    "error": "plan_invalid",
                    "details": details,
                    "warnings": warnings,
                    "plan": normalized,
                    "plan_hash": "",
                    "strict": strict,
                    "strict_status": plan_schema.strict_status(),
                }

        val = plan_schema.validate_plan(dict(normalized or {}), registry=action_registry)
        details.extend(list(val.get("details") or []))
        ph = str(val.get("plan_hash") or "")

        if not bool(val.get("ok")):
            if strict:
                return {
                    "ok": False,
                    "error": "plan_invalid",
                    "details": details,
                    "warnings": warnings,
                    "plan": normalized,
                    "plan_hash": ph,
                    "strict": strict,
                    "strict_status": plan_schema.strict_status(),
                }
            if "plan_lenient_mode" not in warnings:
                warnings.append("plan_lenient_mode")
            for code in _error_codes(list(val.get("details") or [])):
                marker = "lenient_" + code
                if marker not in warnings:
                    warnings.append(marker)
        elif strict:
            plan_schema.note_strict_success()

        return {
            "ok": True,
            "error": "",
            "details": details,
            "warnings": warnings,
            "plan": dict(normalized or {}),
            "plan_hash": ph,
            "strict": strict,
            "strict_status": plan_schema.strict_status(),
        }
    except Exception as exc:
        if strict:
            status = plan_schema.note_strict_exception("agent_runner.run_once", exc)
            details.append(
                _detail(
                    "error",
                    "plan_schema_exception",
                    "strict plan schema crashed",
                    where="agent_runner.run_once",
                    detail=f"{exc.__class__.__name__}: {exc}",
                )
            )
            if bool(status.get("strict_enabled")):
                return {
                    "ok": False,
                    "error": "plan_invalid",
                    "details": details,
                    "warnings": warnings,
                    "plan": None,
                    "plan_hash": "",
                    "strict": True,
                    "strict_status": status,
                }
            if "plan_schema_auto_rollback" not in warnings:
                warnings.append("plan_schema_auto_rollback")
        if "plan_lenient_mode" not in warnings:
            warnings.append("plan_lenient_mode")
        if "plan_schema_exception" not in warnings:
            warnings.append("plan_schema_exception")
        return {
            "ok": True,
            "error": "",
            "details": details,
            "warnings": warnings,
            "plan": dict(source_plan),
            "plan_hash": "",
            "strict": False,
            "strict_status": plan_schema.strict_status(),
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


def _exec_files_sandbox_write(agent_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    ok, rel = _safe_relpath(str(args.get("relpath") or "output.txt"))
    if not ok:
        return {"ok": False, "error": "invalid_relpath"}
    content = str(args.get("content") or "")
    root = _sandbox_root(agent_id)
    dst = (root / rel).resolve()
    if root not in dst.parents and dst != root:
        return {"ok": False, "error": "path_outside_sandbox"}
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content, encoding="utf-8")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return {
        "ok": True,
        "stored_path": str(dst),
        "relpath": rel,
        "bytes": len(content.encode("utf-8")),
        "sha256": digest,
    }


def _exec_files_sha256_verify(agent_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    ok, rel = _safe_relpath(str(args.get("relpath") or ""))
    if not ok:
        return {"ok": False, "error": "invalid_relpath"}
    root = _sandbox_root(agent_id)
    src = (root / rel).resolve()
    if root not in src.parents and src != root:
        return {"ok": False, "error": "path_outside_sandbox"}
    if not src.exists() or not src.is_file():
        return {"ok": False, "error": "file_not_found", "relpath": rel}
    raw = src.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    expected = str(args.get("expected_sha256") or "").strip().lower()
    matched = (digest == expected) if expected else True
    return {
        "ok": matched,
        "matched": matched,
        "sha256": digest,
        "expected_sha256": expected,
        "relpath": rel,
        "bytes": len(raw),
    }


def _step_needs(action_id: str) -> List[str]:
    if action_id in {"oracle.openai.call", "llm.remote.call"}:
        return ["network", "oracle"]
    return []


def _is_oracle_action(action_id: str) -> bool:
    return str(action_id or "").strip() in {"oracle.openai.call", "llm.remote.call"}


def _normalize_action_kind(action_id: str) -> str:
    if _is_oracle_action(action_id):
        return "llm.remote.call"
    return str(action_id or "").strip()


def _oracle_prompt_digest(args: Dict[str, Any]) -> str:
    prompt = str((args or {}).get("prompt") or "")
    if not prompt:
        return ""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _same_step_index(left: Any, right: Any) -> bool:
    try:
        if left is None or right is None:
            return left is None and right is None
        return int(left) == int(right)
    except Exception:
        return False


def _find_request_for_step(
    *,
    agent_id: str,
    plan_id: str,
    step_index: int,
    model: str,
    statuses: List[str],
) -> Dict[str, Any]:
    rep = oracle_requests.list_requests(limit=500)
    if not bool(rep.get("ok")):
        return {}
    wanted_status = {str(x or "").strip() for x in statuses if str(x or "").strip()}
    for row in list(rep.get("requests") or []):
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "").strip() not in wanted_status:
            continue
        if str(row.get("agent_id") or "").strip() != str(agent_id or "").strip():
            continue
        row_plan = str(row.get("plan_id") or "").strip()
        if row_plan and row_plan != str(plan_id or "").strip():
            continue
        if not _same_step_index(row.get("step_index"), step_index):
            continue
        row_model = str(row.get("model") or "").strip()
        if row_model and str(model or "").strip() and row_model != str(model).strip():
            continue
        return dict(row)
    return {}


def _ester_actor(actor: str) -> bool:
    clean = str(actor or "").strip().lower()
    return clean == "ester" or clean.startswith("ester:")


def _retry_limit_per_step() -> int:
    return max(0, _as_int(os.getenv("ESTER_AGENT_MAX_RETRIES_PER_STEP", "1"), 1))


def _retry_transient_tags() -> set[str]:
    raw = str(os.getenv("ESTER_AGENT_RETRY_TRANSIENT_TAGS", "timeout,temp_io,oracle_window_closed") or "")
    out = {str(x).strip().lower() for x in raw.split(",") if str(x).strip()}
    if not out:
        out = {"timeout", "temp_io", "oracle_window_closed"}
    return out


def _error_tag(error: str) -> str:
    raw = str(error or "").strip().lower()
    if not raw:
        return ""
    return raw.split(":", 1)[0].strip()


def _resume_check(agent_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    st = _sanitize_state(agent_id, dict(state or {}))
    if str(st.get("status") or "") != "paused":
        return {"ok": False, "error": "not_paused", "status": st.get("status")}

    paused_reason = str(st.get("paused_reason") or "")
    if paused_reason == "pending_oracle":
        req_id = str(st.get("pending_request_id") or "").strip()
        if not req_id:
            return {"ok": False, "error": "request_id_missing"}

        req_rep = oracle_requests.get_request(req_id)
        if not bool(req_rep.get("ok")):
            return {"ok": False, "error": "request_not_found", "request_id": req_id}
        req = dict(req_rep.get("request") or {})
        if str(req.get("status") or "") != "approved":
            return {"ok": False, "error": "request_not_approved", "request_id": req_id}

        cur = oracle_window.current_window()
        if not bool(cur.get("open")):
            return {"ok": False, "error": "oracle_window_closed", "request_id": req_id}

        win_actor = str(cur.get("actor") or "").strip().lower()
        if not (win_actor == "ester" or win_actor.startswith("ester:")):
            return {"ok": False, "error": "actor_not_ester", "request_id": req_id}

        if not bool(cur.get("allow_agents")):
            return {"ok": False, "error": "window_allow_agents_false", "request_id": req_id}

        approved_ids = [str(x) for x in list(((cur.get("meta") or {}).get("approved_request_ids") or []))]
        if approved_ids and req_id not in approved_ids:
            return {"ok": False, "error": "window_request_binding", "request_id": req_id}

        return {
            "ok": True,
            "paused_reason": paused_reason,
            "request_id": req_id,
            "window_id": str(cur.get("window_id") or ""),
        }

    if paused_reason == "error":
        step_index = max(1, _as_int(st.get("next_step_index"), 0))
        retries = dict(st.get("retries") or {})
        tried = max(0, _as_int(retries.get(str(step_index)), 0))
        max_retries = _retry_limit_per_step()
        tag = _error_tag(str(st.get("last_error") or ""))
        allowed_tags = _retry_transient_tags()
        if tag not in allowed_tags:
            return {
                "ok": False,
                "error": "retry_not_allowed",
                "step_index": step_index,
                "error_tag": tag,
                "allowed_tags": sorted(allowed_tags),
            }
        if tried >= max_retries:
            return {
                "ok": False,
                "error": "retries_exhausted",
                "step_index": step_index,
                "retries": tried,
                "max_retries": max_retries,
            }
        return {
            "ok": True,
            "paused_reason": paused_reason,
            "step_index": step_index,
            "error_tag": tag,
            "retries": tried,
            "max_retries": max_retries,
        }

    return {"ok": False, "error": "resume_reason_not_supported", "paused_reason": paused_reason}


def can_resume(agent_id: str, state: Dict[str, Any]) -> bool:
    return bool(_resume_check(agent_id, state).get("ok"))


def pause_run(
    agent_id: str,
    run_id: str,
    plan_id: str,
    step_index: int,
    reason: str,
    request_id: str = "",
    *,
    last_error: str = "",
) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    rid = str(run_id or "").strip()
    pid = str(plan_id or "").strip()
    idx = max(1, _as_int(step_index, 1))
    pause_reason = str(reason or "").strip().lower() or "error"
    req_id = str(request_id or "").strip()

    st = save_state(
        aid,
        {
            "status": "paused",
            "current_run_id": rid,
            "plan_id": pid,
            "next_step_index": idx,
            "paused_reason": pause_reason,
            "pending_request_id": req_id,
            "last_error": str(last_error or ("" if pause_reason == "pending_oracle" else pause_reason)),
        },
    )
    _append_run(
        aid,
        {
            "event": "pause",
            "run_id": rid,
            "plan_id": pid,
            "step_index": idx,
            "reason": pause_reason,
            "request_id": req_id,
        },
    )
    return st


def resume_run(
    agent_id: str,
    *,
    actor: str = "ester",
    reason: str = "",
    dry_run: bool = False,
) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not aid:
        return {"ok": False, "error": "agent_id_required", "resumed": False}

    actor_clean = str(actor or "").strip() or "ester"
    if not _ester_actor(actor_clean):
        st_bad = load_state(aid)
        return {
            "ok": False,
            "error": "actor_forbidden",
            "resumed": False,
            "agent_id": aid,
            "status": str(st_bad.get("status") or "idle"),
            "run_id": str(st_bad.get("current_run_id") or ""),
            "next_step_index": int(st_bad.get("next_step_index") or 0),
        }

    st = load_state(aid)
    check = _resume_check(aid, st)
    base = {
        "agent_id": aid,
        "status": str(st.get("status") or "idle"),
        "run_id": str(st.get("current_run_id") or ""),
        "next_step_index": int(st.get("next_step_index") or 0),
        "paused_reason": str(st.get("paused_reason") or ""),
    }
    if not bool(check.get("ok")):
        return {
            "ok": False,
            "resumed": False,
            "error": str(check.get("error") or "resume_not_allowed"),
            "resume_check": check,
            **base,
        }

    if bool(dry_run):
        return {
            "ok": True,
            "resumed": False,
            "dry_run": True,
            "can_resume": True,
            "resume_check": check,
            **base,
        }

    run_id = str(st.get("current_run_id") or ("run_" + uuid.uuid4().hex[:12]))
    plan_id = str(st.get("plan_id") or ("plan_" + uuid.uuid4().hex[:10]))
    from_step = max(1, _as_int(st.get("next_step_index"), 1))

    plan = st.get("plan")
    if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list) or not list(plan.get("steps") or []):
        return {
            "ok": False,
            "resumed": False,
            "error": "plan_checkpoint_missing",
            "run_id": run_id,
            "next_step_index": from_step,
            "status": str(st.get("status") or "paused"),
        }

    if str(st.get("paused_reason") or "") == "error":
        retries = dict(st.get("retries") or {})
        step_key = str(from_step)
        retries[step_key] = max(0, _as_int(retries.get(step_key), 0)) + 1
        st = save_state(aid, {"retries": retries})
        _append_run(
            aid,
            {
                "event": "retry",
                "run_id": run_id,
                "step_index": from_step,
                "why": str(st.get("last_error") or "retry"),
                "policy": {
                    "max_retries_per_step": _retry_limit_per_step(),
                    "retry_transient_tags": sorted(_retry_transient_tags()),
                    "attempt": int(retries.get(step_key) or 0),
                },
            },
        )

    _append_run(
        aid,
        {
            "event": "resume",
            "run_id": run_id,
            "plan_id": plan_id,
            "from_step": from_step,
            "by": actor_clean,
            "reason": str(reason or ""),
        },
    )
    rep = run_once(
        aid,
        plan,
        {
            "intent": "agent_resume",
            "chain_id": plan_id,
            "plan_id": plan_id,
            "run_id": run_id,
            "resume_from_step": from_step,
            "is_resume": True,
            "resume_reason": str(reason or ""),
            "resume_actor": actor_clean,
        },
    )
    out = dict(rep if isinstance(rep, dict) else {"ok": False, "error": "resume_invalid_reply"})
    out.setdefault("agent_id", aid)
    out.setdefault("run_id", run_id)
    out.setdefault("plan_id", plan_id)
    out["resumed"] = True
    return out


def _exec_action(agent_id: str, action_id: str, args: Dict[str, Any], gate: Any, budgets: Dict[str, Any]) -> Dict[str, Any]:
    del gate, budgets
    if action_id == "files.sandbox_write":
        return _exec_files_sandbox_write(agent_id, args)
    if action_id == "files.sha256_verify":
        return _exec_files_sha256_verify(agent_id, args)
    if action_id in {
        "plan.build",
        "memory.add_note",
        "initiative.mark_done",
        "proactivity.queue.add",
        "messages.outbox.enqueue",
        "messages.telegram.send",
        "llm.remote.call",
        "local.search",
        "local.extract",
        "local.crosscheck",
        "crystallize.fact",
        "crystallize.negative",
        "close.ticket",
        "web.search",
    }:
        return action_registry.invoke(action_id, dict(args or {}))
    if action_id == "oracle.openai.call":
        payload = dict(args or {})
        if not str(payload.get("purpose") or "").strip():
            payload["purpose"] = str(payload.get("reason") or "agent_runner")
        return action_registry.invoke("llm.remote.call", payload)
    return {"ok": False, "error": "unknown_action", "action_id": action_id}


def run_once(agent_id: str, plan_yaml_or_json: Any, ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ctx = dict(ctx or {})
    aid = str(agent_id or "").strip()
    rep = agent_factory.get_agent(aid)
    if not bool(rep.get("ok")):
        return rep
    agent = dict(rep.get("agent") or {})
    spec = dict(agent.get("spec") or {})
    if not bool(spec.get("enabled", agent.get("enabled", True))):
        return {"ok": False, "error": "agent_disabled", "error_code": "AGENT_DISABLED", "agent_id": aid}
    runtime_warnings: List[str] = []

    chain_id = str(ctx.get("chain_id") or ("chain_agentos_" + uuid.uuid4().hex[:10]))
    plan_id = str(ctx.get("plan_id") or chain_id)
    run_id = str(ctx.get("run_id") or ("run_" + uuid.uuid4().hex[:12]))
    start_step = max(1, _as_int(ctx.get("resume_from_step"), 1))
    is_resume = bool(ctx.get("is_resume")) or start_step > 1

    try:
        from modules.runtime import integrity_verifier  # type: ignore
    except Exception:
        integrity_verifier = None  # type: ignore
    if integrity_verifier is not None and hasattr(integrity_verifier, "precheck_agent_action"):
        irep = integrity_verifier.precheck_agent_action(
            aid,
            template_id=str(spec.get("template_id") or ""),
            spec_path=str(agent.get("spec_path") or ""),
            action="agent.run",
        )
        if not bool(irep.get("ok")):
            q = dict(irep.get("quarantine") or {})
            _append_run_quarantine_deny(
                agent_id=aid,
                run_id=run_id,
                plan_id=plan_id,
                reason_code=str(irep.get("error_code") or "INTEGRITY_TAMPER"),
                reason=str(irep.get("error") or "integrity_tamper"),
                event_id=str(q.get("event_id") or ""),
                severity=str(q.get("severity") or "HIGH"),
                kind=str(q.get("kind") or "integrity_tamper"),
            )
            save_state(
                aid,
                {
                    "status": "failed",
                    "current_run_id": run_id,
                    "plan_id": plan_id,
                    "next_step_index": start_step,
                    "paused_reason": "",
                    "pending_request_id": "",
                    "last_error": str(irep.get("error_code") or "integrity_tamper"),
                },
            )
            return {
                "ok": False,
                "error": str(irep.get("error") or "integrity_tamper"),
                "error_code": str(irep.get("error_code") or "INTEGRITY_TAMPER"),
                "reason_code": str(irep.get("reason_code") or ""),
                "agent_id": aid,
                "chain_id": chain_id,
                "plan_id": plan_id,
                "run_id": run_id,
                "slot": _slot(),
                "integrity": dict(irep.get("integrity") or {}),
                "spec_guard": dict(irep.get("spec_guard") or {}),
                "quarantine": dict(q),
            }
        for w in list(irep.get("warnings") or []):
            ws = str(w or "").strip()
            if ws and ws not in runtime_warnings:
                runtime_warnings.append(ws)

    allow_rep = agent_factory.resolve_allowlist_for_spec(spec, slot_override=_slot())
    if bool(allow_rep.get("ok")):
        allowed_actions = [str(x) for x in list(allow_rep.get("allowed_actions") or []) if str(x).strip()]
    else:
        if _slot() == "B":
            reason = str(allow_rep.get("error") or "allowlist_invalid")
            _append_run_step_deny(
                agent_id=aid,
                run_id="",
                plan_id="",
                step_index=0,
                action_id="",
                reason_code=str(allow_rep.get("error_code") or "ALLOWLIST_INVALID"),
                reason=reason,
                allowlist=[],
            )
            return {
                "ok": False,
                "error": reason,
                "error_code": str(allow_rep.get("error_code") or "ALLOWLIST_INVALID"),
                "agent_id": aid,
                "slot": _slot(),
            }
        allowed_actions = [str(x) for x in list(spec.get("allowed_actions") or []) if str(x).strip()]

    try:
        from modules.runtime import drift_quarantine
    except Exception:
        drift_quarantine = None  # type: ignore

    if drift_quarantine is not None:
        q = drift_quarantine.ensure_quarantine_for_agent(aid, source="agent.run")
        if bool(q.get("active")) and bool(q.get("enforced")):
            _append_run_quarantine_deny(
                agent_id=aid,
                run_id=run_id,
                plan_id=plan_id,
                reason_code="DRIFT_QUARANTINED",
                reason="drift quarantine active",
                event_id=str(q.get("event_id") or ""),
                severity=str(q.get("severity") or "HIGH"),
                kind=str(q.get("kind") or ""),
            )
            try:
                drift_quarantine.note_quarantine_block(
                    aid,
                    str(q.get("event_id") or ""),
                    str(q.get("reason_code") or "DRIFT_QUARANTINED"),
                    str(q.get("severity") or "HIGH"),
                    step="agent.run",
                    details={"source": "agent_runner", "kind": str(q.get("kind") or "")},
                )
            except Exception:
                pass
            save_state(
                aid,
                {
                    "status": "failed",
                    "current_run_id": run_id,
                    "plan_id": plan_id,
                    "next_step_index": start_step,
                    "paused_reason": "",
                    "pending_request_id": "",
                    "last_error": "drift_quarantined",
                },
            )
            return {
                "ok": False,
                "error": "drift_quarantined",
                "error_code": "DRIFT_QUARANTINED",
                "agent_id": aid,
                "chain_id": chain_id,
                "plan_id": plan_id,
                "run_id": run_id,
                "slot": _slot(),
                "quarantine": {
                    "active": True,
                    "event_id": str(q.get("event_id") or ""),
                    "reason_code": str(q.get("reason_code") or ""),
                    "severity": str(q.get("severity") or ""),
                    "kind": str(q.get("kind") or ""),
                    "enforced": bool(q.get("enforced")),
                },
            }
        if bool(q.get("active")) and (not bool(q.get("enforced"))):
            if "drift_quarantine_active_observe_only" not in runtime_warnings:
                runtime_warnings.append("drift_quarantine_active_observe_only")

    base_budgets = dict(spec.get("budgets") or {})
    gate = get_default_gate()

    ok_plan, plan, plan_err = _parse_plan(plan_yaml_or_json)
    if not ok_plan:
        save_state(
            aid,
            {
                "status": "failed",
                "current_run_id": run_id,
                "plan_id": plan_id,
                "next_step_index": start_step,
                "paused_reason": "",
                "pending_request_id": "",
                "last_error": plan_err,
            },
        )
        _emit_outbox(
            agent_id=aid,
            chain_id=chain_id,
            status="failed_plan_parse",
            reason=plan_err,
        )
        return {"ok": False, "error": plan_err, "agent_id": aid, "chain_id": chain_id, "run_id": run_id}

    schema_rep = _normalize_validate_plan_for_run(plan)
    normalized_plan = dict(schema_rep.get("plan") or {})
    plan_id = str(ctx.get("plan_id") or normalized_plan.get("plan_id") or plan_id)
    if not bool(schema_rep.get("ok")):
        deny_reason = str(schema_rep.get("error") or "plan_invalid")
        deny_details = list(schema_rep.get("details") or [])
        _append_plan_validate_deny(
            agent_id=aid,
            run_id=run_id,
            plan_id=plan_id,
            reason_code="PLAN_INVALID",
            reason=deny_reason,
            details=deny_details,
            plan_hash=str(schema_rep.get("plan_hash") or ""),
        )
        save_state(
            aid,
            {
                "status": "failed",
                "current_run_id": run_id,
                "plan_id": plan_id,
                "next_step_index": start_step,
                "paused_reason": "",
                "pending_request_id": "",
                "last_error": deny_reason,
            },
        )
        _emit_outbox(
            agent_id=aid,
            chain_id=plan_id,
            status="failed_plan_validate",
            reason=deny_reason,
        )
        return {
            "ok": False,
            "error": "plan_invalid",
            "agent_id": aid,
            "chain_id": plan_id,
            "plan_id": plan_id,
            "run_id": run_id,
            "details": deny_details,
            "warnings": list(schema_rep.get("warnings") or []),
            "plan_hash": str(schema_rep.get("plan_hash") or ""),
            "slot": _slot(),
        }

    plan = _build_exec_plan(normalized_plan, plan)
    if not str(ctx.get("plan_id") or "").strip():
        plan_id = str(plan.get("plan_id") or plan_id)

    if _slot() == "B" and (not allowed_actions):
        _append_run_step_deny(
            agent_id=aid,
            run_id=run_id,
            plan_id=plan_id,
            step_index=0,
            action_id="",
            reason_code="ALLOWLIST_EMPTY",
            reason="allowlist_empty",
            allowlist=[],
        )
        save_state(
            aid,
            {
                "status": "failed",
                "current_run_id": run_id,
                "plan_id": plan_id,
                "next_step_index": start_step,
                "paused_reason": "",
                "pending_request_id": "",
                "last_error": "allowlist_empty",
            },
        )
        return {
            "ok": False,
            "error": "allowlist_empty",
            "error_code": "ALLOWLIST_EMPTY",
            "agent_id": aid,
            "chain_id": plan_id,
            "plan_id": plan_id,
            "run_id": run_id,
            "slot": _slot(),
        }

    current_state = load_state(aid)
    retries_map = dict(current_state.get("retries") or {}) if is_resume else {}
    save_state(
        aid,
        {
            "status": "running",
            "current_run_id": run_id,
            "plan_id": plan_id,
            "next_step_index": start_step,
            "paused_reason": "",
            "pending_request_id": "",
            "last_error": "",
            "retries": retries_map,
            "plan": plan,
        },
    )
    steps_all = list(plan.get("steps") or [])
    total_steps = len(steps_all)
    if start_step > (total_steps + 1):
        start_step = total_steps + 1

    # plan stage
    dec_plan = gate.decide(
        VolitionContext(
            chain_id=chain_id,
            step="plan",
            actor="ester",
            intent=str(ctx.get("intent") or "agent_runner_plan"),
            needs=["agent.plan"],
            budgets=base_budgets,
            metadata={"agent_id": aid, "run_id": run_id, "plan_id": plan_id},
        )
    )
    if not dec_plan.allowed:
        _rollback_slot_a(f"plan_denied:{dec_plan.reason_code}")
        save_state(
            aid,
            {
                "status": "failed",
                "current_run_id": run_id,
                "plan_id": plan_id,
                "next_step_index": start_step,
                "paused_reason": "",
                "pending_request_id": "",
                "last_error": str(dec_plan.reason_code),
            },
        )
        _emit_outbox(
            agent_id=aid,
            chain_id=chain_id,
            status="denied_plan",
            reason=dec_plan.reason_code,
        )
        return {
            "ok": False,
            "error": "volition_denied",
            "denied_at": "plan",
            "reason_code": dec_plan.reason_code,
            "reason": dec_plan.reason,
            "agent_id": aid,
            "chain_id": chain_id,
            "run_id": run_id,
        }

    dec_agent = gate.decide(
        VolitionContext(
            chain_id=chain_id,
            step="agent",
            actor="ester",
            intent=str(ctx.get("intent") or "agent_runner_dispatch"),
            needs=["agents.run"],
            budgets=base_budgets,
            metadata={"agent_id": aid, "run_id": run_id, "plan_id": plan_id},
        )
    )
    if not dec_agent.allowed:
        _rollback_slot_a(f"agent_denied:{dec_agent.reason_code}")
        save_state(
            aid,
            {
                "status": "failed",
                "current_run_id": run_id,
                "plan_id": plan_id,
                "next_step_index": start_step,
                "paused_reason": "",
                "pending_request_id": "",
                "last_error": str(dec_agent.reason_code),
            },
        )
        _emit_outbox(
            agent_id=aid,
            chain_id=chain_id,
            status="denied_agent",
            reason=dec_agent.reason_code,
        )
        return {
            "ok": False,
            "error": "volition_denied",
            "denied_at": "agent",
            "reason_code": dec_agent.reason_code,
            "reason": dec_agent.reason,
            "agent_id": aid,
            "chain_id": chain_id,
            "run_id": run_id,
        }

    steps_out: List[Dict[str, Any]] = []
    all_ok = True
    denied_at = ""
    deny_reason = ""
    paused_reason = ""
    pending_request_id = ""
    failure_step_index = 0

    for idx, step in enumerate(steps_all, start=1):
        if idx < start_step:
            continue
        action_id = str(step.get("action") or step.get("action_id") or "").strip()
        action_kind = _normalize_action_kind(action_id)
        args = dict(step.get("args") or {})
        step_budgets = dict(base_budgets)
        step_budgets.update(dict(step.get("budgets") or {}))
        if action_id not in allowed_actions and action_kind not in allowed_actions:
            all_ok = False
            denied_at = "action"
            deny_reason = "action_not_allowed_by_spec"
            failure_step_index = idx
            _append_run_step_deny(
                agent_id=aid,
                run_id=run_id,
                plan_id=plan_id,
                step_index=idx,
                action_id=action_id,
                reason_code="ACTION_NOT_ALLOWED",
                reason="action_not_allowed_by_spec",
                allowlist=allowed_actions,
            )
            _rollback_slot_a(f"action_not_allowed:{action_id}")
            _emit_outbox(
                agent_id=aid,
                chain_id=chain_id,
                status="denied_action",
                reason="action_not_allowed_by_spec",
                action_id=action_id,
            )
            steps_out.append(
                {
                    "index": idx,
                    "action_id": action_id,
                    "ok": False,
                    "error": "action_not_allowed_by_spec",
                }
            )
            break

        dec_action = gate.decide(
            VolitionContext(
                chain_id=chain_id,
                step="action",
                actor=f"agent:{aid}",
                intent=str(ctx.get("intent") or f"run:{action_kind}"),
                action_kind=action_kind,
                needs=_step_needs(action_kind),
                budgets=step_budgets,
                metadata={"agent_id": aid, "step": idx, "run_id": run_id, "plan_id": plan_id},
            )
        )
        if not dec_action.allowed:
            all_ok = False
            denied_at = "action"
            deny_reason = dec_action.reason_code
            failure_step_index = idx
            _rollback_slot_a(f"action_denied:{dec_action.reason_code}")
            _emit_outbox(
                agent_id=aid,
                chain_id=chain_id,
                status="denied_action",
                reason=dec_action.reason_code,
                action_id=action_id,
            )
            steps_out.append(
                {
                    "index": idx,
                    "action_id": action_id,
                    "ok": False,
                    "error": "volition_denied",
                    "reason_code": dec_action.reason_code,
                    "reason": dec_action.reason,
                }
            )
            break

        exec_action_id = action_kind
        exec_args = dict(args)
        if _is_oracle_action(action_kind):
            exec_action_id = "llm.remote.call"
            exec_args["actor"] = str(exec_args.get("actor") or f"agent:{aid}")
            exec_args["agent_id"] = str(exec_args.get("agent_id") or aid)
            exec_args["plan_id"] = str(exec_args.get("plan_id") or plan_id)
            exec_args["step_index"] = int(exec_args.get("step_index") or idx)
            if not str(exec_args.get("purpose") or "").strip():
                exec_args["purpose"] = str(exec_args.get("reason") or f"agent_runner:{aid}:step{idx}")
            exec_args["model"] = str(exec_args.get("model") or "gpt-4o-mini").strip() or "gpt-4o-mini"

            current_window_id = ""
            try:
                cur = oracle_window.current_window()
                if isinstance(cur, dict) and bool(cur.get("open")):
                    current_window_id = str(cur.get("window_id") or "")
            except Exception:
                current_window_id = ""

            request_id = str(exec_args.get("request_id") or "").strip()
            request_ok = False
            if request_id:
                chk = oracle_requests.validate_approved_request(
                    request_id=request_id,
                    agent_id=str(exec_args.get("agent_id") or ""),
                    plan_id=str(exec_args.get("plan_id") or ""),
                    step_index=exec_args.get("step_index"),
                    model=str(exec_args.get("model") or ""),
                    window_id=current_window_id,
                )
                request_ok = bool(chk.get("ok"))

            if (not request_ok) and (not request_id):
                approved = _find_request_for_step(
                    agent_id=str(exec_args.get("agent_id") or ""),
                    plan_id=str(exec_args.get("plan_id") or ""),
                    step_index=int(exec_args.get("step_index") or idx),
                    model=str(exec_args.get("model") or ""),
                    statuses=["approved"],
                )
                if approved:
                    request_id = str(approved.get("request_id") or "").strip()
                    if request_id:
                        chk = oracle_requests.validate_approved_request(
                            request_id=request_id,
                            agent_id=str(exec_args.get("agent_id") or ""),
                            plan_id=str(exec_args.get("plan_id") or ""),
                            step_index=exec_args.get("step_index"),
                            model=str(exec_args.get("model") or ""),
                            window_id=current_window_id,
                        )
                        request_ok = bool(chk.get("ok"))

            if request_ok and request_id:
                exec_args["request_id"] = request_id
            else:
                pending = _find_request_for_step(
                    agent_id=str(exec_args.get("agent_id") or ""),
                    plan_id=str(exec_args.get("plan_id") or ""),
                    step_index=int(exec_args.get("step_index") or idx),
                    model=str(exec_args.get("model") or ""),
                    statuses=["pending"],
                )
                if pending:
                    request_id = str(pending.get("request_id") or "").strip()
                if not request_id:
                    request_rep = oracle_requests.submit_request(
                        agent_id=str(exec_args.get("agent_id") or ""),
                        plan_id=str(exec_args.get("plan_id") or ""),
                        step_index=exec_args.get("step_index"),
                        action_id="llm.remote.call",
                        model=str(exec_args.get("model") or ""),
                        purpose=str(exec_args.get("purpose") or ""),
                        prompt_digest=_oracle_prompt_digest(exec_args),
                        budgets_requested={
                            "max_tokens": int(exec_args.get("max_tokens") or 256),
                            "timeout_sec": int(exec_args.get("timeout") or 20),
                            "max_work_ms": int(step_budgets.get("max_work_ms") or 0),
                            "window_sec": int(step_budgets.get("window") or 0),
                        },
                    )
                    request_id = str(request_rep.get("request_id") or "").strip()

                paused_reason = "pending_oracle"
                pending_request_id = request_id
                denied_at = "pending_oracle"
                deny_reason = "pending_oracle"
                pause_run(
                    aid,
                    run_id,
                    plan_id,
                    idx,
                    "pending_oracle",
                    request_id=request_id,
                )
                _emit_outbox(
                    agent_id=aid,
                    chain_id=chain_id,
                    status="pending_oracle",
                    reason=f"request_id={request_id}",
                    action_id="llm.remote.call",
                )
                steps_out.append(
                    {
                        "index": idx,
                        "action_id": "llm.remote.call",
                        "ok": True,
                        "pending_oracle": True,
                        "request_id": request_id,
                        "result": {"ok": True, "status": "pending_oracle", "request_id": request_id},
                    }
                )
                break

        try:
            step_rep = _exec_action(aid, exec_action_id, exec_args, gate, step_budgets)
        except Exception as exc:
            _rollback_slot_a(f"action_exception:{exc.__class__.__name__}")
            step_rep = {"ok": False, "error": "action_exception", "detail": exc.__class__.__name__}
            _emit_outbox(
                agent_id=aid,
                chain_id=chain_id,
                status="exception",
                reason=exc.__class__.__name__,
                action_id=action_id,
            )

        row = {
            "index": idx,
            "action_id": exec_action_id,
            "ok": bool(step_rep.get("ok")),
            "result": step_rep,
        }
        steps_out.append(row)
        if not row["ok"]:
            all_ok = False
            denied_at = "action"
            deny_reason = str(step_rep.get("error") or "action_failed")
            failure_step_index = idx
            paused_reason = "error"
            pending_request_id = str(step_rep.get("request_id") or "")
            pause_run(
                aid,
                run_id,
                plan_id,
                idx,
                "error",
                request_id=pending_request_id,
                last_error=deny_reason,
            )
            _emit_outbox(
                agent_id=aid,
                chain_id=chain_id,
                status="failed_action",
                reason=deny_reason,
                action_id=exec_action_id,
            )
            break

        save_state(
            aid,
            {
                "status": "running",
                "current_run_id": run_id,
                "plan_id": plan_id,
                "next_step_index": idx + 1,
                "paused_reason": "",
                "pending_request_id": "",
                "last_error": "",
                "retries": retries_map,
                "plan": plan,
            },
        )

    if paused_reason:
        final_state = load_state(aid)
    elif all_ok:
        final_state = save_state(
            aid,
            {
                "status": "done",
                "current_run_id": run_id,
                "plan_id": plan_id,
                "next_step_index": max(total_steps + 1, start_step),
                "paused_reason": "",
                "pending_request_id": "",
                "last_error": "",
                "retries": retries_map,
                "plan": plan,
            },
        )
    else:
        final_state = save_state(
            aid,
            {
                "status": "failed",
                "current_run_id": run_id,
                "plan_id": plan_id,
                "next_step_index": max(1, failure_step_index or start_step),
                "paused_reason": "",
                "pending_request_id": "",
                "last_error": deny_reason,
                "retries": retries_map,
                "plan": plan,
            },
        )

    is_pending_pause = str(final_state.get("paused_reason") or "") == "pending_oracle"
    ok_out = bool(all_ok) or bool(is_pending_pause)

    out = {
        "ok": bool(ok_out),
        "agent_id": aid,
        "chain_id": chain_id,
        "plan_id": plan_id,
        "run_id": run_id,
        "steps_total": total_steps,
        "steps_done": len(steps_out),
        "steps": steps_out,
        "denied_at": denied_at,
        "reason": deny_reason,
        "status": str(final_state.get("status") or "idle"),
        "paused": bool(str(final_state.get("status") or "") == "paused"),
        "pause_reason": str(final_state.get("paused_reason") or ""),
        "pending_request_id": str(final_state.get("pending_request_id") or ""),
        "next_step_index": int(final_state.get("next_step_index") or 0),
        "retries": dict(final_state.get("retries") or {}),
        "can_resume": bool(can_resume(aid, final_state)),
        "journal_path": str(journal_path()),
        "state_path": str(_state_path(aid)),
        "slot": _slot(),
        "slot_b_disabled_in_process": bool(_SLOTB_DISABLED),
    }
    if runtime_warnings:
        out["warnings"] = [str(x) for x in runtime_warnings]
    _append_run(
        aid,
        {
            "event": "result",
            "run_id": run_id,
            "plan_id": plan_id,
            "agent_id": aid,
            "ok": bool(ok_out),
            "status": str(final_state.get("status") or "idle"),
            "steps_total": out["steps_total"],
            "steps_done": out["steps_done"],
            "denied_at": denied_at,
            "reason": deny_reason,
            "paused": bool(out["paused"]),
            "paused_reason": out["pause_reason"],
            "pending_request_id": out["pending_request_id"],
            "next_step_index": out["next_step_index"],
            "slot": out["slot"],
        },
    )
    if str(final_state.get("status") or "") == "done":
        _emit_outbox(
            agent_id=aid,
            chain_id=chain_id,
            status="executed",
            reason=f"steps={out['steps_done']}",
        )
    return out


__all__ = [
    "run_once",
    "load_state",
    "save_state",
    "pause_run",
    "can_resume",
    "resume_run",
]
