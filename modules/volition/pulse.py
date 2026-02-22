# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

from modules.thinking.action_registry import invoke_guarded
from modules.volition.volition_gate import VolitionContext, get_default_gate

CFG_PATH = os.getenv("VOLITION_CFG", "data/volition/pulse.json")
LOG_PATH = os.getenv("VOLITION_LOG", "data/volition/log.jsonl")
MAX_ACTIONS = int(os.getenv("VOLITION_MAX_ACTIONS", "4") or "4")

_LOCK = threading.RLock()

DEFAULT_CFG: Dict[str, Any] = {
    "version": 1,
    "tasks": [
        {
            "id": "app.discover.1h",
            "enabled": True,
            "ab_slot": "A",
            "kind": "interval",
            "every": "1h",
            "action": "app.discover.scan",
            "args": {},
            "needs": ["proactivity.plan", "agents.run"],
            "cost": 0.005,
            "requires_pill": False,
        },
        {
            "id": "mem.affect.nightly",
            "enabled": True,
            "ab_slot": "A",
            "kind": "cron",
            "at": "30 03 * * *",
            "action": "mem.affect.reprioritize",
            "args": {"top": 100},
            "needs": ["proactivity.plan", "agents.run"],
            "cost": 0.01,
            "requires_pill": False,
        },
    ],
}


def _ensure_parent(path: str) -> None:
    Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)


def _ensure_files() -> None:
    _ensure_parent(CFG_PATH)
    _ensure_parent(LOG_PATH)
    if not Path(CFG_PATH).exists():
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CFG, f, ensure_ascii=False, indent=2)
    if not Path(LOG_PATH).exists():
        Path(LOG_PATH).touch()


def _log(row: Dict[str, Any]) -> None:
    _ensure_files()
    line = json.dumps({"ts": int(time.time()), **dict(row or {})}, ensure_ascii=False)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_cfg() -> Dict[str, Any]:
    _ensure_files()
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            raw.setdefault("tasks", [])
            return raw
    except Exception:
        pass
    return dict(DEFAULT_CFG)


def save_cfg(obj: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_files()
    payload = dict(obj or {})
    payload.setdefault("version", 1)
    payload.setdefault("tasks", [])
    tmp = str(Path(CFG_PATH).with_suffix(".tmp"))
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CFG_PATH)
    return {"ok": True, "path": str(Path(CFG_PATH).resolve())}


def _parse_every(s: str) -> int:
    m = re.match(r"^(\d+)\s*([smhd])$", str(s or "").strip().lower())
    if not m:
        return 0
    n = int(m.group(1))
    u = m.group(2)
    if u == "s":
        return n
    if u == "m":
        return n * 60
    if u == "h":
        return n * 3600
    if u == "d":
        return n * 86400
    return 0


def _cron_due(expr: str, st: time.struct_time) -> bool:
    parts = [p.strip() for p in str(expr or "").split()]
    if len(parts) != 5:
        return False

    def _ok(field: str, value: int) -> bool:
        if field == "*":
            return True
        for part in [x.strip() for x in field.split(",") if x.strip()]:
            if part.isdigit() and int(part) == value:
                return True
        return False

    m, h, dom, mon, dow = parts
    return _ok(m, st.tm_min) and _ok(h, st.tm_hour) and _ok(dom, st.tm_mday) and _ok(mon, st.tm_mon) and _ok(dow, st.tm_wday)


def _ab_ok(task: Dict[str, Any]) -> bool:
    want = str(task.get("ab_slot", "A") or "A").upper()
    cur = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").upper()
    if want == "A":
        return True
    return cur == "B"


def _due(task: Dict[str, Any], now_ts: float) -> bool:
    if not bool(task.get("enabled", False)):
        return False
    if not _ab_ok(task):
        return False
    kind = str(task.get("kind", "interval") or "interval").lower()
    last = float(task.get("_last") or 0.0)
    st = time.localtime(now_ts)
    if kind == "interval":
        sec = _parse_every(str(task.get("every", "0s")))
        return sec > 0 and (now_ts - last) >= sec
    if kind == "cron":
        return (now_ts - last) > 55 and _cron_due(str(task.get("at", "* * * * *")), st)
    if kind == "once":
        return not bool(task.get("_done"))
    return False


