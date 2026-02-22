# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_ID = "ester.plan.v1"
MAX_STEPS_HARD = 64
MAX_ACTION_LEN = 120
MAX_WHY_LEN = 500
MAX_ARGS_BYTES = 32 * 1024
MAX_ARGS_DEPTH = 8

_LOCK = threading.RLock()
_STRICT_ERR_STREAK = 0
_STRICT_DISABLED = False


def _slot() -> str:
    raw = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if raw == "B" else "A"


def _strict_fail_max() -> int:
    try:
        return max(1, int(os.getenv("ESTER_PLAN_SCHEMA_STRICT_FAIL_MAX", "3") or "3"))
    except Exception:
        return 3


def strict_enabled() -> bool:
    with _LOCK:
        return bool(_slot() == "B" and (not _STRICT_DISABLED))


def strict_status() -> Dict[str, Any]:
    with _LOCK:
        return {
            "slot": _slot(),
            "strict_enabled": bool(_slot() == "B" and (not _STRICT_DISABLED)),
            "strict_disabled": bool(_STRICT_DISABLED),
            "strict_err_streak": int(_STRICT_ERR_STREAK),
            "strict_fail_max": int(_strict_fail_max()),
        }


def note_strict_success() -> Dict[str, Any]:
    global _STRICT_ERR_STREAK
    with _LOCK:
        _STRICT_ERR_STREAK = 0
    return strict_status()


def note_strict_exception(where: str, exc: Exception) -> Dict[str, Any]:
    global _STRICT_ERR_STREAK, _STRICT_DISABLED
    with _LOCK:
        _STRICT_ERR_STREAK += 1
        if _STRICT_ERR_STREAK >= _strict_fail_max():
            _STRICT_DISABLED = True
            os.environ["ESTER_PLAN_SCHEMA_STRICT_DISABLED"] = "1"
            os.environ["ESTER_PLAN_SCHEMA_LAST_ROLLBACK_REASON"] = f"{where}:{exc.__class__.__name__}"
    return strict_status()


def _detail(level: str, code: str, message: str, **extra: Any) -> Dict[str, Any]:
    row = {
        "level": str(level or "error"),
        "code": str(code or "invalid"),
        "message": str(message or ""),
    }
    if extra:
        row.update(dict(extra))
    return row


def _canonical_action(action: str) -> str:
    a = str(action or "").strip()
    if a == "oracle.openai.call":
        return "llm.remote.call"
    return a


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _json_depth(value: Any, depth: int = 0) -> int:
    if depth > 64:
        return depth
    if isinstance(value, dict):
        d = depth
        for k, v in value.items():
            d = max(d, _json_depth(k, depth + 1), _json_depth(v, depth + 1))
        return d
    if isinstance(value, list):
        d = depth
        for v in value:
            d = max(d, _json_depth(v, depth + 1))
        return d
    return depth


def _meta_valid(value: Any, *, max_depth: int = 8) -> bool:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return True
    if isinstance(value, list):
        if _json_depth(value) > max_depth:
            return False
        return all(_meta_valid(v, max_depth=max_depth) for v in value)
    if isinstance(value, dict):
        if _json_depth(value) > max_depth:
            return False
        for k, v in value.items():
            if not isinstance(k, str):
                return False
            if not _meta_valid(v, max_depth=max_depth):
                return False
        return True
    return False


