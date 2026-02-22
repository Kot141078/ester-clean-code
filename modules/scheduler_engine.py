# -*- coding: utf-8 -*-
"""
modules/scheduler_engine.py — unifitsirovannyy fasad planirovschika (v1+v2) + API dlya /autonomy.

MOSTY:
- (Yavnyy) Staroe API (create_task(kind,payload,due_ts), run_due→list) ↔ Novoe API (create_task(kind,action,rrule,payload), run_due→count).
- (Skrytyy #1) Planirovschik ↔ Shina sobytiy: deystvie publish_event pishet v modules.events_bus.
- (Skrytyy #2) /autonomy/* ↔ «yadro» planirovschika: dobavleny start/stop/status/schedule/cancel bez lomki kontraktov.

ZEMNOY ABZATs:
Eto privychnyy «kvartsevyy budilnik» s zapisnoy knizhkoy. Zadal pravilo (kazhdye N sekund/minut) — i on budet vovremya «pikat»,
skladyvaya otmetki v istoriyu i podnimaya sobytiya, poka ty ne otklyuchish.

Drop-in: signatury suschestvuyuschikh funktsiy sokhraneny; dobavleny tolko novye, kotorye uzhe zhdut marshruty.
"""
from __future__ import annotations
import json, os, time, uuid
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# -------- persist layout --------
def _mirror_background_event(text: str, source: str, kind: str) -> None:
    try:
        meta = {"source": str(source), "type": str(kind), "scope": "global", "ts": time.time()}
        try:
            from modules.memory import store  # type: ignore
            memory_add("dialog", text, meta=meta)
        except Exception:
            pass
        try:
            from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
            ch = get_chroma_ui()
            if False:
                pass
        except Exception:
            pass
    except Exception:
        pass

def _persist_dir() -> str:
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    path = os.path.join(base, "scheduler")
    os.makedirs(path, exist_ok=True)
    return path

def _tasks_path() -> str:
    return os.path.join(_persist_dir(), "tasks.json")

def _state_path() -> str:
    return os.path.join(_persist_dir(), "state.json")

def _history_path() -> str:
    return os.path.join(_persist_dir(), "history.ndjson")

# -------- io helpers --------
def _load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _save_json(path: str, data) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)

def _load_state() -> Dict[str, Any]:
    st = _load_json(_state_path(), {"enabled": False, "last_tick": 0.0})
    st["enabled"] = bool(st.get("enabled", False))
    st["last_tick"] = float(st.get("last_tick", 0.0))
    return st

def _save_state(st: Dict[str, Any]) -> None:
    _save_json(_state_path(), {"enabled": bool(st.get("enabled", False)),
                               "last_tick": float(st.get("last_tick", 0.0))})

def _load_tasks() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = _load_json(_tasks_path(), [])
    # normiruem bazovye polya
    out: List[Dict[str, Any]] = []
    for t in items:
        out.append({
            "id": str(t.get("id") or uuid.uuid4().hex),
            "kind": str(t.get("kind") or ""),
            "action": str(t.get("action") or t.get("type") or "call"),
            "rrule": str(t.get("rrule") or ""),
            "payload": t.get("payload"),
            "next_run_ts": float(t.get("next_run_ts") or t.get("due_ts") or 0.0),
            "last_run_ts": float(t.get("last_run_ts") or 0.0),
            "active": bool(t.get("active", True)),
        })
    return out

def _save_tasks(items: List[Dict[str, Any]]) -> None:
    _save_json(_tasks_path(), items)

