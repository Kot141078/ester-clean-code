# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Tuple

from modules.garage.templates.pack_v1 import by_id as _pack_by_id

_TEMPLATES = _pack_by_id()

CAPABILITY_ACTIONS: Dict[str, List[str]] = {
    "cap.memory.note": ["memory.add_note"],
    "cap.fs.sandbox.write": ["files.sandbox_write"],
    "cap.fs.sha256.verify": ["files.sha256_verify"],
    "cap.proactivity.queue.add": ["proactivity.queue.add"],
    "cap.initiative.mark_done": ["initiative.mark_done"],
    "cap.messages.outbox": ["messages.outbox.enqueue"],
    "cap.messages.telegram": ["messages.telegram.send"],
    "cap.oracle.remote.call": ["llm.remote.call"],
}

# Template-stable IDs -> project action IDs.
STABLE_ACTION_ALIASES: Dict[str, List[str]] = {
    "fs.list": ["files.list", "fs.list"],
    "fs.read": ["files.read", "fs.read"],
    "memory.ingest": ["memory.ingest"],
    "memory.add_note": ["memory.add_note"],
    "messages.outbox.enqueue": ["messages.outbox.enqueue"],
    "messages.telegram.send": ["messages.telegram.send"],
    "dreams.run_once": ["dreams.run_once", "dreams.generate"],
    "dreams.generate": ["dreams.generate", "dreams.run_once"],
    "initiatives.run_once": ["initiatives.run_once", "initiative.run_once"],
    "proactivity.queue.add": ["proactivity.queue.add"],
    "initiative.mark_done": ["initiative.mark_done"],
    "plan.build": ["plan.build", "planner.build"],
    "fs.write": ["files.sandbox_write", "files.write", "fs.write"],
    "fs.patch": ["files.patch", "files.sandbox_write", "fs.patch"],
    "fs.hash": ["files.sha256_verify", "files.hash", "fs.hash"],
    "run_checks_offline": ["tools.run_checks_offline", "checks.run_offline", "run_checks_offline"],
    "route_registry_check": ["tools.route_registry_check", "checks.route_registry_check", "route_registry_check"],
    "route_return_lint": ["tools.route_return_lint", "checks.route_return_lint", "route_return_lint"],
    "agent.run_once": ["agent.run_once"],
    "llm.remote.call": ["oracle.openai.call", "llm.remote.call"],
}

_DIRECT_RUNNER_ACTIONS = {
    "files.sandbox_write",
    "files.sha256_verify",
    "plan.build",
    "memory.add_note",
    "initiative.mark_done",
    "proactivity.queue.add",
    "messages.outbox.enqueue",
    "messages.telegram.send",
    "oracle.openai.call",
}

_BOOL_TRUE = {"1", "true", "yes", "on", "y"}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in _BOOL_TRUE