def _hash_seed(src: Dict[str, Any]) -> str:
    safe = {
        "title": str(src.get("title") or ""),
        "intent": str(src.get("intent") or ""),
        "initiative_id": str(src.get("initiative_id") or ""),
        "agent_id": str(src.get("agent_id") or ""),
        "template_id": str(src.get("template_id") or ""),
        "steps": list(src.get("steps") or []),
    }
    raw = json.dumps(safe, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def normalize_plan(obj: Dict[str, Any]) -> Dict[str, Any]:
    details: List[Dict[str, Any]] = []
    if not isinstance(obj, dict):
        return {"ok": False, "plan": None, "error": "plan_not_object", "details": [_detail("error", "plan_not_object", "plan must be a dict")]}

    src = dict(obj or {})
    allowed_plan_keys = {
        "schema",
        "plan_id",
        "steps",
        "created_ts",
        "title",
        "intent",
        "initiative_id",
        "agent_id",
        "template_id",
        "budgets",
        "meta",
    }
    unknown_plan_keys = sorted([k for k in src.keys() if str(k) not in allowed_plan_keys])
    if unknown_plan_keys:
        details.append(
            _detail(
                "warn",
                "unknown_plan_keys",
                "plan contains unknown top-level keys",
                keys=unknown_plan_keys,
            )
        )

    steps_raw = src.get("steps")
    if not isinstance(steps_raw, list):
        return {
            "ok": False,
            "plan": None,
            "error": "plan_steps_required",
            "details": details + [_detail("error", "plan_steps_required", "steps must be a list")],
        }

    steps: List[Dict[str, Any]] = []
    allowed_step_keys = {"action", "action_id", "args", "why"}
    for idx, row in enumerate(list(steps_raw), start=1):
        if not isinstance(row, dict):
            details.append(_detail("error", "step_not_object", "step must be an object", step_index=idx))
            continue

        unknown_step_keys = sorted([k for k in row.keys() if str(k) not in allowed_step_keys])
        if unknown_step_keys:
            details.append(
                _detail(
                    "warn",
                    "unknown_step_keys",
                    "step contains unknown keys",
                    step_index=idx,
                    keys=unknown_step_keys,
                )
            )

        action_raw = row.get("action")
        if not str(action_raw or "").strip():
            action_raw = row.get("action_id")
        action = _canonical_action(str(action_raw or "").strip())
        if not action:
            details.append(_detail("error", "step_action_required", "step.action is required", step_index=idx))
            continue

        args_raw = row.get("args", {})
        if args_raw is None:
            args_raw = {}
        if not isinstance(args_raw, dict):
            details.append(_detail("error", "step_args_type", "step.args must be an object", step_index=idx))
            continue
        args = dict(args_raw)

        why_raw = row.get("why")
        if why_raw is None or str(why_raw).strip() == "":
            why = f"agent_step:{action}"
        else:
            why = str(why_raw)

        steps.append({"action": action, "args": args, "why": why})

    plan_id = str(src.get("plan_id") or "").strip()
    if not plan_id:
        plan_id = "plan_" + _hash_seed({"steps": steps, **src})[:12]

    out: Dict[str, Any] = {
        "schema": SCHEMA_ID,
        "plan_id": plan_id,
        "steps": steps,
    }

    if "created_ts" in src and src.get("created_ts") is not None:
        out["created_ts"] = _safe_int(src.get("created_ts"), int(time.time()))
    for key in ("title", "intent", "initiative_id", "agent_id", "template_id"):
        if key in src and src.get(key) is not None:
            out[key] = str(src.get(key))

    budgets = src.get("budgets")
    if budgets is not None:
        if not isinstance(budgets, dict):
            details.append(_detail("error", "budgets_type", "budgets must be an object"))
        else:
            b_src = dict(budgets or {})
            b_out: Dict[str, Any] = {}
            if "max_ms" in b_src:
                b_out["max_ms"] = max(1, _safe_int(b_src.get("max_ms"), 0))
            if "max_steps" in b_src:
                b_out["max_steps"] = max(1, _safe_int(b_src.get("max_steps"), 0))
            if "window_sec" in b_src:
                b_out["window_sec"] = max(1, _safe_int(b_src.get("window_sec"), 0))
            if "oracle_window" in b_src and b_src.get("oracle_window") is not None:
                b_out["oracle_window"] = str(b_src.get("oracle_window"))
            unknown_budget_keys = sorted([k for k in b_src.keys() if str(k) not in {"max_ms", "max_steps", "window_sec", "oracle_window"}])
            if unknown_budget_keys:
                details.append(_detail("warn", "unknown_budget_keys", "budgets contains unknown keys", keys=unknown_budget_keys))
            out["budgets"] = b_out

    meta = src.get("meta")
    if meta is not None:
        if not isinstance(meta, dict):
            details.append(_detail("error", "meta_type", "meta must be an object"))
        elif not _meta_valid(meta, max_depth=MAX_ARGS_DEPTH):
            details.append(_detail("error", "meta_invalid", "meta must contain JSON-safe values within depth limits"))
        else:
            out["meta"] = dict(meta)

    errors = [d for d in details if str(d.get("level") or "") == "error"]
    if errors:
        return {"ok": False, "plan": out, "error": str(errors[0].get("code") or "plan_invalid"), "details": details}
    return {"ok": True, "plan": out, "error": "", "details": details}


def _registry_has_action(registry: Any, action_id: str) -> bool:
    aid = str(action_id or "").strip()
    if not aid:
        return False
    try:
        if hasattr(registry, "has_action") and callable(registry.has_action):
            return bool(registry.has_action(aid))
    except Exception:
        pass
    try:
        if hasattr(registry, "list_action_ids") and callable(registry.list_action_ids):
            return aid in set([str(x) for x in list(registry.list_action_ids() or []) if str(x).strip()])
    except Exception:
        pass
    try:
        if hasattr(registry, "list_registered") and callable(registry.list_registered):
            reg = registry.list_registered()
            if isinstance(reg, dict):
                return aid in reg
    except Exception:
        pass
    return False


def _plan_hash(plan: Dict[str, Any]) -> str:
    src = dict(plan or {})
    src.pop("created_ts", None)
    raw = json.dumps(src, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_plan(plan: Dict[str, Any], *, registry: Any) -> Dict[str, Any]:
    details: List[Dict[str, Any]] = []
    if not isinstance(plan, dict):
        return {"ok": False, "error": "plan_not_object", "details": [_detail("error", "plan_not_object", "plan must be an object")], "plan_hash": ""}

    src = dict(plan or {})
    schema = str(src.get("schema") or "").strip()
    if schema != SCHEMA_ID:
        details.append(_detail("error", "schema_invalid", "schema must be ester.plan.v1", schema=schema))

    plan_id = str(src.get("plan_id") or "").strip()
    if not plan_id:
        details.append(_detail("error", "plan_id_required", "plan_id is required"))

    steps = src.get("steps")
    if not isinstance(steps, list):
        details.append(_detail("error", "plan_steps_required", "steps must be a list"))
        steps = []

    max_steps = MAX_STEPS_HARD
    budgets = src.get("budgets")
    if budgets is not None and isinstance(budgets, dict):
        if "max_steps" in budgets:
            max_steps = min(MAX_STEPS_HARD, max(1, _safe_int(budgets.get("max_steps"), MAX_STEPS_HARD)))
    if len(steps) <= 0:
        details.append(_detail("error", "plan_steps_required", "steps must contain at least one step"))
    if len(steps) > max_steps:
        details.append(_detail("error", "plan_steps_limit", "steps exceed max_steps", limit=max_steps, count=len(steps)))

    allowed_step_keys = {"action", "action_id", "args", "why"}
    for idx, row in enumerate(list(steps), start=1):
        if not isinstance(row, dict):
            details.append(_detail("error", "step_not_object", "step must be an object", step_index=idx))
            continue
        unknown_keys = sorted([k for k in row.keys() if str(k) not in allowed_step_keys])
        if unknown_keys:
            details.append(_detail("error", "unknown_step_keys", "unknown step keys are forbidden", step_index=idx, keys=unknown_keys))

        action_raw = row.get("action")
        if not str(action_raw or "").strip():
            action_raw = row.get("action_id")
        action = _canonical_action(str(action_raw or "").strip())
        if not action:
            details.append(_detail("error", "step_action_required", "step.action is required", step_index=idx))
            continue
        if len(action) > MAX_ACTION_LEN:
            details.append(_detail("error", "step_action_too_long", "action length exceeds limit", step_index=idx, limit=MAX_ACTION_LEN))
        if not _registry_has_action(registry, action):
            details.append(_detail("error", "unknown_action", "action is not registered", step_index=idx, action=action))

        why = str(row.get("why") or "")
        if len(why) > MAX_WHY_LEN:
            details.append(_detail("error", "step_why_too_long", "why length exceeds limit", step_index=idx, limit=MAX_WHY_LEN))

        args = row.get("args", {})
        if args is None:
            args = {}
        if not isinstance(args, dict):
            details.append(_detail("error", "step_args_type", "step.args must be an object", step_index=idx))
            continue
        depth = _json_depth(args)
        if depth > MAX_ARGS_DEPTH:
            details.append(_detail("error", "step_args_depth", "step.args depth exceeds limit", step_index=idx, depth=depth, limit=MAX_ARGS_DEPTH))
        try:
            args_dump = json.dumps(args, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            args_size = len(args_dump.encode("utf-8"))
        except Exception as exc:
            details.append(_detail("error", "step_args_json_invalid", "step.args must be JSON serializable", step_index=idx, detail=str(exc)))
            args_size = MAX_ARGS_BYTES + 1
        if args_size > MAX_ARGS_BYTES:
            details.append(_detail("error", "step_args_too_large", "step.args exceeds size limit", step_index=idx, size=args_size, limit=MAX_ARGS_BYTES))

    # Validate optional top-level fields and unknown keys.
    allowed_plan_keys = {
        "schema",
        "plan_id",
        "steps",
        "created_ts",
        "title",
        "intent",
        "initiative_id",
        "agent_id",
        "template_id",
        "budgets",
        "meta",
    }
    unknown_plan_keys = sorted([k for k in src.keys() if str(k) not in allowed_plan_keys])
    if unknown_plan_keys:
        details.append(_detail("error", "unknown_plan_keys", "unknown top-level plan keys are forbidden", keys=unknown_plan_keys))

    if "title" in src and src.get("title") is not None and not isinstance(src.get("title"), str):
        details.append(_detail("error", "title_type", "title must be a string"))
    if "intent" in src and src.get("intent") is not None and not isinstance(src.get("intent"), str):
        details.append(_detail("error", "intent_type", "intent must be a string"))
    if "initiative_id" in src and src.get("initiative_id") is not None and not isinstance(src.get("initiative_id"), str):
        details.append(_detail("error", "initiative_id_type", "initiative_id must be a string"))
    if "agent_id" in src and src.get("agent_id") is not None and not isinstance(src.get("agent_id"), str):
        details.append(_detail("error", "agent_id_type", "agent_id must be a string"))
    if "template_id" in src and src.get("template_id") is not None and not isinstance(src.get("template_id"), str):
        details.append(_detail("error", "template_id_type", "template_id must be a string"))
    if "created_ts" in src and src.get("created_ts") is not None and (not isinstance(src.get("created_ts"), int)):
        details.append(_detail("error", "created_ts_type", "created_ts must be an int"))

    if "meta" in src and src.get("meta") is not None:
        meta = src.get("meta")
        if not isinstance(meta, dict):
            details.append(_detail("error", "meta_type", "meta must be an object"))
        elif (not _meta_valid(meta, max_depth=MAX_ARGS_DEPTH)):
            details.append(_detail("error", "meta_invalid", "meta must contain JSON-safe values within depth limits"))

    if "budgets" in src and src.get("budgets") is not None:
        b = src.get("budgets")
        if not isinstance(b, dict):
            details.append(_detail("error", "budgets_type", "budgets must be an object"))
        else:
            allowed_budget_keys = {"max_ms", "max_steps", "window_sec", "oracle_window"}
            unknown_budget_keys = sorted([k for k in b.keys() if str(k) not in allowed_budget_keys])
            if unknown_budget_keys:
                details.append(_detail("error", "unknown_budget_keys", "unknown budgets keys are forbidden", keys=unknown_budget_keys))
            if "max_ms" in b and (not isinstance(b.get("max_ms"), int)):
                details.append(_detail("error", "budget_max_ms_type", "budgets.max_ms must be int"))
            if "max_steps" in b and (not isinstance(b.get("max_steps"), int)):
                details.append(_detail("error", "budget_max_steps_type", "budgets.max_steps must be int"))
            if "window_sec" in b and (not isinstance(b.get("window_sec"), int)):
                details.append(_detail("error", "budget_window_sec_type", "budgets.window_sec must be int"))
            if "oracle_window" in b and b.get("oracle_window") is not None and (not isinstance(b.get("oracle_window"), str)):
                details.append(_detail("error", "budget_oracle_window_type", "budgets.oracle_window must be str"))

    errors = [d for d in details if str(d.get("level") or "") == "error"]
    ph = ""
    try:
        ph = _plan_hash(src)
    except Exception:
        ph = hashlib.sha256(uuid.uuid4().hex.encode("utf-8")).hexdigest()
    if errors:
        return {"ok": False, "error": str(errors[0].get("code") or "plan_invalid"), "details": details, "plan_hash": ph}
    return {"ok": True, "error": "", "details": details, "plan_hash": ph}


def load_plan_from_path(path: str) -> Dict[str, Any]:
    p = Path(str(path or "")).resolve()
    if not str(path or "").strip():
        return {"ok": False, "plan": None, "error": "path_required", "details": [_detail("error", "path_required", "path is required")]}
    if not p.exists():
        return {"ok": False, "plan": None, "error": "path_not_found", "details": [_detail("error", "path_not_found", "plan path does not exist", path=str(p))]}
    if not p.is_file():
        return {"ok": False, "plan": None, "error": "path_not_file", "details": [_detail("error", "path_not_file", "plan path must be a file", path=str(p))]}

    suffix = p.suffix.lower()
    try:
        text = p.read_text(encoding="utf-8")
    except Exception as exc:
        return {"ok": False, "plan": None, "error": "path_read_failed", "details": [_detail("error", "path_read_failed", str(exc), path=str(p))]}

    parsed: Any
    if suffix == ".json":
        try:
            parsed = json.loads(text)
        except Exception as exc:
            return {"ok": False, "plan": None, "error": "json_invalid", "details": [_detail("error", "json_invalid", str(exc), path=str(p))]}
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except Exception:
            return {
                "ok": False,
                "plan": None,
                "error": "yaml_not_supported_no_deps",
                "details": [_detail("error", "yaml_not_supported_no_deps", "PyYAML is not installed", path=str(p))],
            }
        try:
            parsed = yaml.safe_load(text)
        except Exception as exc:
            return {"ok": False, "plan": None, "error": "yaml_invalid", "details": [_detail("error", "yaml_invalid", str(exc), path=str(p))]}
    else:
        return {"ok": False, "plan": None, "error": "unsupported_extension", "details": [_detail("error", "unsupported_extension", "use .json/.yaml/.yml", path=str(p))]}

    if isinstance(parsed, list):
        parsed = {"steps": parsed}
    if not isinstance(parsed, dict):
        return {"ok": False, "plan": None, "error": "plan_not_object", "details": [_detail("error", "plan_not_object", "loaded plan must be object", path=str(p))]}
    return normalize_plan(parsed)


__all__ = [
    "SCHEMA_ID",
    "load_plan_from_path",
    "normalize_plan",
    "validate_plan",
    "strict_enabled",
    "strict_status",
    "note_strict_success",
    "note_strict_exception",
]
