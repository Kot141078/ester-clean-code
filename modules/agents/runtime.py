
# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from modules.thinking import action_registry
from modules.volition import journal as volition_journal
from modules.volition.volition_gate import VolitionContext, get_default_gate

try:
    from modules.garage.templates import (  # type: ignore
        create_agent_from_template as _garage_create_agent_from_template,
        get_template as _garage_get_template,
    )
except Exception:  # pragma: no cover
    _garage_create_agent_from_template = None  # type: ignore
    _garage_get_template = None  # type: ignore

_LOCK = threading.RLock()
_BOOL_TRUE = {"1", "true", "yes", "on", "y"}
_LOG = logging.getLogger(__name__)
_LEGACY_CREATE_WARNED = False

_TEMPLATE_TO_GARAGE: Dict[str, str] = {
    "archivist": "archivist.v1",
    "builder": "builder.v1",
    "reviewer": "reviewer.v1",
}

_TEMPLATE_FALLBACKS: Dict[str, Dict[str, Any]] = {
    "archivist": {
        "allowed_actions": ["fs.list", "fs.read", "memory.add_note", "messages.outbox.enqueue"],
        "budgets": {"max_steps": 6, "max_ms": 3000, "window_sec": 60, "est_ms": 250},
    },
    "builder": {
        "allowed_actions": [
            "fs.list",
            "fs.read",
            "fs.write",
            "fs.patch",
            "scaffold.module",
            "memory.add_note",
            "messages.outbox.enqueue",
        ],
        "budgets": {"max_steps": 8, "max_ms": 4000, "window_sec": 60, "est_ms": 300},
    },
    "reviewer": {
        "allowed_actions": [
            "run_checks_offline",
            "route_registry_check",
            "route_return_lint",
            "deps.report",
            "stubs.report",
            "messages.outbox.enqueue",
            "memory.add_note",
        ],
        "budgets": {"max_steps": 8, "max_ms": 4500, "window_sec": 60, "est_ms": 350},
    },
    "procedural": {
        "allowed_actions": ["memory.add_note", "messages.outbox.enqueue", "fs.list", "fs.read", "fs.write"],
        "budgets": {"max_steps": 4, "max_ms": 2000, "window_sec": 60, "est_ms": 250},
    },
}

_ACTION_ALIASES: Dict[str, List[str]] = {
    "fs.list": ["fs.list", "files.list"],
    "fs.read": ["fs.read", "files.read"],
    "fs.write": ["fs.write", "files.write", "files.sandbox_write"],
    "fs.patch": ["fs.patch", "files.patch", "files.sandbox_write"],
    "fs.hash": ["fs.hash", "files.hash", "files.sha256_verify"],
    "run_checks_offline": ["run_checks_offline", "tools.run_checks_offline", "checks.run_offline"],
    "route_registry_check": ["route_registry_check", "tools.route_registry_check", "checks.route_registry_check"],
    "route_return_lint": ["route_return_lint", "tools.route_return_lint", "checks.route_return_lint"],
    "deps.report": ["deps.report", "deps_report", "tools.deps_report"],
    "stubs.report": ["stubs.report", "stubs_kill_list", "tools.stubs_kill_list"],
    "scaffold.module": ["scaffold.module", "module.scaffold"],
    "memory.add_note": ["memory.add_note"],
    "initiative.mark_done": ["initiative.mark_done"],
    "proactivity.queue.add": ["proactivity.queue.add"],
    "messages.outbox.enqueue": ["messages.outbox.enqueue"],
    "messages.telegram.send": ["messages.telegram.send"],
    "oracle.openai.call": ["oracle.openai.call", "llm.remote.call"],
}

_LOCAL_ACTIONS = {
    "fs.list",
    "fs.read",
    "fs.write",
    "fs.patch",
    "fs.hash",
    "run_checks_offline",
    "route_registry_check",
    "route_return_lint",
    "deps.report",
    "stubs.report",
    "scaffold.module",
}

_ALIAS_TO_CANONICAL: Dict[str, str] = {}
for _canonical, _aliases in _ACTION_ALIASES.items():
    for _alias in [_canonical, *_aliases]:
        _key = str(_alias or "").strip().lower()
        if _key:
            _ALIAS_TO_CANONICAL[_key] = _canonical


@dataclass
class AgentContext:
    ester_core: str
    volition_gate: Any
    action_runner: "ActionRunner"
    budgets: Dict[str, Any]
    io_roots: Dict[str, List[str]]
    journal_sink: Callable[[Dict[str, Any]], Dict[str, Any]]


def _now_iso(ts: Optional[float] = None) -> str:
    value = float(ts if ts is not None else time.time())
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in _BOOL_TRUE


def _repo_root() -> Path:
    return Path.cwd().resolve()