def _append_history(rec: Dict[str, Any]) -> None:
    try:
        line = json.dumps(rec, ensure_ascii=False) + "\n"
        with open(_history_path(), "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

# -------- rrule helpers (minimum, dostatochnyy dlya testa v2) --------
def _parse_rrule(rrule: str) -> Tuple[str, int]:
    """
    Vozvraschaet (freq, interval_sec). Podderzhivaem SECONDLY/MINUTELY/HOURLY.
    """
    if not rrule:
        return ("", 0)
    s = rrule.upper().strip()
    # Primer: "RRULE:FREQ=MINUTELY;INTERVAL=1"
    if s.startswith("RRULE:"):
        s = s[6:]
    parts = dict((kv.split("=", 1) + [""])[:2] for kv in s.split(";") if "=" in kv)
    freq = parts.get("FREQ", "")
    interval = int(parts.get("INTERVAL", "1") or "1")
    if freq == "SECONDLY":
        return (freq, max(1, interval))
    if freq == "MINUTELY":
        return (freq, max(1, interval) * 60)
    if freq == "HOURLY":
        return (freq, max(1, interval) * 3600)
    return ("", 0)

def _next_from_rrule(now_ts: float, rrule: str) -> float:
    _, step = _parse_rrule(rrule)
    return (now_ts + step) if step > 0 else 0.0

# -------- public API: v1 + v2 --------
def list_tasks() -> Dict[str, Any]:
    return {"ok": True, "items": _load_tasks()}

def cancel_task(task_id: str) -> Dict[str, Any]:
    items = _load_tasks()
    before = len(items)
    items = [t for t in items if str(t.get("id")) != str(task_id)]
    _save_tasks(items)
    try:
        _mirror_background_event(
            f"[SCHED_CANCEL] id={task_id}",
            "scheduler_engine",
            "cancel",
        )
    except Exception:
        pass
    return {"ok": True, "removed": (before - len(items))}

def create_task(*args, **kwargs) -> Dict[str, Any]:
    """
    Sovmeschennaya signatura:
      v1: create_task(kind: str, payload: Any, due_ts: float)
      v2: create_task(kind: str, action: str, rrule: str, payload: Any)
    """
    now = time.time()
    items = _load_tasks()

    # detect v2
    if ("rrule" in kwargs) or (len(args) >= 3 and isinstance(args[2], str) and "RRULE:" in str(args[2]).upper()):
        # v2
        kind = str(args[0] if len(args) >= 1 else kwargs.get("kind", ""))
        action = str(args[1] if len(args) >= 2 else kwargs.get("action", ""))
        rrule = str(args[2] if len(args) >= 3 else kwargs.get("rrule", ""))
        payload = args[3] if len(args) >= 4 else kwargs.get("payload")
        next_ts = _next_from_rrule(now, rrule) or (now + 60.0)
        tid = uuid.uuid4().hex
        rec = {"id": tid, "kind": kind, "action": action, "rrule": rrule,
               "payload": payload, "next_run_ts": float(next_ts), "last_run_ts": 0.0, "active": True}
        items.append(rec); _save_tasks(items)
        try:
            _mirror_background_event(
                f"[SCHED_CREATE] id={tid} kind={kind} action={action}",
                "scheduler_engine",
                "create",
            )
        except Exception:
            pass
        return {"ok": True, "id": tid, "next_run_ts": float(next_ts)}

    # v1
    kind = str(args[0] if len(args) >= 1 else kwargs.get("kind", ""))
    payload = args[1] if len(args) >= 2 else kwargs.get("payload")
    due_ts = float(args[2] if len(args) >= 3 else kwargs.get("due_ts", now))
    tid = uuid.uuid4().hex
    rec = {"id": tid, "kind": kind, "action": "call", "rrule": "",
           "payload": payload, "next_run_ts": float(due_ts), "last_run_ts": 0.0, "active": True}
    items.append(rec); _save_tasks(items)
    try:
        _mirror_background_event(
            f"[SCHED_CREATE] id={tid} kind={kind} action=call",
            "scheduler_engine",
            "create",
        )
    except Exception:
        pass
    return {"ok": True, "id": tid, "next_run_ts": float(due_ts)}

def run_due(now_ts: float | None = None) -> Dict[str, Any]:
    now = float(now_ts if now_ts is not None else time.time())
    items = _load_tasks()
    ran_items: List[Dict[str, Any]] = []
    left = 0

    for t in list(items):
        if not t.get("active", True):
            continue
        if float(t.get("next_run_ts", 0.0)) > now:
            left += 1
            continue

        kind = str(t.get("kind") or "")
        action = str(t.get("action") or "")
        payload = t.get("payload")

        try:
            if action == "publish_event":
                # ozhidaemyy deshevyy ekshen dlya testov
                from modules.events_bus import publish  # type: ignore
                ev_kind = str((payload or {}).get("kind") or kind or "tick")
                ev_payload = (payload or {}).get("payload")
                publish(ev_kind, ev_payload)
            elif action == "retrieval_router_snapshot":
                try:
                    from modules.rag.retrieval_router import snapshot_metrics_to_memory  # type: ignore
                    snapshot_metrics_to_memory()
                except Exception:
                    pass
            # inye action mogut byt dobavleny pozzhe (vnutrennie vyzovy, gc i t.p.)

            ran_items.append({"id": t["id"], "kind": kind, "action": action, "ts": now})
            t["last_run_ts"] = now

            # pereschet next_run_ts po rrule
            if t.get("rrule"):
                step_next = _next_from_rrule(now, str(t["rrule"]))
                if step_next > 0:
                    t["next_run_ts"] = float(step_next)
                else:
                    t["active"] = False
            else:
                t["active"] = False
        except Exception as e:
            # fiksiruem oshibku i ostavlyaem zadachu aktivnoy (na sleduyuschuyu popytku)
            _append_history({"ts": now, "id": t.get("id"), "kind": kind, "action": action,
                             "error": f"{type(e).__name__}: {e}"})
            try:
                _mirror_background_event(
                    f"[SCHED_RUN_ERROR] id={t.get('id')} action={action} err={e}",
                    "scheduler_engine",
                    "run_error",
                )
            except Exception:
                pass

    _save_tasks(items)
    st = _load_state(); st["last_tick"] = now; _save_state(st)
    try:
        _mirror_background_event(
            f"[SCHED_RUN_DUE] ran={len(ran_items)} left={left}",
            "scheduler_engine",
            "run_due",
        )
    except Exception:
        pass
    # dlya sovmestimosti: vozvraschaem i schetchik, i podrobnosti
    return {"ok": True, "ran": len(ran_items), "ran_items": ran_items, "left": left}

# -------- autonomy facade (ozhidayut marshruty /autonomy/*) --------
def start() -> Dict[str, Any]:
    st = _load_state(); st["enabled"] = True; _save_state(st)
    try:
        _mirror_background_event(
            "[SCHED_START]",
            "scheduler_engine",
            "start",
        )
    except Exception:
        pass
    return {"ok": True, "enabled": True}

def stop() -> Dict[str, Any]:
    st = _load_state(); st["enabled"] = False; _save_state(st)
    try:
        _mirror_background_event(
            "[SCHED_STOP]",
            "scheduler_engine",
            "stop",
        )
    except Exception:
        pass
    return {"ok": True, "enabled": False}

def status() -> Dict[str, Any]:
    st = _load_state()
    items = _load_tasks()
    now = time.time()
    next_due = min([float(t.get("next_run_ts") or 0.0) - now for t in items if t.get("active", True)], default=-1.0)
    return {"ok": True, "enabled": bool(st.get("enabled", False)), "tasks": len(items),
            "last_tick": float(st.get("last_tick", 0.0)), "next_due_in": float(next_due)}

def schedule(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ozhidaniya iz routes/autonomy_routes.py: {type, interval_sec, ...}
    Mappim na publish_event s rrule SECONDLY.
    """
    t = str(body.get("type") or "")
    if not t:
        return {"ok": False, "error": "type_required"}
    interval = int(body.get("interval_sec", 60) or 60)
    rrule = f"RRULE:FREQ=SECONDLY;INTERVAL={max(1, interval)}"
    payload = {"kind": t, "payload": dict(body.get("payload") or {})}
    res = create_task("autonomy", "publish_event", rrule, payload)
    return {"ok": True, "task": res}

def cancel(task_id: str) -> Dict[str, Any]:
    return cancel_task(task_id)

# c=a+b
