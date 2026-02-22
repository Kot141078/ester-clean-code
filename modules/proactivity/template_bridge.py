# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict, List

try:
    from modules.garage.templates import get_template  # type: ignore
except Exception:  # pragma: no cover
    get_template = None  # type: ignore


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "on", "y"}:
        return True
    if s in {"0", "false", "no", "off", "n"}:
        return False
    return bool(default)


def _run_safe_enabled() -> bool:
    return _as_bool(os.getenv("ESTER_PROACTIVITY_RUN_SAFE", "0"), False)


def _normalize_tokens(initiative: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key in ("title", "text", "kind", "source", "priority"):
        val = str(initiative.get(key) or "").strip().lower()
        if val:
            out.append(val)
    for tag in list(initiative.get("tags") or []):
        sval = str(tag or "").strip().lower()
        if sval:
            out.append(sval)
    return out


def _contains_any(tokens: List[str], words: List[str]) -> bool:
    hay = " ".join(tokens)
    return any(w in hay for w in words)


def _template_allowed_actions(template_id: str) -> List[str]:
    if get_template is None:
        return []
    try:
        tpl = get_template(template_id)
        if not isinstance(tpl, dict):
            return []
        vals = list(tpl.get("available_actions") or tpl.get("default_allowed_actions") or [])
        return [str(x) for x in vals if str(x).strip()]
    except Exception:
        return []


def _template_capabilities(template_id: str) -> List[str]:
    if get_template is None:
        return []
    try:
        tpl = get_template(template_id)
        if not isinstance(tpl, dict):
            return []
        vals = list(tpl.get("capabilities_effective") or tpl.get("capabilities") or [])
        return [str(x) for x in vals if str(x).strip()]
    except Exception:
        return []


def select_template(initiative: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic initiative -> garage template mapping.
    """
    src = dict(initiative or {})
    tokens = _normalize_tokens(src)
    run_safe = _run_safe_enabled()

    template_id = "planner.v1"
    role = "planner"
    risk = "low"
    needs_oracle = False

    if _contains_any(tokens, ["oracle", "openai", "remote", "internet", "web search", "llm"]):
        template_id = "oracle.v1"
        role = "oracle"
        risk = "high"
        needs_oracle = True
    elif _contains_any(tokens, ["review", "lint", "check", "audit", "qa", "quality", "registry"]):
        template_id = "reviewer.v1"
        role = "reviewer"
        risk = "low"
    elif _contains_any(tokens, ["dream", "son", "mecht"]):
        template_id = "dreamer.v1"
        role = "dreamer"
        risk = "low"
    elif _contains_any(tokens, ["archive", "summary", "ingest", "arkhiv", "svodk"]):
        template_id = "archivist.v1"
        role = "archivist"
        risk = "low"
    elif _contains_any(tokens, ["initiative", "queue", "follow-up", "initsiativ"]):
        template_id = "initiator.v1"
        role = "initiator"
        risk = "low"
    elif _contains_any(tokens, ["run", "execute", "dispatch", "runner"]):
        template_id = "runner.v1" if run_safe else "reviewer.v1"
        role = "runner" if run_safe else "reviewer"
        risk = "med" if run_safe else "low"
    elif _contains_any(tokens, ["build", "patch", "file", "code", "fix"]):
        template_id = "builder.v1" if run_safe else "planner.v1"
        role = "builder" if run_safe else "planner"
        risk = "med" if run_safe else "low"

    return {
        "template_id": template_id,
        "agent_role": role,
        "risk": risk,
        "needs_oracle": bool(needs_oracle),
        "capabilities": _template_capabilities(template_id),
        "allowed_actions": _template_allowed_actions(template_id),
    }


__all__ = ["select_template"]