def _status_recent(n: int = 10) -> List[Dict[str, Any]]:
    _ensure_files()
    out: List[Dict[str, Any]] = []
    try:
        with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            lines = [line.strip() for line in f if line.strip()][-max(1, int(n)):]
        for line in lines:
            try:
                obj = json.loads(line)
            except Exception:
                obj = {"ok": False, "error": "invalid_log_line", "raw": line}
            if isinstance(obj, dict):
                out.append(obj)
    except Exception:
        pass
    return out


def status() -> Dict[str, Any]:
    cfg = load_cfg()
    return {
        "ok": True,
        "slot": str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").upper(),
        "tasks": len(list(cfg.get("tasks") or [])),
        "recent": _status_recent(10),
        "config_path": str(Path(CFG_PATH).resolve()),
        "log_path": str(Path(LOG_PATH).resolve()),
    }


def tick(pill: str | None = None, dry_run: bool = False) -> Dict[str, Any]:
    with _LOCK:
        cfg = load_cfg()
        tasks = list(cfg.get("tasks") or [])
        now = time.time()
        due = [t for t in tasks if isinstance(t, dict) and _due(t, now)][: max(1, int(MAX_ACTIONS))]
        gate = get_default_gate()

        done: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        for task in due:
            tid = str(task.get("id") or ("task_" + uuid.uuid4().hex[:8]))
            if bool(task.get("requires_pill")) and not str(pill or "").strip():
                skipped.append({"id": tid, "why": "pill_required"})
                _log({"kind": "skip", "id": tid, "why": "pill_required"})
                continue

            chain_id = str(task.get("chain_id") or tid)
            common_budgets = {
                "max_work_ms": int(os.getenv("ESTER_VOLITION_MAX_WORK_MS", "2000") or "2000"),
                "max_actions": int(os.getenv("ESTER_VOLITION_MAX_ACTIONS", "3") or "3"),
                "window": 60,
            }

            d_plan = gate.decide(
                VolitionContext(
                    chain_id=chain_id,
                    step="plan",
                    actor="ester",
                    intent=f"plan:{tid}",
                    needs=["proactivity.plan"],
                    budgets=common_budgets,
                    metadata={"task_id": tid, "source": "volition.pulse"},
                )
            )
            if not d_plan.allowed:
                skipped.append({"id": tid, "why": d_plan.reason_code})
                continue

            d_agent = gate.decide(
                VolitionContext(
                    chain_id=chain_id,
                    step="agent",
                    actor="ester",
                    intent=f"agent:{tid}",
                    needs=["agents.run"],
                    budgets=common_budgets,
                    metadata={"task_id": tid, "source": "volition.pulse"},
                )
            )
            if not d_agent.allowed:
                skipped.append({"id": tid, "why": d_agent.reason_code})
                continue

            action_name = str(task.get("action") or "")
            action_args = dict(task.get("args") or {})
            needs = [str(x) for x in list(task.get("needs") or [])]
            if not action_name:
                skipped.append({"id": tid, "why": "action_missing"})
                continue

            if dry_run:
                rep = {"ok": True, "dry_run": True, "action": action_name}
            else:
                rep = invoke_guarded(
                    action_name,
                    action_args,
                    ctx=VolitionContext(
                        chain_id=chain_id,
                        step="action",
                        actor="agent:volition_pulse",
                        intent=f"action:{action_name}",
                        action_kind=action_name,
                        needs=needs,
                        budgets=common_budgets,
                        metadata={"task_id": tid, "source": "volition.pulse"},
                    ),
                    gate=gate,
                )

            ok = bool((rep or {}).get("ok"))
            task["_last"] = now
            if str(task.get("kind") or "") == "once" and ok:
                task["_done"] = True

            evt = {
                "kind": "run",
                "id": tid,
                "action": action_name,
                "ok": ok,
                "slot": str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").upper(),
                "rep": {k: (rep or {}).get(k) for k in ["ok", "error", "reason_code", "reason", "slot"]},
            }
            _log(evt)
            if ok:
                done.append({"id": tid, "action": action_name, "ok": True})
            else:
                errors.append({"id": tid, "action": action_name, "ok": False, "error": (rep or {}).get("error")})

        save_cfg({"version": cfg.get("version", 1), "tasks": tasks})
        return {
            "ok": len(errors) == 0,
            "due": [str(t.get("id") or "") for t in due],
            "done": done,
            "skipped": skipped,
            "errors": errors,
        }


__all__ = ["load_cfg", "save_cfg", "tick", "status"]
