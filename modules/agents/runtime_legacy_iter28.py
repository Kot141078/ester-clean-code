# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from modules.thinking.action_registry import invoke_guarded
from modules.volition.volition_gate import VolitionContext, get_default_gate

_LOCK = threading.RLock()
_ERR_STREAK = 0
_DISABLED_IN_PROCESS = False


def _now_iso(ts: Optional[float] = None) -> str:
    value = float(ts if ts is not None else time.time())
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def _persist_dir() -> Path:
    root = (os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _agents_dir() -> Path:
    p = (_persist_dir() / "agents").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _agents_events_path() -> Path:
    p = (_agents_dir() / "agents.jsonl").resolve()
    if not p.exists():
        p.touch()
    return p


def _runs_path() -> Path:
    p = (_agents_dir() / "runs.jsonl").resolve()
    if not p.exists():
        p.touch()
    return p


def _state_path() -> Path:
    p = (_agents_dir() / "state.json").resolve()
    if not p.exists():
        payload = {
            "agents": {},
            "last_run": None,
            "last_ok": None,
            "last_error": "",
            "last_action_kind": "",
            "runs_total": 0,
        }
        try:
            p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
    return p


def _slot() -> str:
    v = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if v == "B" else "A"


def _enabled() -> bool:
    if _DISABLED_IN_PROCESS:
        return False
    if _slot() != "B":
        return False
    return _truthy(os.getenv("ESTER_AGENTS_RUNTIME_ENABLED", "1"))


def _fail_max() -> int:
    try:
        return max(1, int(os.getenv("ESTER_AGENTS_FAIL_MAX", "3") or "3"))
    except Exception:
        return 3


def _load_state() -> Dict[str, Any]:
    p = _state_path()
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
    if not isinstance(raw["agents"], dict):
        raw["agents"] = {}
    raw.setdefault("last_run", None)
    raw.setdefault("last_ok", None)
    raw.setdefault("last_error", "")
    raw.setdefault("last_action_kind", "")
    raw.setdefault("runs_total", 0)
    return raw


def _save_state(state: Dict[str, Any]) -> None:
    p = _state_path()
    payload = json.dumps(dict(state or {}), ensure_ascii=False, indent=2)
    tmp = p.with_suffix(".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(p)
        return
    except Exception:
        pass
    try:
        with p.open("w", encoding="utf-8") as f:
            f.write(payload)
    except Exception:
        return


def _append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    line = json.dumps(dict(obj or {}), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def _note_error(err: str) -> None:
    global _ERR_STREAK, _DISABLED_IN_PROCESS
    with _LOCK:
        _ERR_STREAK += 1
        if _ERR_STREAK >= _fail_max():
            _DISABLED_IN_PROCESS = True
        st = _load_state()
        st["last_ok"] = False
        st["last_error"] = str(err or "")
        _save_state(st)


def _clear_error() -> None:
    global _ERR_STREAK
    with _LOCK:
        _ERR_STREAK = 0


def list_agents() -> Dict[str, Any]:
    with _LOCK:
        st = _load_state()
        agents = [dict(v) for _, v in sorted((st.get("agents") or {}).items())]
    return {
        "ok": True,
        "enabled": _enabled(),
        "disabled_in_process": bool(_DISABLED_IN_PROCESS),
        "total": len(agents),
        "agents": agents,
        "last_run": st.get("last_run"),
        "last_ok": st.get("last_ok"),
        "last_error": st.get("last_error"),
        "last_action_kind": st.get("last_action_kind"),
        "runs_total": int(st.get("runs_total") or 0),
        "paths": {
            "agents_events": str(_agents_events_path()),
            "runs": str(_runs_path()),
            "state": str(_state_path()),
        },
    }


def status() -> Dict[str, Any]:
    rep = list_agents()
    return {
        "ok": rep.get("ok", True),
        "enabled": rep.get("enabled", False),
        "total": rep.get("total", 0),
        "last_run": rep.get("last_run"),
        "last_ok": rep.get("last_ok"),
        "last_error": rep.get("last_error"),
        "last_action_kind": rep.get("last_action_kind"),
        "disabled_in_process": rep.get("disabled_in_process", False),
        "runs_total": rep.get("runs_total", 0),
    }


def spawn_agent(kind: str, name: str, meta: Optional[Dict[str, Any]] = None) -> str:
    agent_id = "agent_" + uuid.uuid4().hex[:12]
    row = {
        "id": agent_id,
        "kind": str(kind or "procedural"),
        "name": str(name or "agent"),
        "meta": dict(meta or {}),
        "created_ts": int(time.time()),
        "created_at": _now_iso(),
        "status": "ready",
    }
    with _LOCK:
        st = _load_state()
        agents = dict(st.get("agents") or {})
        agents[agent_id] = row
        st["agents"] = agents
        _save_state(st)
        _append_jsonl(
            _agents_events_path(),
            {"ts": int(time.time()), "event": "spawn", "agent": row},
        )
    return agent_id


def _resolve_agent(agent_id: str) -> Optional[Dict[str, Any]]:
    st = _load_state()
    agents = dict(st.get("agents") or {})
    row = agents.get(str(agent_id))
    if isinstance(row, dict):
        return row
    return None


def _task_to_action(task: Dict[str, Any]) -> Tuple[str, Dict[str, Any], List[str]]:
    t = dict(task or {})
    action = str(t.get("action") or "").strip()
    args = dict(t.get("args") or {})
    needs = [str(x) for x in list(t.get("needs") or [])]
    if action:
        return action, args, needs

    text = str(t.get("text") or t.get("intent") or "").strip()
    if not text:
        text = "agent procedural note"
    fallback_args = {
        "text": text,
        "tags": ["agent", "procedural"],
        "source": "agents.runtime",
        "meta": {"task": t},
    }
    return "memory.add_note", fallback_args, []


def run_agent_once(agent_id: str, task: Dict[str, Any], budgets: Dict[str, Any], gate: Any = None) -> Dict[str, Any]:
    start = time.time()
    aid = str(agent_id or "").strip()
    if not aid:
        return {"ok": False, "error": "agent_id_required"}
    if not _enabled():
        return {"ok": False, "error": "agents_runtime_disabled", "slot": _slot()}

    agent = _resolve_agent(aid)
    if agent is None:
        return {"ok": False, "error": "agent_not_found", "agent_id": aid}

    if gate is None:
        gate = get_default_gate()

    chain_id = str(task.get("chain_id") or ("chain_" + uuid.uuid4().hex[:10]))
    action_name, action_args, needs = _task_to_action(task)
    intent = str(task.get("intent") or f"run:{action_name}")

    try:
        rep = invoke_guarded(
            action_name,
            action_args,
            ctx=VolitionContext(
                chain_id=chain_id,
                step="action",
                actor=f"agent:{aid}",
                intent=intent,
                action_kind=action_name,
                needs=needs,
                budgets=dict(budgets or {}),
                metadata={"agent_id": aid, "agent_kind": agent.get("kind"), "task": dict(task or {})},
            ),
            gate=gate,
        )
        ok = bool((rep or {}).get("ok"))
        _clear_error()
        with _LOCK:
            st = _load_state()
            st["last_run"] = _now_iso()
            st["last_ok"] = ok
            st["last_error"] = str((rep or {}).get("error") or "")
            st["last_action_kind"] = action_name
            st["runs_total"] = int(st.get("runs_total") or 0) + 1
            _save_state(st)
            _append_jsonl(
                _runs_path(),
                {
                    "ts": int(time.time()),
                    "run_at": _now_iso(),
                    "agent_id": aid,
                    "chain_id": chain_id,
                    "task": dict(task or {}),
                    "action_kind": action_name,
                    "ok": ok,
                    "result": dict(rep or {}),
                    "duration_ms": max(0, int((time.time() - start) * 1000)),
                },
            )
        return {
            "ok": ok,
            "agent_id": aid,
            "chain_id": chain_id,
            "action_kind": action_name,
            "result": rep,
        }
    except Exception as exc:
        err = f"{exc.__class__.__name__}: {exc}"
        _note_error(err)
        with _LOCK:
            _append_jsonl(
                _runs_path(),
                {
                    "ts": int(time.time()),
                    "run_at": _now_iso(),
                    "agent_id": aid,
                    "chain_id": chain_id,
                    "task": dict(task or {}),
                    "ok": False,
                    "error": err,
                    "duration_ms": max(0, int((time.time() - start) * 1000)),
                },
            )
        return {"ok": False, "agent_id": aid, "chain_id": chain_id, "error": "agent_runtime_error", "detail": err}


__all__ = [
    "list_agents",
    "status",
    "spawn_agent",
    "run_agent_once",
]