def _persist_dir() -> Path:
    root = (os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((_repo_root() / "data").resolve())
    out = Path(root).resolve()
    out.mkdir(parents=True, exist_ok=True)
    return out


def _agents_root() -> Path:
    out = (_persist_dir() / "agents").resolve()
    out.mkdir(parents=True, exist_ok=True)
    return out


def _plans_root() -> Path:
    out = (_persist_dir() / "plans").resolve()
    out.mkdir(parents=True, exist_ok=True)
    return out


def _compat_events_path() -> Path:
    p = (_agents_root() / "agents.jsonl").resolve()
    if not p.exists():
        p.touch()
    return p


def _compat_runs_path() -> Path:
    p = (_agents_root() / "runs.jsonl").resolve()
    if not p.exists():
        p.touch()
    return p


def _compat_state_path() -> Path:
    p = (_agents_root() / "state.json").resolve()
    if not p.exists():
        payload = {
            "agents": {},
            "last_run": None,
            "last_ok": None,
            "last_error": "",
            "last_action_kind": "",
            "runs_total": 0,
        }
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def _load_compat_state() -> Dict[str, Any]:
    p = _compat_state_path()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("bad_state")
    except Exception:
        raw = {
            "agents": {},
            "last_run": None,
            "last_ok": None,
            "last_error": "",
            "last_action_kind": "",
            "runs_total": 0,
        }
    raw.setdefault("agents", {})
    raw.setdefault("last_run", None)
    raw.setdefault("last_ok", None)
    raw.setdefault("last_error", "")
    raw.setdefault("last_action_kind", "")
    raw.setdefault("runs_total", 0)
    return raw


def _save_compat_state(state: Dict[str, Any]) -> None:
    p = _compat_state_path()
    payload = json.dumps(dict(state or {}), ensure_ascii=False, indent=2)
    tmp = p.with_suffix(".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(p)
        return
    except Exception:
        pass
    p.write_text(payload, encoding="utf-8")


def _agent_root(agent_id: str) -> Path:
    out = (_agents_root() / str(agent_id)).resolve()
    out.mkdir(parents=True, exist_ok=True)
    return out


def _agent_json_path(agent_id: str) -> Path:
    return (_agent_root(agent_id) / "agent.json").resolve()


def _runs_jsonl_path(agent_id: str) -> Path:
    p = (_agent_root(agent_id) / "runs.jsonl").resolve()
    if not p.exists():
        p.touch()
    return p


def _artifacts_dir(agent_id: str) -> Path:
    out = (_agent_root(agent_id) / "artifacts").resolve()
    out.mkdir(parents=True, exist_ok=True)
    return out


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    line = json.dumps(dict(row or {}), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def _read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except Exception:
        pass
    return dict(default)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    text = json.dumps(dict(payload or {}), ensure_ascii=False, indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
        return
    except Exception:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

def _canonical_template_name(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if raw in _TEMPLATE_FALLBACKS:
        return raw
    if raw.endswith(".v1"):
        raw = raw[:-3]
    if raw in _TEMPLATE_FALLBACKS:
        return raw
    return raw


def _warn_legacy_create_once() -> None:
    global _LEGACY_CREATE_WARNED
    if _LEGACY_CREATE_WARNED:
        return
    with _LOCK:
        if _LEGACY_CREATE_WARNED:
            return
        _LOG.warning("LEGACY agents.runtime used; routed to Garage templates (canonical).")
        _LEGACY_CREATE_WARNED = True


def _resolve_template_pair(value: Any) -> Tuple[str, str]:
    raw = str(value or "").strip().lower()
    if not raw:
        return "", ""
    if raw in _TEMPLATE_TO_GARAGE:
        return raw, str(_TEMPLATE_TO_GARAGE.get(raw) or "")
    reverse = {str(v): str(k) for k, v in _TEMPLATE_TO_GARAGE.items()}
    if raw in reverse:
        return reverse[raw], raw
    canonical = _canonical_template_name(raw)
    if canonical in _TEMPLATE_TO_GARAGE:
        return canonical, str(_TEMPLATE_TO_GARAGE.get(canonical) or "")
    if canonical == "procedural":
        return "procedural", str(_TEMPLATE_TO_GARAGE.get("builder") or "builder.v1")
    return canonical, ""


def _runtime_budgets_to_garage(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    src = _normalize_budgets(raw)
    return {
        "max_steps": int(src.get("max_steps") or 1),
        "max_work_ms": int(src.get("max_ms") or 1),
        "window_sec": int(src.get("window_sec") or 1),
        "est_work_ms": int(src.get("est_ms") or 1),
    }


def _garage_overrides_from_legacy(overrides: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in ("name", "goal", "owner", "window_id"):
        val = str(overrides.get(key) or "").strip()
        if val:
            out[key] = val
    if "enable_oracle" in overrides:
        out["enable_oracle"] = _truthy(overrides.get("enable_oracle"))
    if "enable_comm" in overrides:
        out["enable_comm"] = _truthy(overrides.get("enable_comm"))
    if str(out.get("window_id") or "").strip() == "":
        maybe_window = str((dict(overrides.get("budgets") or {})).get("oracle_window") or "").strip()
        if maybe_window:
            out["window_id"] = maybe_window
    caps = list(overrides.get("capabilities") or [])
    if caps:
        out["capabilities"] = [str(x) for x in caps if str(x).strip()]
    budgets = _runtime_budgets_to_garage(overrides.get("budgets"))
    if budgets:
        out["budgets"] = budgets
    return out


def _canonical_action(value: Any) -> str:
    key = str(value or "").strip()
    if not key:
        return ""
    out = _ALIAS_TO_CANONICAL.get(key.lower())
    if out:
        return out
    return key


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _clip_text(text: str, max_chars: int = 1200) -> str:
    value = str(text or "")
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + " ...<truncated>"


def _normalize_budgets(raw: Any, base: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    seed = dict(base or {})
    src = dict(raw or {})
    max_steps = int(src.get("max_steps") or src.get("max_actions") or seed.get("max_steps") or 6)
    max_ms = int(src.get("max_ms") or src.get("max_work_ms") or seed.get("max_ms") or 2500)
    window_sec = int(src.get("window_sec") or src.get("window") or seed.get("window_sec") or 60)
    est_ms = int(src.get("est_ms") or src.get("est_work_ms") or seed.get("est_ms") or min(max_ms, 250))
    oracle_window = str(src.get("oracle_window") or src.get("window_id") or seed.get("oracle_window") or "").strip()
    max_steps = max(1, max_steps)
    max_ms = max(1, max_ms)
    window_sec = max(1, window_sec)
    est_ms = max(1, min(max_ms, est_ms))
    return {
        "max_steps": int(max_steps),
        "max_ms": int(max_ms),
        "window_sec": int(window_sec),
        "est_ms": int(est_ms),
        "oracle_window": oracle_window,
    }


def _normalize_io_roots(
    raw: Any,
    *,
    template: str,
    repo_root: Path,
    artifact_root: Path,
) -> Dict[str, List[str]]:
    src = dict(raw or {})
    read_roots = list(src.get("read") or src.get("read_roots") or [])
    write_roots = list(src.get("write") or src.get("write_roots") or [])

    if not read_roots:
        read_roots = [str(repo_root)]
    if not write_roots:
        write_roots = [str(artifact_root)]
        if template in {"builder", "procedural"}:
            write_roots.append(str(repo_root))

    def _clean(items: List[str]) -> List[str]:
        out: List[str] = []
        for item in items:
            p = Path(str(item or "").strip())
            if not str(p):
                continue
            if not p.is_absolute():
                p = (repo_root / p).resolve()
            else:
                p = p.resolve()
            s = str(p)
            if s not in out:
                out.append(s)
        return out

    return {
        "read": _clean(read_roots),
        "write": _clean(write_roots),
    }


def _dedupe(items: List[str]) -> List[str]:
    out: List[str] = []
    for item in items:
        s = str(item or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def _template_spec(template: str) -> Dict[str, Any]:
    name = _canonical_template_name(template)
    if not name:
        return {}
    base = dict(_TEMPLATE_FALLBACKS.get(name) or {})
    if not base:
        return {}

    spec = {
        "template": name,
        "template_source": str(_TEMPLATE_TO_GARAGE.get(name) or ""),
        "allowed_actions": _dedupe([_canonical_action(x) for x in list(base.get("allowed_actions") or []) if _canonical_action(x)]),
        "budgets": _normalize_budgets(base.get("budgets")),
    }

    garage_id = _TEMPLATE_TO_GARAGE.get(name)
    if _garage_get_template and garage_id:
        try:
            tpl = _garage_get_template(garage_id) or {}
            actions_raw = list(tpl.get("default_allowed_actions") or tpl.get("available_actions") or [])
            mapped = [_canonical_action(x) for x in actions_raw if _canonical_action(x)]
            if mapped:
                spec["allowed_actions"] = _dedupe(mapped + list(spec["allowed_actions"]))
            gb = tpl.get("default_budgets")
            if isinstance(gb, dict):
                spec["budgets"] = _normalize_budgets(
                    {
                        "max_steps": gb.get("max_steps"),
                        "max_work_ms": gb.get("max_work_ms"),
                        "window_sec": gb.get("window_sec"),
                        "est_work_ms": gb.get("est_work_ms"),
                    },
                    base=spec["budgets"],
                )
        except Exception:
            pass
    return spec


def _registered_actions() -> Dict[str, Dict[str, Any]]:
    try:
        return dict(action_registry.list_registered() or {})
    except Exception:
        return {}


def _resolve_registry_action(canonical_action_id: str) -> str:
    canonical = _canonical_action(canonical_action_id)
    if canonical in _LOCAL_ACTIONS:
        return canonical
    reg = _registered_actions()
    for candidate in _ACTION_ALIASES.get(canonical, [canonical]):
        if candidate in reg:
            return candidate
    if canonical in reg:
        return canonical
    return canonical


def _contains_path(path: Path, roots: List[str]) -> bool:
    p = path.resolve()
    for root in roots:
        r = Path(str(root)).resolve()
        if p == r or r in p.parents:
            return True
    return False


class ActionRunner:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()

    def _resolve_target(self, raw: Any) -> Path:
        text = str(raw or "").strip()
        if not text:
            return self.repo_root
        p = Path(text)
        if not p.is_absolute():
            p = (self.repo_root / p).resolve()
        else:
            p = p.resolve()
        return p

    def _run_command(self, cmd: List[str], timeout_sec: int = 180) -> Dict[str, Any]:
        try:
            cp = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=max(10, int(timeout_sec)),
                shell=False,
            )
            return {
                "ok": cp.returncode == 0,
                "rc": int(cp.returncode),
                "stdout_tail": _clip_text(cp.stdout, 3000),
                "stderr_tail": _clip_text(cp.stderr, 3000),
            }
        except Exception as exc:
            return {
                "ok": False,
                "error": "command_failed",
                "detail": f"{exc.__class__.__name__}: {exc}",
            }

    def _fs_list(self, args: Dict[str, Any], io_roots: Dict[str, List[str]]) -> Dict[str, Any]:
        target = self._resolve_target(args.get("path") or ".")
        if not _contains_path(target, list(io_roots.get("read") or [])):
            return {"ok": False, "error": "read_root_violation", "path": str(target)}
        if not target.exists() or not target.is_dir():
            return {"ok": False, "error": "path_not_directory", "path": str(target)}
        limit = max(1, min(200, int(args.get("limit") or 50)))
        items: List[Dict[str, Any]] = []
        for child in sorted(target.iterdir(), key=lambda p: p.name.lower())[:limit]:
            kind = "dir" if child.is_dir() else "file"
            size = child.stat().st_size if child.is_file() else 0
            items.append({"name": child.name, "kind": kind, "size": int(size), "path": str(child)})
        return {"ok": True, "path": str(target), "count": len(items), "items": items}

    def _fs_read(self, args: Dict[str, Any], io_roots: Dict[str, List[str]]) -> Dict[str, Any]:
        target = self._resolve_target(args.get("path") or args.get("file") or "")
        if not str(args.get("path") or args.get("file") or "").strip():
            return {"ok": False, "error": "path_required"}
        if not _contains_path(target, list(io_roots.get("read") or [])):
            return {"ok": False, "error": "read_root_violation", "path": str(target)}
        if not target.exists() or not target.is_file():
            return {"ok": False, "error": "file_not_found", "path": str(target)}
        max_bytes = max(1, min(1_000_000, int(args.get("max_bytes") or 16384)))
        raw = target.read_bytes()
        chunk = raw[:max_bytes]
        text = chunk.decode("utf-8", errors="replace")
        return {
            "ok": True,
            "path": str(target),
            "size": len(raw),
            "returned_bytes": len(chunk),
            "truncated": len(raw) > len(chunk),
            "text": text,
        }

    def _fs_write_like(
        self,
        args: Dict[str, Any],
        io_roots: Dict[str, List[str]],
        *,
        append: bool,
    ) -> Dict[str, Any]:
        target_arg = args.get("path") or args.get("relpath") or ""
        if not str(target_arg).strip():
            return {"ok": False, "error": "path_required"}
        target = self._resolve_target(target_arg)
        if not _contains_path(target, list(io_roots.get("write") or [])):
            return {"ok": False, "error": "write_root_violation", "path": str(target)}

        dry_run = _truthy(args.get("dry_run"))
        content = str(args.get("content") or "")
        if append:
            content = str(args.get("append") or content)

        if dry_run:
            would_bytes = len(content.encode("utf-8"))
            return {"ok": True, "dry_run": True, "path": str(target), "would_write_bytes": would_bytes}

        target.parent.mkdir(parents=True, exist_ok=True)
        if append and target.exists():
            with target.open("a", encoding="utf-8") as f:
                f.write(content)
        else:
            target.write_text(content, encoding="utf-8")

        raw = target.read_bytes()
        return {
            "ok": True,
            "path": str(target),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    def _fs_hash(self, args: Dict[str, Any], io_roots: Dict[str, List[str]]) -> Dict[str, Any]:
        target_arg = args.get("path") or args.get("relpath") or ""
        if not str(target_arg).strip():
            return {"ok": False, "error": "path_required"}
        target = self._resolve_target(target_arg)
        if not _contains_path(target, list(io_roots.get("read") or [])):
            return {"ok": False, "error": "read_root_violation", "path": str(target)}
        if not target.exists() or not target.is_file():
            return {"ok": False, "error": "file_not_found", "path": str(target)}
        raw = target.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        expected = str(args.get("expected_sha256") or "").strip().lower()
        matched = digest == expected if expected else True
        return {
            "ok": bool(matched),
            "path": str(target),
            "sha256": digest,
            "expected_sha256": expected,
            "matched": bool(matched),
            "bytes": len(raw),
        }

    def _scaffold_module(self, args: Dict[str, Any], io_roots: Dict[str, List[str]]) -> Dict[str, Any]:
        module_path = str(args.get("path") or args.get("module") or "modules/generated/agent_artifact.py").strip()
        module_name = Path(module_path).stem
        content = str(args.get("content") or "").strip()
        if not content:
            content = (
                "# -*- coding: utf-8 -*-\n"
                "from __future__ import annotations\n\n"
                f"def describe_{module_name}() -> dict:\n"
                "    return {\"ok\": True, \"module\": \"generated\"}\n"
            )
        return self._fs_write_like({"path": module_path, "content": content, "dry_run": args.get("dry_run")}, io_roots, append=False)

    def execute(self, action_id: str, args: Dict[str, Any], *, io_roots: Dict[str, List[str]]) -> Dict[str, Any]:
        canonical = _canonical_action(action_id)

        if canonical == "fs.list":
            return self._fs_list(args, io_roots)
        if canonical == "fs.read":
            return self._fs_read(args, io_roots)
        if canonical == "fs.write":
            return self._fs_write_like(args, io_roots, append=False)
        if canonical == "fs.patch":
            append = str(args.get("mode") or "").strip().lower() == "append"
            return self._fs_write_like(args, io_roots, append=append)
        if canonical == "fs.hash":
            return self._fs_hash(args, io_roots)
        if canonical == "scaffold.module":
            return self._scaffold_module(args, io_roots)
        if canonical == "run_checks_offline":
            return self._run_command(["powershell", "-File", "tools/run_checks_offline.ps1", "-NoGitGuard", "-Quiet"], timeout_sec=600)
        if canonical == "route_registry_check":
            return self._run_command(["python", "-B", "tools/route_registry_check.py"], timeout_sec=120)
        if canonical == "route_return_lint":
            return self._run_command(["python", "-B", "tools/route_return_lint.py"], timeout_sec=120)
        if canonical == "deps.report":
            return self._run_command(["python", "-B", "tools/deps_report.py"], timeout_sec=180)
        if canonical == "stubs.report":
            return self._run_command(["python", "-B", "tools/stubs_kill_list.py", "--smoke", "1"], timeout_sec=180)

        resolved = _resolve_registry_action(canonical)
        rep = action_registry.invoke(resolved, dict(args or {}))
        if isinstance(rep, dict):
            rep.setdefault("kind", resolved)
            return rep
        return {"ok": True, "result": rep, "kind": resolved}


def _enabled() -> bool:
    return _truthy(os.getenv("ESTER_AGENTS_RUNTIME_ENABLED", "1"))


def list_templates() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for name in ["archivist", "builder", "reviewer"]:
        spec = _template_spec(name)
        rows.append(
            {
                "template": name,
                "template_source": str(spec.get("template_source") or ""),
                "allowed_actions": list(spec.get("allowed_actions") or []),
                "budgets": dict(spec.get("budgets") or {}),
            }
        )
    return rows


def _load_agent(agent_id: str) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not aid:
        return {}
    payload = _read_json(_agent_json_path(aid), default={})
    if not payload:
        return {}
    payload.setdefault("agent_id", aid)
    payload.setdefault("id", aid)
    payload.setdefault("status", "ready")
    payload.setdefault("budgets", {})
    payload.setdefault("io_roots", {})
    payload.setdefault("allowed_actions", [])
    payload.setdefault("name", aid)
    payload.setdefault("kind", payload.get("template") or "procedural")
    payload.setdefault("meta", {})
    return payload


def _save_agent(agent: Dict[str, Any]) -> None:
    aid = str(agent.get("agent_id") or agent.get("id") or "").strip()
    if not aid:
        return
    payload = dict(agent)
    payload["agent_id"] = aid
    payload["id"] = aid
    _write_json(_agent_json_path(aid), payload)


def create_agent(template: str, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    tpl, garage_id = _resolve_template_pair(template)
    if not garage_id:
        return {
            "ok": False,
            "error": "template_not_found",
            "template": str(template or ""),
            "templates": ["archivist", "builder", "reviewer", "procedural"],
        }
    if _garage_create_agent_from_template is None:
        return {
            "ok": False,
            "error": "garage_templates_unavailable",
            "template": str(template or ""),
            "template_source": garage_id,
        }

    over = dict(overrides or {})
    _warn_legacy_create_once()
    garage_overrides = _garage_overrides_from_legacy(over)
    garage_rep = _garage_create_agent_from_template(garage_id, garage_overrides, dry_run=False)
    if not bool(garage_rep.get("ok")):
        return {
            "ok": False,
            "error": "garage_create_failed",
            "template": tpl,
            "template_source": garage_id,
            "garage": garage_rep,
        }

    aid = str(garage_rep.get("agent_id") or "").strip()
    if not aid:
        return {
            "ok": False,
            "error": "garage_missing_agent_id",
            "template": tpl,
            "template_source": garage_id,
            "garage": garage_rep,
        }

    spec = dict(garage_rep.get("spec") or {})
    legacy_spec = _template_spec(tpl if tpl in _TEMPLATE_FALLBACKS else "builder")
    created_at = _now_iso()
    artifact_root = _artifacts_dir(aid)
    repo_root = _repo_root()
    budgets = _normalize_budgets(over.get("budgets"), base=spec.get("budgets") or legacy_spec.get("budgets") or {})
    allowed_actions = _dedupe(
        [_canonical_action(x) for x in list(over.get("allowed_actions") or spec.get("allowed_actions") or []) if _canonical_action(x)]
    )
    io_roots = _normalize_io_roots(over.get("io_roots"), template=tpl or "builder", repo_root=repo_root, artifact_root=artifact_root)

    payload: Dict[str, Any] = {
        "agent_id": aid,
        "id": aid,
        "name": str(over.get("name") or spec.get("name") or f"{tpl or 'builder'}.{aid[-6:]}").strip(),
        "template": str(tpl or "builder"),
        "template_source": garage_id,
        "created_at": created_at,
        "created_ts": int(time.time()),
        "status": "ready",
        "budgets": budgets,
        "allowed_actions": allowed_actions,
        "io_roots": io_roots,
        "kind": str(over.get("kind") or tpl or "builder"),
        "meta": dict(over.get("meta") or {}),
        "last_run": None,
        "last_ok": None,
        "last_error": "",
        "last_action_kind": "",
        "runs_total": 0,
    }

    with _LOCK:
        _runs_jsonl_path(aid)
        _save_agent(payload)
        _append_jsonl(
            _compat_events_path(),
            {
                "ts": int(time.time()),
                "event": "create",
                "agent_id": aid,
                "template": str(tpl or "builder"),
                "template_source": garage_id,
                "name": payload["name"],
            },
        )

        st = _load_compat_state()
        agents = dict(st.get("agents") or {})
        agents[aid] = {
                "id": aid,
                "name": payload["name"],
                "kind": payload["kind"],
                "template": str(tpl or "builder"),
                "status": payload["status"],
                "created_at": payload["created_at"],
            }
        st["agents"] = agents
        _save_compat_state(st)

    return {
        "ok": True,
        "agent_id": aid,
        "path": str(_agent_root(aid)),
        "template": str(tpl or "builder"),
        "template_source": garage_id,
        "garage_path": str(garage_rep.get("path") or ""),
        "agent": payload,
    }


def spawn_agent(kind: str, name: str, meta: Optional[Dict[str, Any]] = None) -> str:
    k = _canonical_template_name(kind)
    if k not in _TEMPLATE_FALLBACKS:
        k = "procedural"
    rep = create_agent(
        k,
        {
            "name": str(name or "agent").strip() or "agent",
            "meta": dict(meta or {}),
            "kind": str(kind or k),
        },
    )
    return str(rep.get("agent_id") or "")


def _last_run_row(agent_id: str) -> Dict[str, Any]:
    path = _runs_jsonl_path(agent_id)
    if not path.exists() or path.stat().st_size <= 0:
        return {}
    last = ""
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        chunk = b""
        while pos > 0:
            step = min(2048, pos)
            pos -= step
            f.seek(pos, os.SEEK_SET)
            chunk = f.read(step) + chunk
            lines = chunk.splitlines()
            if len(lines) >= 1:
                for line in reversed(lines):
                    text = line.decode("utf-8", errors="replace").strip()
                    if text:
                        last = text
                        break
            if last:
                break
    if not last:
        return {}
    try:
        obj = json.loads(last)
        if isinstance(obj, dict):
            return obj
    except Exception:
        return {}
    return {}


def list_agents() -> Dict[str, Any]:
    agents: List[Dict[str, Any]] = []
    last_run = None
    last_ok = None
    last_error = ""
    last_action_kind = ""
    runs_total = 0

    with _LOCK:
        for child in sorted(_agents_root().iterdir(), key=lambda p: p.name.lower()):
            if not child.is_dir():
                continue
            agent = _load_agent(child.name)
            if not agent:
                continue
            row = {
                "id": str(agent.get("agent_id") or child.name),
                "agent_id": str(agent.get("agent_id") or child.name),
                "name": str(agent.get("name") or child.name),
                "kind": str(agent.get("kind") or agent.get("template") or "procedural"),
                "template": str(agent.get("template") or "procedural"),
                "status": str(agent.get("status") or "ready"),
                "created_at": agent.get("created_at"),
                "budgets": dict(agent.get("budgets") or {}),
                "io_roots": dict(agent.get("io_roots") or {}),
                "allowed_actions": list(agent.get("allowed_actions") or []),
                "last_run": agent.get("last_run"),
                "last_ok": agent.get("last_ok"),
                "last_error": str(agent.get("last_error") or ""),
                "last_action_kind": str(agent.get("last_action_kind") or ""),
                "runs_total": int(agent.get("runs_total") or 0),
                "artifacts_count": len([p for p in _artifacts_dir(child.name).iterdir()]),
                "meta": dict(agent.get("meta") or {}),
            }
            if not row["last_run"]:
                last_row = _last_run_row(child.name)
                if last_row:
                    row["last_run"] = last_row.get("run_at") or last_row.get("ts_iso")
                    if "ok" in last_row:
                        row["last_ok"] = bool(last_row.get("ok"))
                    if last_row.get("error"):
                        row["last_error"] = str(last_row.get("error"))
                    if last_row.get("action_id"):
                        row["last_action_kind"] = str(last_row.get("action_id"))
            runs_total += int(row["runs_total"] or 0)
            if row["last_run"] and (last_run is None or str(row["last_run"]) > str(last_run)):
                last_run = row["last_run"]
                last_ok = row.get("last_ok")
                last_error = str(row.get("last_error") or "")
                last_action_kind = str(row.get("last_action_kind") or "")
            agents.append(row)

    return {
        "ok": True,
        "enabled": _enabled(),
        "templates": ["archivist", "builder", "reviewer"],
        "total": len(agents),
        "total_agents": len(agents),
        "agents": agents,
        "last_run": last_run,
        "last_ok": last_ok,
        "last_error": last_error,
        "last_action_kind": last_action_kind,
        "runs_total": runs_total,
        "paths": {
            "root": str(_agents_root()),
            "plans": str(_plans_root()),
            "agents_events": str(_compat_events_path()),
            "runs": str(_compat_runs_path()),
            "state": str(_compat_state_path()),
        },
    }


def status() -> Dict[str, Any]:
    rep = list_agents()
    return {
        "ok": bool(rep.get("ok")),
        "enabled": bool(rep.get("enabled")),
        "templates": list(rep.get("templates") or []),
        "total": int(rep.get("total") or 0),
        "total_agents": int(rep.get("total_agents") or 0),
        "last_run": rep.get("last_run"),
        "last_ok": rep.get("last_ok"),
        "last_error": str(rep.get("last_error") or ""),
        "last_action_kind": str(rep.get("last_action_kind") or ""),
        "runs_total": int(rep.get("runs_total") or 0),
    }

def _load_plan_payload(plan: Any) -> Tuple[bool, Dict[str, Any], str, str]:
    source = ""
    if isinstance(plan, dict):
        payload = dict(plan)
    elif isinstance(plan, list):
        payload = {"steps": list(plan)}
    else:
        raw = str(plan or "").strip()
        if not raw:
            return False, {}, source, "plan_required"
        maybe_path = Path(raw)
        if maybe_path.exists() and maybe_path.is_file():
            source = str(maybe_path.resolve())
            try:
                payload = json.loads(maybe_path.read_text(encoding="utf-8"))
            except Exception:
                return False, {}, source, "plan_json_parse_failed"
        else:
            try:
                payload = json.loads(raw)
            except Exception:
                return False, {}, source, "plan_json_parse_failed"
    if not isinstance(payload, dict):
        return False, {}, source, "plan_not_object"

    rows = list(payload.get("steps") or [])
    steps: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        action_id = str(row.get("action") or row.get("action_id") or "").strip()
        if not action_id:
            continue
        steps.append(
            {
                "action": action_id,
                "args": dict(row.get("args") or {}),
                "why": str(row.get("why") or "").strip(),
            }
        )

    if not steps:
        return False, {}, source, "plan_steps_required"

    out = dict(payload)
    out["steps"] = steps
    return True, out, source, ""


def _needs_for_action(action_id: str) -> List[str]:
    canonical = _canonical_action(action_id)
    if canonical in {"oracle.openai.call"}:
        return ["network", "oracle"]
    return []


def _manual_journal_deny(
    *,
    chain_id: str,
    actor: str,
    intent: str,
    action_id: str,
    reason: str,
    metadata: Dict[str, Any],
) -> None:
    row = {
        "id": "vol_manual_" + uuid.uuid4().hex,
        "ts": int(time.time()),
        "chain_id": chain_id,
        "step": "action",
        "actor": actor,
        "intent": intent,
        "action_kind": action_id,
        "allowed": False,
        "reason_code": "DENY_AGENT_POLICY",
        "reason": str(reason or "agent_policy_deny"),
        "slot": str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A"),
        "metadata": dict(metadata or {}),
        "agent_id": str(metadata.get("agent_id") or ""),
        "plan_id": str(metadata.get("plan_id") or ""),
        "step_index": metadata.get("step_index"),
        "action_id": str(metadata.get("action_id") or action_id),
        "args_digest": str(metadata.get("args_digest") or ""),
        "budgets_snapshot": dict(metadata.get("budgets_snapshot") or {}),
        "decision": "deny",
        "policy_hit": "agent_allowlist",
        "duration_ms": 0,
    }
    volition_journal.append(row)


def run_plan_once(
    agent_id: str,
    plan: Any,
    gate: Any = None,
    *,
    dry: bool = False,
) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not aid:
        return {"ok": False, "error": "agent_id_required"}
    if not _enabled():
        return {"ok": False, "error": "agents_runtime_disabled"}

    if gate is None:
        gate = get_default_gate()

    agent = _load_agent(aid)
    if not agent:
        return {"ok": False, "error": "agent_not_found", "agent_id": aid}

    ok_plan, payload, plan_source, plan_err = _load_plan_payload(plan)
    if not ok_plan:
        return {"ok": False, "error": plan_err, "agent_id": aid}

    finished_ts = int(time.time())
    plan_id = str(payload.get("plan_id") or "").strip()
    if not plan_id and plan_source:
        plan_id = Path(plan_source).stem
    if not plan_id:
        plan_id = "plan_" + uuid.uuid4().hex[:12]

    agent_budgets = _normalize_budgets(agent.get("budgets") or {})
    run_budgets = _normalize_budgets(payload.get("budgets") or {}, base=agent_budgets)
    steps = list(payload.get("steps") or [])
    max_steps = int(run_budgets.get("max_steps") or len(steps) or 1)
    if len(steps) > max_steps:
        steps = steps[:max_steps]

    allowed_actions = [_canonical_action(x) for x in list(agent.get("allowed_actions") or []) if _canonical_action(x)]
    io_roots = _normalize_io_roots(
        agent.get("io_roots") or {},
        template=str(agent.get("template") or "procedural"),
        repo_root=_repo_root(),
        artifact_root=_artifacts_dir(aid),
    )
    ctx = AgentContext(
        ester_core="ester",
        volition_gate=gate,
        action_runner=ActionRunner(_repo_root()),
        budgets=run_budgets,
        io_roots=io_roots,
        journal_sink=volition_journal.append,
    )

    start = time.monotonic()
    step_rows: List[Dict[str, Any]] = []
    all_ok = True
    deny_reason = ""

    for step_index, step in enumerate(steps):
        elapsed_ms = int((time.monotonic() - start) * 1000.0)
        if elapsed_ms >= int(run_budgets.get("max_ms") or 1):
            all_ok = False
            deny_reason = "budget_time_exceeded"
            step_rows.append(
                {
                    "index": step_index,
                    "action_id": "",
                    "ok": False,
                    "error": "budget_time_exceeded",
                }
            )
            break

        requested = _canonical_action(step.get("action"))
        action_exec = _resolve_registry_action(requested)
        args = dict(step.get("args") or {})
        why = str(step.get("why") or f"agent_step:{requested}")
        args_digest = _sha256_json(args)

        budget_snapshot = {
            "time_window": int(run_budgets.get("window_sec") or 0),
            "max_ms": int(run_budgets.get("max_ms") or 0),
            "max_steps": int(run_budgets.get("max_steps") or 0),
            "oracle_window": str(run_budgets.get("oracle_window") or args.get("window_id") or ""),
        }

        metadata = {
            "agent_id": aid,
            "plan_id": plan_id,
            "step_index": int(step_index),
            "action_id": requested,
            "action_exec": action_exec,
            "args_digest": args_digest,
            "budgets_snapshot": budget_snapshot,
            "policy_hit": "volition_gate",
            "why": why,
            "template": str(agent.get("template") or ""),
        }

        if allowed_actions and requested not in allowed_actions:
            _manual_journal_deny(
                chain_id=plan_id,
                actor=f"agent:{aid}",
                intent=why,
                action_id=requested,
                reason="action_not_allowed_by_agent",
                metadata=metadata,
            )
            row = {
                "index": step_index,
                "action_id": requested,
                "action_exec": action_exec,
                "ok": False,
                "error": "action_not_allowed_by_agent",
                "reason": "action_not_allowed_by_agent",
                "args_digest": args_digest,
            }
            _append_jsonl(
                _runs_jsonl_path(aid),
                {
                    "ts": int(time.time()),
                    "run_at": _now_iso(),
                    "event": "step",
                    "plan_id": plan_id,
                    "agent_id": aid,
                    "step_index": step_index,
                    "action_id": requested,
                    "action_exec": action_exec,
                    "ok": False,
                    "error": "action_not_allowed_by_agent",
                    "args_digest": args_digest,
                },
            )
            step_rows.append(row)
            all_ok = False
            deny_reason = "action_not_allowed_by_agent"
            break

        decision = ctx.volition_gate.decide(
            VolitionContext(
                chain_id=plan_id,
                step="action",
                actor=f"agent:{aid}",
                intent=why,
                action_kind=action_exec,
                needs=_needs_for_action(requested),
                budgets={
                    "max_actions": int(run_budgets.get("max_steps") or 1),
                    "max_work_ms": int(run_budgets.get("max_ms") or 1),
                    "window": int(run_budgets.get("window_sec") or 1),
                    "est_work_ms": int(run_budgets.get("est_ms") or 1),
                },
                metadata=metadata,
            )
        )

        if not decision.allowed:
            all_ok = False
            deny_reason = str(decision.reason_code)
            row = {
                "index": step_index,
                "action_id": requested,
                "action_exec": action_exec,
                "ok": False,
                "error": "volition_denied",
                "reason_code": decision.reason_code,
                "reason": decision.reason,
                "args_digest": args_digest,
            }
            _append_jsonl(
                _runs_jsonl_path(aid),
                {
                    "ts": int(time.time()),
                    "run_at": _now_iso(),
                    "event": "step",
                    "plan_id": plan_id,
                    "agent_id": aid,
                    "step_index": step_index,
                    "action_id": requested,
                    "action_exec": action_exec,
                    "ok": False,
                    "error": "volition_denied",
                    "reason_code": decision.reason_code,
                    "reason": decision.reason,
                    "args_digest": args_digest,
                },
            )
            step_rows.append(row)
            break

        step_started = time.monotonic()
        step_dry = bool(dry) or _truthy(args.get("dry_run"))
        if step_dry:
            step_result = {
                "ok": True,
                "dry_run": True,
                "action_id": requested,
                "action_exec": action_exec,
                "args": args,
            }
        else:
            step_result = ctx.action_runner.execute(action_exec, args, io_roots=ctx.io_roots)
            if not isinstance(step_result, dict):
                step_result = {"ok": True, "result": step_result}

        step_ok = bool(step_result.get("ok"))
        duration_ms = max(0, int((time.monotonic() - step_started) * 1000))
        row = {
            "index": step_index,
            "action_id": requested,
            "action_exec": action_exec,
            "ok": step_ok,
            "result": step_result,
            "args_digest": args_digest,
            "duration_ms": duration_ms,
        }
        if not step_ok:
            row["error"] = str(step_result.get("error") or "action_failed")

        _append_jsonl(
            _runs_jsonl_path(aid),
            {
                "ts": int(time.time()),
                "run_at": _now_iso(),
                "event": "step",
                "plan_id": plan_id,
                "agent_id": aid,
                "step_index": step_index,
                "action_id": requested,
                "action_exec": action_exec,
                "ok": step_ok,
                "rc": int(step_result.get("rc") or 0) if isinstance(step_result, dict) else 0,
                "outputs": step_result,
                "error": str(step_result.get("error") or "") if isinstance(step_result, dict) else "",
                "args_digest": args_digest,
                "duration_ms": duration_ms,
            },
        )

        step_rows.append(row)
        if not step_ok:
            all_ok = False
            deny_reason = str(step_result.get("error") or "action_failed")
            break

    finished_ts = int(time.time())
    summary_row = {
        "ts": finished_ts,
        "run_at": _now_iso(),
        "event": "run_summary",
        "plan_id": plan_id,
        "agent_id": aid,
        "ok": all_ok,
        "steps_total": len(steps),
        "steps_done": len(step_rows),
        "reason": deny_reason,
        "duration_ms": max(0, int((time.monotonic() - start) * 1000)),
    }
    _append_jsonl(_runs_jsonl_path(aid), summary_row)
    _append_jsonl(_compat_runs_path(), summary_row)

    with _LOCK:
        agent["last_run"] = _now_iso(float(finished_ts))
        agent["last_ok"] = bool(all_ok)
        agent["last_error"] = "" if all_ok else str(deny_reason or "run_failed")
        agent["last_action_kind"] = str(step_rows[-1].get("action_id") or "") if step_rows else ""
        agent["runs_total"] = int(agent.get("runs_total") or 0) + 1
        agent["status"] = "ready" if all_ok else "error"
        _save_agent(agent)

        st = _load_compat_state()
        st["last_run"] = agent["last_run"]
        st["last_ok"] = bool(all_ok)
        st["last_error"] = str(agent["last_error"])
        st["last_action_kind"] = str(agent["last_action_kind"])
        st["runs_total"] = int(st.get("runs_total") or 0) + 1
        _save_compat_state(st)

    return {
        "ok": bool(all_ok),
        "agent_id": aid,
        "plan_id": plan_id,
        "plan_source": plan_source,
        "steps_total": len(steps),
        "steps_done": len(step_rows),
        "steps": step_rows,
        "reason": deny_reason,
        "journal_path": str(volition_journal.journal_path()),
    }


def run_agent_once(agent_id: str, task: Dict[str, Any], budgets: Dict[str, Any], gate: Any = None) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not aid:
        return {"ok": False, "error": "agent_id_required"}

    payload = dict(task or {})
    action_id = str(payload.get("action") or payload.get("action_id") or "memory.add_note").strip() or "memory.add_note"
    args = dict(payload.get("args") or {})
    intent = str(payload.get("intent") or f"run:{action_id}")
    chain_id = str(payload.get("chain_id") or ("plan_" + uuid.uuid4().hex[:12]))

    plan = {
        "plan_id": chain_id,
        "agent": str(_load_agent(aid).get("template") or "procedural"),
        "budgets": {
            "max_steps": int(dict(budgets or {}).get("max_steps") or dict(budgets or {}).get("max_actions") or 3),
            "max_ms": int(dict(budgets or {}).get("max_ms") or dict(budgets or {}).get("max_work_ms") or 2000),
            "window_sec": int(dict(budgets or {}).get("window_sec") or dict(budgets or {}).get("window") or 60),
            "est_ms": int(dict(budgets or {}).get("est_ms") or dict(budgets or {}).get("est_work_ms") or 250),
            "oracle_window": str(dict(budgets or {}).get("oracle_window") or ""),
        },
        "steps": [
            {
                "action": action_id,
                "args": args,
                "why": intent,
            }
        ],
    }

    rep = run_plan_once(aid, plan, gate=gate, dry=False)
    first = dict((rep.get("steps") or [{}])[0] if rep.get("steps") else {})
    out = {
        "ok": bool(rep.get("ok")),
        "agent_id": aid,
        "chain_id": str(rep.get("plan_id") or chain_id),
        "action_kind": str(first.get("action_id") or _canonical_action(action_id)),
        "result": first.get("result") if isinstance(first.get("result"), dict) else {},
    }
    if not out["ok"]:
        out["error"] = str(first.get("error") or rep.get("reason") or "agent_run_failed")
        out["detail"] = str(first.get("reason") or rep.get("reason") or "")
    return out


def _demo_plan_payload(agent_id: str = "") -> Dict[str, Any]:
    target_agent = str(agent_id or "").strip() or "__AGENT_ID__"
    return {
        "plan_id": "demo_builder_plan",
        "agent": "builder",
        "budgets": {
            "max_steps": 4,
            "max_ms": 2500,
            "window_sec": 60,
            "est_ms": 220,
            "oracle_window": "",
        },
        "steps": [
            {
                "action": "fs.list",
                "args": {"path": "tools", "limit": 10},
                "why": "inspect workspace tools",
            },
            {
                "action": "fs.read",
                "args": {"path": "tools/agent_run_once.py", "max_bytes": 800},
                "why": "inspect run helper",
            },
            {
                "action": "fs.patch",
                "args": {
                    "path": f"data/agents/{target_agent}/artifacts/demo_builder.txt",
                    "content": "demo_builder_patch\\n",
                    "dry_run": True,
                },
                "why": "dry patch artifact path",
            },
        ],
    }


def write_demo_plan(path: str = "", *, agent_id: str = "") -> Dict[str, Any]:
    target = Path(path).resolve() if str(path or "").strip() else (_plans_root() / "demo_builder_plan.json").resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = _demo_plan_payload(agent_id=agent_id)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "plan_path": str(target), "plan": payload}


def ensure_agent(agent_id: str, template: str = "builder") -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    if aid and _agent_json_path(aid).exists():
        return {"ok": True, "agent_id": aid, "existing": True, "agent": _load_agent(aid)}
    return create_agent(template, {"agent_id": aid} if aid else None)


__all__ = [
    "AgentContext",
    "list_templates",
    "create_agent",
    "ensure_agent",
    "list_agents",
    "status",
    "spawn_agent",
    "run_plan_once",
    "run_agent_once",
    "write_demo_plan",
]