def _dedupe(items: List[str]) -> List[str]:
    out: List[str] = []
    for item in list(items or []):
        s = str(item or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def _available_actions() -> set[str]:
    out = set(_DIRECT_RUNNER_ACTIONS)
    try:
        from modules.thinking import action_registry

        if hasattr(action_registry, "list_action_ids") and callable(action_registry.list_action_ids):
            out.update(str(k).strip() for k in list(action_registry.list_action_ids() or []) if str(k).strip())
        else:
            out.update(str(k).strip() for k in action_registry.list_registered().keys() if str(k).strip())
    except Exception:
        pass
    return out


def _capabilities_list(raw: Any) -> List[str]:
    return _dedupe([str(x) for x in list(raw or []) if str(x).strip()])


def _action_known(action_id: str, registry: Any, available: set[str]) -> bool:
    aid = str(action_id or "").strip()
    if not aid:
        return False
    try:
        if registry is not None and hasattr(registry, "has_action") and callable(registry.has_action):
            return bool(registry.has_action(aid))
    except Exception:
        pass
    return aid in available


def resolve_allowed_actions(capabilities: List[str], registry: Any = None) -> List[str]:
    """
    Resolve deterministic allowlist from capability IDs.
    Unknown capability/action raises ValueError (fail-closed contract).
    """
    caps = _capabilities_list(capabilities)
    available = _available_actions()
    out: List[str] = []
    for cap in caps:
        mapped = list(CAPABILITY_ACTIONS.get(cap) or [])
        if not mapped:
            raise ValueError(f"unknown_capability:{cap}")
        for action_id in mapped:
            aid = str(action_id or "").strip()
            if not aid:
                continue
            if not _action_known(aid, registry, available):
                raise ValueError(f"unknown_action_for_capability:{cap}:{aid}")
            out.append(aid)
    return sorted(_dedupe(out))


def _resolve_alias(stable_action_id: str, available: set[str]) -> str:
    stable = str(stable_action_id or "").strip()
    if not stable:
        return ""
    for candidate in STABLE_ACTION_ALIASES.get(stable, [stable]):
        c = str(candidate or "").strip()
        if c and c in available:
            return c
    return ""


def _normalize_budgets(raw: Any) -> Dict[str, int]:
    src = dict(raw or {})
    max_steps = int(src.get("max_steps") or src.get("max_actions") or 4)
    max_work_ms = int(src.get("max_work_ms") or 2000)
    window = int(src.get("window_sec") or src.get("window") or 60)
    est_work_ms = int(src.get("est_work_ms") or min(max_work_ms, 250))
    max_steps = max(1, max_steps)
    max_work_ms = max(1, max_work_ms)
    window = max(1, window)
    est_work_ms = max(1, min(max_work_ms, est_work_ms))
    return {
        "max_actions": max_steps,
        "max_work_ms": max_work_ms,
        "window": window,
        "est_work_ms": est_work_ms,
    }


def _render_value(value: Any, values: Dict[str, Any]) -> Any:
    if isinstance(value, str):
        out = value
        for key, val in values.items():
            out = out.replace("{" + str(key) + "}", str(val))
        return out
    if isinstance(value, list):
        return [_render_value(v, values) for v in value]
    if isinstance(value, dict):
        return {str(k): _render_value(v, values) for k, v in value.items()}
    return value


def _text_bytes_for_write(content: str) -> bytes:
    text = str(content or "")
    if os.linesep != "\n":
        text = text.replace("\n", os.linesep)
    return text.encode("utf-8")


def _template_or_empty(template_id: str) -> Dict[str, Any]:
    return dict(_TEMPLATES.get(str(template_id or "").strip()) or {})


def _preferred_fallback_action(available: set[str]) -> str:
    for action in ("messages.outbox.enqueue", "memory.add_note", "files.sandbox_write"):
        if action in available:
            return action
    return ""


def _resolve_allowed_actions(
    template: Dict[str, Any],
    overrides: Dict[str, Any],
    available: set[str],
) -> Tuple[List[str], List[str], List[str], Dict[str, str], str]:
    stable_actions = _dedupe([str(x) for x in list(template.get("default_allowed_actions") or [])])
    enable_oracle = _as_bool(overrides.get("enable_oracle", False))
    enable_comm = _as_bool(overrides.get("enable_comm", False))

    resolved: List[str] = []
    missing: List[str] = []
    disabled_by_policy: List[str] = []
    alias_table: Dict[str, str] = {}
    fallback_action = _preferred_fallback_action(available)

    for stable in stable_actions:
        if stable == "llm.remote.call" and not enable_oracle:
            disabled_by_policy.append(stable)
            continue
        if stable == "messages.telegram.send" and not enable_comm:
            disabled_by_policy.append(stable)
            continue
        actual = _resolve_alias(stable, available)
        if actual:
            resolved.append(actual)
            alias_table[stable] = actual
        else:
            missing.append(stable)

    resolved = _dedupe(resolved)
    missing = _dedupe(missing)
    disabled_by_policy = _dedupe(disabled_by_policy)

    if fallback_action and ((not resolved) or missing):
        if fallback_action not in resolved:
            resolved.append(fallback_action)

    return resolved, missing, disabled_by_policy, alias_table, fallback_action


def capability_policy_filter(
    capabilities: List[str],
    *,
    enable_oracle: bool,
    enable_comm: bool,
) -> Tuple[List[str], List[str]]:
    out: List[str] = []
    disabled: List[str] = []
    for cap in _capabilities_list(capabilities):
        if cap == "cap.oracle.remote.call" and (not bool(enable_oracle)):
            disabled.append(cap)
            continue
        if cap == "cap.messages.telegram" and (not bool(enable_comm)):
            disabled.append(cap)
            continue
        out.append(cap)
    return _dedupe(out), _dedupe(disabled)


def _template_view(template: Dict[str, Any], overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    over = dict(overrides or {})
    available = _available_actions()
    enable_oracle = _as_bool(over.get("enable_oracle", False))
    enable_comm = _as_bool(over.get("enable_comm", False))
    base_caps = _capabilities_list(template.get("capabilities") or [])
    req_caps = _capabilities_list(over.get("capabilities") or (dict(over.get("overrides") or {}).get("capabilities") or []))
    capability_warnings: List[str] = []
    if base_caps:
        if req_caps:
            invalid = [x for x in req_caps if x not in base_caps]
            if invalid:
                capability_warnings.append("capabilities_not_subset_template")
            eff_caps = [x for x in req_caps if x in base_caps]
            if not eff_caps:
                eff_caps = list(base_caps)
        else:
            eff_caps = list(base_caps)
        filtered_caps, disabled_caps = capability_policy_filter(
            eff_caps,
            enable_oracle=enable_oracle,
            enable_comm=enable_comm,
        )
        disabled = ["capability:" + x for x in disabled_caps]
        alias_table = {}
        missing: List[str] = []
        try:
            resolved = resolve_allowed_actions(filtered_caps, registry=None)
        except Exception as exc:
            resolved = []
            missing = [f"capabilities_resolve_failed:{exc}"]
    else:
        filtered_caps = []
        resolved, missing, disabled, alias_table, _ = _resolve_allowed_actions(template, over, available)
    return {
        "id": str(template.get("id") or ""),
        "title": str(template.get("title") or ""),
        "description": str(template.get("description") or ""),
        "default_name": str(template.get("default_name") or ""),
        "default_goal": str(template.get("default_goal") or ""),
        "capabilities": list(base_caps),
        "capabilities_effective": list(filtered_caps),
        "capability_warnings": list(capability_warnings),
        "default_allowed_actions": _dedupe([str(x) for x in list(template.get("default_allowed_actions") or [])]),
        "available_actions": resolved,
        "missing_actions": missing,
        "disabled_by_policy": disabled,
        "partially_available": bool(missing or disabled),
        "alias_table": alias_table,
        "default_budgets": dict(template.get("default_budgets") or {}),
        "default_scopes": dict(template.get("default_scopes") or {}),
        "oracle_policy": dict(template.get("oracle_policy") or {}),
        "comm_policy": dict(template.get("comm_policy") or {}),
    }


def list_templates() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for tid in sorted(_TEMPLATES.keys()):
        tpl = dict(_TEMPLATES.get(tid) or {})
        rows.append(_template_view(tpl))
    return rows


def get_template(template_id: str) -> Dict[str, Any]:
    tpl = _template_or_empty(template_id)
    if not tpl:
        return {}
    out = _template_view(tpl)
    out["default_plan"] = deepcopy(list(tpl.get("default_plan") or []))
    if isinstance(tpl.get("plan_when_oracle_enabled"), list):
        out["plan_when_oracle_enabled"] = deepcopy(list(tpl.get("plan_when_oracle_enabled") or []))
    return out


def render_spec(template_id: str, overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    tpl = _template_or_empty(template_id)
    if not tpl:
        raise ValueError("template_not_found")

    over = dict(overrides or {})
    available = _available_actions()
    enable_oracle = _as_bool(over.get("enable_oracle", False))
    enable_comm = _as_bool(over.get("enable_comm", False))
    window_id = str(over.get("window_id") or "").strip()
    if enable_comm and not window_id:
        raise ValueError("window_id_required_for_comm")

    base_caps = _capabilities_list(tpl.get("capabilities") or [])
    req_caps = _capabilities_list(over.get("capabilities") or (dict(over.get("overrides") or {}).get("capabilities") or []))

    alias_table: Dict[str, str] = {}
    fallback_action = _preferred_fallback_action(available)
    missing: List[str] = []
    disabled: List[str] = []

    if base_caps:
        if req_caps:
            invalid_caps = [x for x in req_caps if x not in base_caps]
            if invalid_caps:
                raise ValueError("capabilities_not_subset_template")
            eff_caps = list(req_caps)
        else:
            eff_caps = list(base_caps)
        filtered_caps, disabled_caps = capability_policy_filter(
            eff_caps,
            enable_oracle=enable_oracle,
            enable_comm=enable_comm,
        )
        disabled = ["capability:" + x for x in disabled_caps]
        resolved = resolve_allowed_actions(filtered_caps, registry=None)
        capabilities_effective = list(filtered_caps)
    else:
        capabilities_effective = []
        resolved, missing, disabled, alias_table, fallback_action = _resolve_allowed_actions(tpl, over, available)

    name = str(over.get("name") or tpl.get("default_name") or tpl.get("id") or "garage.agent")
    goal = str(over.get("goal") or tpl.get("default_goal") or f"Run template {tpl.get('id')}")
    owner = str(over.get("owner") or "ester")
    budgets = _normalize_budgets({**dict(tpl.get("default_budgets") or {}), **dict(over.get("budgets") or {})})

    values = {
        "name": name,
        "goal": goal,
        "owner": owner,
        "template_id": str(tpl.get("id") or ""),
        "window_id": window_id,
    }

    oracle_policy = dict(tpl.get("oracle_policy") or {})
    oracle_policy["enabled"] = bool(enable_oracle)
    comm_policy = dict(tpl.get("comm_policy") or {})
    comm_policy["enabled"] = bool(enable_comm)

    spec = {
        "name": _render_value(name, values),
        "goal": _render_value(goal, values),
        "allowed_actions": _dedupe(resolved),
        "budgets": budgets,
        "owner": owner,
        "oracle_policy": oracle_policy,
        "comm_policy": comm_policy,
        "scopes": deepcopy(dict(tpl.get("default_scopes") or {})),
        "template_id": str(tpl.get("id") or ""),
        "capabilities": list(capabilities_effective),
        "capabilities_effective": list(capabilities_effective),
        "capabilities_base": list(base_caps),
        "template_aliases": alias_table,
        "template_missing_actions": missing,
        "template_disabled_by_policy": disabled,
        "template_fallback_action": fallback_action,
    }
    return spec


def _fallback_step(
    *,
    template_id: str,
    stable_action_id: str,
    fallback_action: str,
) -> Dict[str, Any]:
    if fallback_action == "messages.outbox.enqueue":
        return {
            "action_id": "messages.outbox.enqueue",
            "args": {
                "kind": "garage.agent.partial",
                "text": f"{template_id}: action '{stable_action_id}' unavailable, skipped.",
                "meta": {
                    "template_id": template_id,
                    "skipped_action": stable_action_id,
                },
            },
        }
    if fallback_action == "memory.add_note":
        return {
            "action_id": "memory.add_note",
            "args": {
                "text": f"{template_id}: action '{stable_action_id}' unavailable, skipped.",
                "tags": ["garage", "template", "partial"],
                "source": "garage.templates.registry",
            },
        }
    if fallback_action == "files.sandbox_write":
        return {
            "action_id": "files.sandbox_write",
            "args": {
                "relpath": "template/partial_availability.txt",
                "content": f"{template_id}: action '{stable_action_id}' unavailable, skipped.",
            },
        }
    return {}


def render_plan(template_id: str, overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    tpl = _template_or_empty(template_id)
    if not tpl:
        raise ValueError("template_not_found")

    over = dict(overrides or {})
    available = _available_actions()
    spec = render_spec(template_id, over)
    alias_table = dict(spec.get("template_aliases") or {})
    fallback_action = str(spec.get("template_fallback_action") or "")

    steps_src = list(tpl.get("default_plan") or [])
    if _as_bool(over.get("enable_oracle", False)) and isinstance(tpl.get("plan_when_oracle_enabled"), list):
        steps_src = list(tpl.get("plan_when_oracle_enabled") or [])

    values = {
        "name": str(spec.get("name") or ""),
        "goal": str(spec.get("goal") or ""),
        "owner": str(spec.get("owner") or ""),
        "template_id": str(tpl.get("id") or ""),
        "window_id": str(over.get("window_id") or ""),
    }

    steps: List[Dict[str, Any]] = []
    written_files: Dict[str, str] = {}

    for row in steps_src:
        src = dict(row or {})
        stable_action = str(src.get("action_id") or src.get("action") or "").strip()
        if not stable_action:
            continue

        actual_action = str(alias_table.get(stable_action) or _resolve_alias(stable_action, available)).strip()
        if not actual_action:
            fb = _fallback_step(
                template_id=str(tpl.get("id") or ""),
                stable_action_id=stable_action,
                fallback_action=fallback_action,
            )
            if fb:
                steps.append(fb)
            continue

        args = _render_value(dict(src.get("args") or {}), values)
        budgets = {}
        if src.get("budgets"):
            budgets = _normalize_budgets(src.get("budgets"))

        if actual_action == "files.sandbox_write":
            rel = str(args.get("relpath") or "").strip()
            content = str(args.get("content") or "")
            if rel:
                written_files[rel] = content
        if actual_action == "files.sha256_verify":
            rel = str(args.get("relpath") or "").strip()
            exp = str(args.get("expected_sha256") or "").strip()
            if exp in {"__AUTO_FROM_WRITE__", "__AUTO_SHA256__"} and rel in written_files:
                args["expected_sha256"] = hashlib.sha256(_text_bytes_for_write(written_files[rel])).hexdigest()

        step = {"action_id": actual_action, "args": dict(args)}
        if budgets:
            step["budgets"] = budgets
        steps.append(step)

    if not steps:
        fb = _fallback_step(
            template_id=str(tpl.get("id") or ""),
            stable_action_id="no_steps_available",
            fallback_action=fallback_action,
        )
        if fb:
            steps.append(fb)

    return {"steps": steps}


def _readme_text(
    *,
    template_id: str,
    template_title: str,
    spec: Dict[str, Any],
    missing_actions: List[str],
    plan_path: Path,
) -> str:
    allowed_actions = [str(x) for x in list(spec.get("allowed_actions") or []) if str(x).strip()]
    budgets = dict(spec.get("budgets") or {})
    lines: List[str] = []
    lines.append(f"template_id: {template_id}")
    lines.append(f"title: {template_title}")
    lines.append(f"name: {spec.get('name')}")
    lines.append(f"owner: {spec.get('owner')}")
    lines.append(f"goal: {spec.get('goal')}")
    lines.append("allowed_actions:")
    for action in allowed_actions:
        lines.append(f"- {action}")
    if not allowed_actions:
        lines.append("- <none>")
    lines.append("budgets:")
    lines.append(json.dumps(budgets, ensure_ascii=False, indent=2))
    if missing_actions:
        lines.append("missing_template_actions:")
        for action in missing_actions:
            lines.append(f"- {action}")
    lines.append(f"plan_path: {plan_path}")
    lines.append("run_once_hint: python -B tools/agent_run_once.py --agent-id <agent_id>")
    return "\n".join(lines) + "\n"


def create_agent_from_template(
    template_id: str,
    overrides: Dict[str, Any] | None = None,
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    tpl = _template_or_empty(template_id)
    if not tpl:
        return {"ok": False, "error": "template_not_found", "template_id": str(template_id or "")}

    over = dict(overrides or {})
    over["enable_oracle"] = _as_bool(over.get("enable_oracle", False))
    over["enable_comm"] = _as_bool(over.get("enable_comm", False))

    try:
        spec = render_spec(str(tpl.get("id") or ""), over)
        plan = render_plan(str(tpl.get("id") or ""), over)
    except Exception as exc:
        return {
            "ok": False,
            "error": "render_failed",
            "detail": str(exc),
            "template_id": str(tpl.get("id") or ""),
        }

    if bool(dry_run):
        all_steps = list(plan.get("steps") or [])
        preview_steps = [dict(x or {}) for x in all_steps[:3]]
        preview_json = json.dumps({"steps": preview_steps}, ensure_ascii=False)
        if len(preview_json) > 1200:
            preview_json = preview_json[:1200] + "...(truncated)"
        return {
            "ok": True,
            "template_id": str(tpl.get("id") or ""),
            "dry_run": True,
            "created": False,
            "spec_summary": {
                "name": str(spec.get("name") or ""),
                "owner": str(spec.get("owner") or ""),
                "goal": str(spec.get("goal") or ""),
                "allowed_actions": list(spec.get("allowed_actions") or []),
                "budgets": dict(spec.get("budgets") or {}),
                "oracle_policy": dict(spec.get("oracle_policy") or {}),
                "comm_policy": dict(spec.get("comm_policy") or {}),
                "capabilities_effective": list(spec.get("capabilities_effective") or []),
            },
            "plan_preview": {
                "steps_total": len(all_steps),
                "steps_preview": preview_steps,
                "json_preview": preview_json,
            },
            "allowed_actions": list(spec.get("allowed_actions") or []),
            "template_missing_actions": list(spec.get("template_missing_actions") or []),
            "template_disabled_by_policy": list(spec.get("template_disabled_by_policy") or []),
        }

    from modules.garage import agent_factory

    create_rep = agent_factory.create_agent(spec)
    if not bool(create_rep.get("ok")):
        return {
            "ok": False,
            "error": "create_failed",
            "template_id": str(tpl.get("id") or ""),
            "create": create_rep,
        }

    agent_id = str(create_rep.get("agent_id") or "")
    folder = Path(str(create_rep.get("folder") or "")).resolve()
    plan_path = (folder / "plan.json").resolve()
    readme_path = (folder / "README_agent.txt").resolve()

    try:
        folder.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        readme_path.write_text(
            _readme_text(
                template_id=str(tpl.get("id") or ""),
                template_title=str(tpl.get("title") or ""),
                spec=spec,
                missing_actions=[str(x) for x in list(spec.get("template_missing_actions") or [])],
                plan_path=plan_path,
            ),
            encoding="utf-8",
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": "artifact_write_failed",
            "detail": str(exc),
            "template_id": str(tpl.get("id") or ""),
            "agent_id": agent_id,
            "path": str(folder),
        }

    return {
        "ok": True,
        "created": True,
        "agent_id": agent_id,
        "path": str(folder),
        "template_id": str(tpl.get("id") or ""),
        "plan_path": str(plan_path),
        "readme_path": str(readme_path),
        "dry_run": bool(dry_run),
        "allowed_actions": list(spec.get("allowed_actions") or []),
        "missing_actions": list(spec.get("template_missing_actions") or []),
        "disabled_by_policy": list(spec.get("template_disabled_by_policy") or []),
        "spec": spec,
        "plan": plan,
    }


__all__ = [
    "CAPABILITY_ACTIONS",
    "STABLE_ACTION_ALIASES",
    "capability_policy_filter",
    "resolve_allowed_actions",
    "list_templates",
    "get_template",
    "render_spec",
    "render_plan",
    "create_agent_from_template",
]
