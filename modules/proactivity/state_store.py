# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOCK = threading.RLock()


def _persist_dir() -> Path:
    root = (os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def queue_path() -> Path:
    p = (_persist_dir() / "initiatives" / "queue.jsonl").resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.touch()
    return p


def state_path() -> Path:
    p = (_persist_dir() / "proactivity" / "executor_state.json").resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        save_state(
            {
                "processed_ids": [],
                "items": {},
                "runtime": {
                    "last_tick": None,
                    "last_ok": None,
                    "last_action_kind": "",
                    "last_denied_at": "",
                    "last_error": "",
                    "queue_size": 0,
                    "last_initiative_id": "",
                    "last_plan_id": "",
                    "last_template_id": "",
                    "last_agent_id": "",
                    "mode": {"plan_only": True, "run_safe": False},
                    "last_run_ts": None,
                },
            }
        )
    return p


def _default_state() -> Dict[str, Any]:
    return {
        "processed_ids": [],
        "items": {},
        "runtime": {
            "last_tick": None,
            "last_ok": None,
            "last_action_kind": "",
            "last_denied_at": "",
            "last_error": "",
            "queue_size": 0,
            "last_initiative_id": "",
            "last_plan_id": "",
            "last_template_id": "",
            "last_agent_id": "",
            "mode": {"plan_only": True, "run_safe": False},
            "last_run_ts": None,
        },
    }


def load_state() -> Dict[str, Any]:
    p = state_path()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("bad_state")
    except Exception:
        raw = _default_state()

    raw.setdefault("processed_ids", [])
    if not isinstance(raw["processed_ids"], list):
        raw["processed_ids"] = []
    raw.setdefault("items", {})
    if not isinstance(raw["items"], dict):
        raw["items"] = {}
    raw.setdefault("runtime", {})
    if not isinstance(raw["runtime"], dict):
        raw["runtime"] = {}
    raw["runtime"].setdefault("last_tick", None)
    raw["runtime"].setdefault("last_ok", None)
    raw["runtime"].setdefault("last_action_kind", "")
    raw["runtime"].setdefault("last_denied_at", "")
    raw["runtime"].setdefault("last_error", "")
    raw["runtime"].setdefault("queue_size", 0)
    raw["runtime"].setdefault("last_initiative_id", "")
    raw["runtime"].setdefault("last_plan_id", "")
    raw["runtime"].setdefault("last_template_id", "")
    raw["runtime"].setdefault("last_agent_id", "")
    raw["runtime"].setdefault("mode", {"plan_only": True, "run_safe": False})
    if not isinstance(raw["runtime"]["mode"], dict):
        raw["runtime"]["mode"] = {"plan_only": True, "run_safe": False}
    raw["runtime"].setdefault("last_run_ts", None)
    return raw


def save_state(state: Dict[str, Any]) -> None:
    p = state_path()
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


def _append_queue_row(row: Dict[str, Any]) -> None:
    with queue_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()


def queue_add(
    *,
    initiative_id: Optional[str] = None,
    title: str = "Synthetic initiative",
    text: str = "",
    priority: str = "normal",
    source: str = "manual",
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    iid = str(initiative_id or ("initiative_" + uuid.uuid4().hex))
    row = {
        "id": iid,
        "ts": int(time.time()),
        "title": str(title or "Synthetic initiative"),
        "text": str(text or ""),
        "priority": str(priority or "normal"),
        "status": "queued",
        "source": str(source or "manual"),
        "meta": dict(meta or {}),
    }
    with _LOCK:
        _append_queue_row(row)
    return {"ok": True, "initiative_id": iid, "row": row, "queue_path": str(queue_path())}


def read_queue() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with queue_path().open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except Exception:
                continue
            if isinstance(obj, dict):
                out.append(obj)
    return out


def mark_done(
    initiative_id: str,
    *,
    status: str = "done",
    note: str = "",
    agent_id: str = "",
    chain_id: str = "",
) -> Dict[str, Any]:
    iid = str(initiative_id or "").strip()
    if not iid:
        return {"ok": False, "error": "initiative_id_required"}
    now = int(time.time())
    with _LOCK:
        st = load_state()
        processed = [str(x) for x in list(st.get("processed_ids") or []) if str(x).strip()]
        if iid not in processed:
            processed.append(iid)
        if len(processed) > 10000:
            processed = processed[-10000:]
        st["processed_ids"] = processed

        items = dict(st.get("items") or {})
        items[iid] = {
            "status": str(status or "done"),
            "note": str(note or ""),
            "agent_id": str(agent_id or ""),
            "chain_id": str(chain_id or ""),
            "updated_ts": now,
        }
        st["items"] = items
        save_state(st)
    return {"ok": True, "initiative_id": iid, "updated": True, "status": str(status or "done")}


def runtime_update(
    *,
    last_tick: Optional[str] = None,
    last_ok: Optional[bool] = None,
    last_action_kind: Optional[str] = None,
    last_denied_at: Optional[str] = None,
    last_error: Optional[str] = None,
    queue_size: Optional[int] = None,
    last_initiative_id: Optional[str] = None,
    last_plan_id: Optional[str] = None,
    last_template_id: Optional[str] = None,
    last_agent_id: Optional[str] = None,
    mode: Optional[Dict[str, Any]] = None,
    last_run_ts: Optional[int] = None,
) -> Dict[str, Any]:
    with _LOCK:
        st = load_state()
        rt = dict(st.get("runtime") or {})
        if last_tick is not None:
            rt["last_tick"] = last_tick
        if last_ok is not None:
            rt["last_ok"] = bool(last_ok)
        if last_action_kind is not None:
            rt["last_action_kind"] = str(last_action_kind or "")
        if last_denied_at is not None:
            rt["last_denied_at"] = str(last_denied_at or "")
        if last_error is not None:
            rt["last_error"] = str(last_error or "")
        if queue_size is not None:
            rt["queue_size"] = max(0, int(queue_size or 0))
        if last_initiative_id is not None:
            rt["last_initiative_id"] = str(last_initiative_id or "")
        if last_plan_id is not None:
            rt["last_plan_id"] = str(last_plan_id or "")
        if last_template_id is not None:
            rt["last_template_id"] = str(last_template_id or "")
        if last_agent_id is not None:
            rt["last_agent_id"] = str(last_agent_id or "")
        if mode is not None:
            m = dict(rt.get("mode") or {"plan_only": True, "run_safe": False})
            m.update(dict(mode or {}))
            m["plan_only"] = bool(m.get("plan_only", True))
            m["run_safe"] = bool(m.get("run_safe", False))
            rt["mode"] = m
        if last_run_ts is not None:
            rt["last_run_ts"] = int(last_run_ts)
        st["runtime"] = rt
        save_state(st)
    return {"ok": True, "runtime": rt}


def runtime_snapshot() -> Dict[str, Any]:
    st = load_state()
    rt = dict(st.get("runtime") or {})
    rt.setdefault("last_tick", None)
    rt.setdefault("last_ok", None)
    rt.setdefault("last_action_kind", "")
    rt.setdefault("last_denied_at", "")
    rt.setdefault("last_error", "")
    rt.setdefault("queue_size", 0)
    rt.setdefault("last_initiative_id", "")
    rt.setdefault("last_plan_id", "")
    rt.setdefault("last_template_id", "")
    rt.setdefault("last_agent_id", "")
    rt.setdefault("mode", {"plan_only": True, "run_safe": False})
    if not isinstance(rt.get("mode"), dict):
        rt["mode"] = {"plan_only": True, "run_safe": False}
    rt.setdefault("last_run_ts", None)
    return rt


def processed_ids() -> List[str]:
    st = load_state()
    return [str(x) for x in list(st.get("processed_ids") or []) if str(x).strip()]


__all__ = [
    "queue_path",
    "state_path",
    "load_state",
    "save_state",
    "queue_add",
    "read_queue",
    "mark_done",
    "runtime_update",
    "runtime_snapshot",
    "processed_ids",
]
