# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import random
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import json

from modules.dreams.dream_engine import DreamRunner
from modules.memory.memory_bus import MemoryBus
from modules.proactivity.initiative_engine import InitiativeEngine
try:
    from modules.agents import runtime as agents_runtime  # type: ignore
except Exception:  # pragma: no cover
    agents_runtime = None  # type: ignore
try:
    from modules.proactivity import state_store as proactivity_state_store  # type: ignore
except Exception:  # pragma: no cover
    proactivity_state_store = None  # type: ignore
try:
    from modules.companion import outbox as companion_outbox  # type: ignore
except Exception:  # pragma: no cover
    companion_outbox = None  # type: ignore
try:
    from modules.companion import companion_engine  # type: ignore
except Exception:  # pragma: no cover
    companion_engine = None  # type: ignore
try:
    from modules.runtime import comm_window  # type: ignore
except Exception:  # pragma: no cover
    comm_window = None  # type: ignore
try:
    from modules.runtime import oracle_window  # type: ignore
except Exception:  # pragma: no cover
    oracle_window = None  # type: ignore
try:
    from modules.runtime import oracle_requests  # type: ignore
except Exception:  # pragma: no cover
    oracle_requests = None  # type: ignore
try:
    from modules.garage import agent_queue as garage_agent_queue  # type: ignore
except Exception:  # pragma: no cover
    garage_agent_queue = None  # type: ignore
try:
    from modules.runtime import capability_audit as runtime_capability_audit  # type: ignore
except Exception:  # pragma: no cover
    runtime_capability_audit = None  # type: ignore
try:
    from modules.runtime import capability_drift as runtime_capability_drift  # type: ignore
except Exception:  # pragma: no cover
    runtime_capability_drift = None  # type: ignore
try:
    from modules.runtime import drift_quarantine as runtime_drift_quarantine  # type: ignore
except Exception:  # pragma: no cover
    runtime_drift_quarantine = None  # type: ignore
try:
    from modules.runtime import integrity_verifier as runtime_integrity_verifier  # type: ignore
except Exception:  # pragma: no cover
    runtime_integrity_verifier = None  # type: ignore
try:
    from modules.runtime import network_deny as runtime_network_deny  # type: ignore
except Exception:  # pragma: no cover
    runtime_network_deny = None  # type: ignore
try:
    from modules.curiosity import unknown_detector as curiosity_unknown_detector  # type: ignore
except Exception:  # pragma: no cover
    curiosity_unknown_detector = None  # type: ignore
try:
    from modules.curiosity import executor as curiosity_executor  # type: ignore
except Exception:  # pragma: no cover
    curiosity_executor = None  # type: ignore

_LOCK = threading.RLock()
_BG_THREAD: Optional[threading.Thread] = None
_BG_STOP = threading.Event()
_BG_FORCE_DISABLED = False

_STATE: Dict[str, Any] = {
    "dreams": {
        "last_run": None,
        "last_ok": None,
        "last_error": "",
        "last_count": 0,
    },
    "initiatives": {
        "last_run": None,
        "last_ok": None,
        "last_error": "",
        "queue_size": 0,
    },
    "background": {
        "enabled": False,
        "thread_alive": False,
        "last_tick": None,
        "last_skip_reason": "",
        "failures": 0,
    },
}

_DREAMS = DreamRunner()
_INITIATIVES = InitiativeEngine()


def _now_iso(ts: Optional[float] = None) -> str:
    value = float(ts if ts is not None else time.time())
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, "1" if default else "0")).strip().lower()
    return raw in {"1", "true", "yes", "on", "y"}


def _bg_interval_sec() -> float:
    try:
        return max(1.0, float(os.getenv("ESTER_BG_INTERVAL_SEC", "60") or 60.0))
    except Exception:
        return 60.0


def _bg_max_work_ms() -> int:
    try:
        return max(100, int(os.getenv("ESTER_BG_MAX_WORK_MS", "2000") or 2000))
    except Exception:
        return 2000


def _bg_fail_max() -> int:
    try:
        return max(1, int(os.getenv("ESTER_BG_FAIL_MAX", "3") or 3))
    except Exception:
        return 3


def _bg_enabled_env() -> bool:
    if _BG_FORCE_DISABLED:
        return False
    return _env_bool("ESTER_BG_ENABLE", False)


def _memory_bus() -> MemoryBus:
    return MemoryBus(use_vector=False, use_chroma=False)


def _set_bg_skip(reason: str) -> None:
    with _LOCK:
        _STATE["background"]["last_skip_reason"] = str(reason or "")


def _update_queue_size() -> int:
    st = _INITIATIVES.status()
    q = int(st.get("queue_size") or 0)
    with _LOCK:
        _STATE["initiatives"]["queue_size"] = q
    return q


def _persist_dir() -> Path:
    raw = str(os.getenv("PERSIST_DIR") or "").strip()
    if not raw:
        raw = str((Path.cwd() / "data").resolve())
    return Path(raw).resolve()


def _runtime_slot() -> str:
    raw = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if raw == "B" else "A"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                row = json.loads(s)
            except Exception:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def _proactivity_enqueue_summary() -> Dict[str, Any]:
    path = (_persist_dir() / "proactivity" / "enqueue.jsonl").resolve()
    rows = _read_jsonl(path)
    out: Dict[str, Any] = {
        "last_plan_ts": None,
        "last_enqueue_ts": None,
        "last_ok": None,
        "last_error": "",
        "last_enqueue_id": "",
    }
    if not rows:
        return out

    last = rows[-1]
    out["last_ok"] = bool(last.get("ok")) if ("ok" in last) else None
    out["last_error"] = str(last.get("error") or "")

    plan_ts = 0
    enqueue_ts = 0
    last_enqueue_id = ""
    for row in rows:
        ts = int(row.get("ts") or 0)
        if str(row.get("plan_id") or "").strip() and ts >= plan_ts:
            plan_ts = ts
        eid = str(row.get("enqueue_id") or "").strip()
        if eid and ts >= enqueue_ts:
            enqueue_ts = ts
            last_enqueue_id = eid
    out["last_plan_ts"] = (plan_ts or None)
    out["last_enqueue_ts"] = (enqueue_ts or None)
    out["last_enqueue_id"] = last_enqueue_id
    return out


def _queue_summary() -> Dict[str, Any]:
    out = {"size": 0, "last_enqueue_id": ""}
    if garage_agent_queue is None:
        return out
    try:
        st = garage_agent_queue.fold_state()
        out["size"] = max(0, int(st.get("live_total") or 0))
    except Exception:
        out["size"] = 0
    try:
        evs = garage_agent_queue.events()
        for row in reversed(evs):
            if str(row.get("type") or "") == "enqueue":
                out["last_enqueue_id"] = str(row.get("queue_id") or "")
                break
    except Exception:
        pass
    return out


def run_dream_once(dry: bool = False, budgets: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    now = _now_iso()
    with _LOCK:
        _STATE["dreams"]["last_run"] = now
        _STATE["dreams"]["last_error"] = ""

    bus = _memory_bus()
    readiness = bus.readiness_status()
    if not bool(readiness.get("memory_ready")):
        err = "memory_not_ready"
        with _LOCK:
            _STATE["dreams"]["last_ok"] = False
            _STATE["dreams"]["last_error"] = err
            _STATE["dreams"]["last_count"] = 0
        return {"ok": False, "error": err, "readiness": readiness}

    rep = _DREAMS.run_once(bus, budgets=budgets, dry=bool(dry))
    with _LOCK:
        _STATE["dreams"]["last_ok"] = bool(rep.get("ok"))
        _STATE["dreams"]["last_error"] = str(rep.get("error") or "")
        _STATE["dreams"]["last_count"] = int(rep.get("last_count") or 0)
    return rep


def run_initiatives_once(dry: bool = False, budgets: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    now = _now_iso()
    with _LOCK:
        _STATE["initiatives"]["last_run"] = now
        _STATE["initiatives"]["last_error"] = ""

    bus = _memory_bus()
    readiness = bus.readiness_status()
    if not bool(readiness.get("memory_ready")):
        err = "memory_not_ready"
        with _LOCK:
            _STATE["initiatives"]["last_ok"] = False
            _STATE["initiatives"]["last_error"] = err
        return {"ok": False, "error": err, "readiness": readiness}

    rep = _INITIATIVES.run_once(bus, budgets=budgets, dry=bool(dry))
    with _LOCK:
        _STATE["initiatives"]["last_ok"] = bool(rep.get("ok"))
        _STATE["initiatives"]["last_error"] = str(rep.get("error") or "")
        _STATE["initiatives"]["queue_size"] = int(rep.get("queue_size") or 0)
    return rep


def background_tick_once(dry: bool = False) -> Dict[str, Any]:
    start = time.monotonic()
    now = _now_iso()
    with _LOCK:
        _STATE["background"]["last_tick"] = now
        _STATE["background"]["last_skip_reason"] = ""

    bus = _memory_bus()
    readiness = bus.readiness_status()
    if not bool(readiness.get("memory_ready")):
        _set_bg_skip("memory_not_ready")
        return {"ok": True, "skipped": True, "reason": "memory_not_ready", "readiness": readiness}

    max_work_ms = _bg_max_work_ms()
    out: Dict[str, Any] = {"ok": True, "skipped": False, "dreams": None, "initiatives": None}
    try:
        if _env_bool("ESTER_DREAMS_ENABLE", True):
            out["dreams"] = run_dream_once(dry=dry)
        else:
            out["dreams"] = {"ok": True, "disabled": True}

        spent_ms = int((time.monotonic() - start) * 1000.0)
        if spent_ms >= max_work_ms:
            out["initiatives"] = {"ok": True, "skipped": True, "reason": "budget_exceeded"}
            _set_bg_skip("budget_exceeded")
            with _LOCK:
                _STATE["background"]["failures"] = 0
            return out

        if _env_bool("ESTER_INITIATIVES_ENABLE", True):
            out["initiatives"] = run_initiatives_once(dry=dry)
        else:
            out["initiatives"] = {"ok": True, "disabled": True}

        with _LOCK:
            _STATE["background"]["failures"] = 0
        return out
    except Exception as exc:
        err = str(exc)
        with _LOCK:
            failures = int(_STATE["background"].get("failures") or 0) + 1
            _STATE["background"]["failures"] = failures
            _STATE["background"]["last_skip_reason"] = err
        if failures >= _bg_fail_max():
            disable_background_in_process(reason="auto_rollback_bg_failures")
        return {"ok": False, "error": err}


def disable_background_in_process(reason: str = "") -> None:
    global _BG_FORCE_DISABLED
    _BG_FORCE_DISABLED = True
    _BG_STOP.set()
    with _LOCK:
        _STATE["background"]["enabled"] = False
        _STATE["background"]["last_skip_reason"] = str(reason or "disabled")


def _bg_loop() -> None:
    while not _BG_STOP.is_set():
        interval = _bg_interval_sec()
        jitter = random.uniform(-0.1, 0.1) * interval
        sleep_s = max(0.5, interval + jitter)
        if _BG_STOP.wait(timeout=sleep_s):
            break
        background_tick_once(dry=False)


def start_background_if_enabled() -> Dict[str, Any]:
    global _BG_THREAD
    enabled = _bg_enabled_env()
    with _LOCK:
        _STATE["background"]["enabled"] = bool(enabled)

    if not enabled:
        _BG_STOP.set()
        with _LOCK:
            _STATE["background"]["thread_alive"] = bool(_BG_THREAD and _BG_THREAD.is_alive())
        return {"ok": True, "enabled": False, "thread_alive": bool(_BG_THREAD and _BG_THREAD.is_alive())}

    if _BG_THREAD and _BG_THREAD.is_alive():
        with _LOCK:
            _STATE["background"]["thread_alive"] = True
        return {"ok": True, "enabled": True, "thread_alive": True}

    _BG_STOP.clear()
    _BG_THREAD = threading.Thread(target=_bg_loop, name="ester-bg-iter18", daemon=True)
    _BG_THREAD.start()
    with _LOCK:
        _STATE["background"]["thread_alive"] = True
    return {"ok": True, "enabled": True, "thread_alive": True}


def runtime_status() -> Dict[str, Any]:
    start_background_if_enabled()
    bus = _memory_bus()
    readiness = bus.readiness_status()
    queue_size = _update_queue_size()

    with _LOCK:
        dreams = dict(_STATE["dreams"])
        initiatives = dict(_STATE["initiatives"])
        background = dict(_STATE["background"])
        background["thread_alive"] = bool(_BG_THREAD and _BG_THREAD.is_alive())
        background["enabled"] = bool(_bg_enabled_env())
        initiatives["queue_size"] = queue_size

    agents_payload: Dict[str, Any] = {
        "enabled": False,
        "templates": [],
        "total": 0,
        "total_agents": 0,
        "last_run": None,
        "last_ok": None,
        "last_error": "",
    }
    if agents_runtime is not None:
        try:
            st_agents = agents_runtime.status()
            if isinstance(st_agents, dict):
                agents_payload = {
                    "enabled": bool(st_agents.get("enabled")),
                    "templates": list(st_agents.get("templates") or []),
                    "total": int(st_agents.get("total") or 0),
                    "total_agents": int(st_agents.get("total_agents") or st_agents.get("total") or 0),
                    "last_run": st_agents.get("last_run"),
                    "last_ok": st_agents.get("last_ok"),
                    "last_error": str(st_agents.get("last_error") or ""),
                    "last_action_kind": str(st_agents.get("last_action_kind") or ""),
                    "disabled_in_process": bool(st_agents.get("disabled_in_process")),
                }
        except Exception as exc:
            agents_payload = {
                "enabled": False,
                "templates": [],
                "total": 0,
                "total_agents": 0,
                "last_run": None,
                "last_ok": False,
                "last_error": str(exc),
            }

    proactivity_payload: Dict[str, Any] = {
        "queue_size": 0,
        "last_initiative_id": "",
        "last_plan_id": "",
        "last_template_id": "",
        "last_agent_id": "",
        "last_plan_ts": None,
        "last_enqueue_ts": None,
        "mode": {"plan_only": True, "run_safe": False},
        "last_ok": None,
        "last_error": "",
        "last_run_ts": None,
        # Backward-compatible fields.
        "last_tick": None,
        "last_action_kind": "",
        "last_denied_at": "",
    }
    if proactivity_state_store is not None:
        try:
            p = proactivity_state_store.runtime_snapshot()
            if isinstance(p, dict):
                mode = dict(p.get("mode") or {})
                proactivity_payload.update(
                    {
                        "queue_size": int(p.get("queue_size") or 0),
                        "last_initiative_id": str(p.get("last_initiative_id") or ""),
                        "last_plan_id": str(p.get("last_plan_id") or ""),
                        "last_template_id": str(p.get("last_template_id") or ""),
                        "last_agent_id": str(p.get("last_agent_id") or ""),
                        "mode": {
                            "plan_only": bool(mode.get("plan_only", True)),
                            "run_safe": bool(mode.get("run_safe", False)),
                        },
                        "last_tick": p.get("last_tick"),
                        "last_ok": p.get("last_ok"),
                        "last_action_kind": str(p.get("last_action_kind") or ""),
                        "last_denied_at": str(p.get("last_denied_at") or ""),
                        "last_error": str(p.get("last_error") or ""),
                        "last_run_ts": p.get("last_run_ts"),
                    }
                )
        except Exception as exc:
            proactivity_payload["last_error"] = str(exc)

    try:
        p_sum = _proactivity_enqueue_summary()
        proactivity_payload["last_plan_ts"] = p_sum.get("last_plan_ts")
        proactivity_payload["last_enqueue_ts"] = p_sum.get("last_enqueue_ts")
        if p_sum.get("last_ok") is not None:
            proactivity_payload["last_ok"] = p_sum.get("last_ok")
        if str(p_sum.get("last_error") or "").strip():
            proactivity_payload["last_error"] = str(p_sum.get("last_error") or "")
    except Exception:
        pass

    queue_payload = _queue_summary()
    if int(proactivity_payload.get("queue_size") or 0) <= 0:
        proactivity_payload["queue_size"] = int(queue_payload.get("size") or 0)

    outbox_payload: Dict[str, Any] = {"count_recent": 0, "last_msg_ts": None, "last_kind": ""}
    if companion_outbox is not None:
        try:
            s = companion_outbox.summary(recent_n=50)
            if isinstance(s, dict):
                outbox_payload = {
                    "count_recent": int(s.get("count_recent") or 0),
                    "last_msg_ts": s.get("last_msg_ts"),
                    "last_kind": str(s.get("last_kind") or ""),
                }
        except Exception:
            pass

    comm_payload: Dict[str, Any] = {"open_count": 0}
    if comm_window is not None:
        try:
            cw = comm_window.list_windows()
            if isinstance(cw, dict):
                comm_payload = {"open_count": int(cw.get("count") or 0)}
        except Exception:
            pass

    companion_payload: Dict[str, Any] = {"last_tick": None, "last_ok": None, "last_error": ""}
    last_explained_chain_id = ""
    if companion_engine is not None:
        try:
            cs = companion_engine.status()
            if isinstance(cs, dict):
                companion_payload = {
                    "last_tick": cs.get("last_tick"),
                    "last_ok": cs.get("last_ok"),
                    "last_error": str(cs.get("last_error") or ""),
                }
                last_explained_chain_id = str(cs.get("last_explained_chain_id") or "")
        except Exception:
            pass

    oracle_payload: Dict[str, Any] = {
        "enabled": False,
        "open": False,
        "window_id": "",
        "remaining_sec": 0,
        "expires_ts": 0,
        "actor": "",
        "allow_agents": False,
        "budgets_left": {},
    }
    oracle_calls_payload: Dict[str, Any] = {"last_ok": None, "last_error": "", "last_call_ts": None}
    oracle_requests_payload: Dict[str, Any] = {
        "pending_count": 0,
        "approved_count_recent": 0,
        "last_request_id": "",
        "last_approved_id": "",
    }
    if oracle_window is not None:
        try:
            ow = oracle_window.current_window()
            if isinstance(ow, dict):
                oracle_payload = {
                    "enabled": bool(os.getenv("ESTER_ORACLE_ENABLE", "0") in {"1", "true", "yes", "on", "y"}),
                    "open": bool(ow.get("open")),
                    "window_id": str(ow.get("window_id") or ""),
                    "remaining_sec": int(ow.get("remaining_sec") or 0),
                    "expires_ts": int(ow.get("expires_ts") or 0),
                    "actor": str(ow.get("actor") or ""),
                    "allow_agents": bool(ow.get("allow_agents")),
                    "budgets_left": dict(ow.get("budgets_left") or {}),
                }
            lc = oracle_window.last_call_status()
            if isinstance(lc, dict):
                oracle_calls_payload = {
                    "last_ok": lc.get("ok"),
                    "last_error": str(lc.get("error") or ""),
                    "last_call_ts": lc.get("ts"),
                }
        except Exception:
            pass
    if oracle_requests is not None:
        try:
            rs = oracle_requests.summary()
            if isinstance(rs, dict):
                oracle_requests_payload = {
                    "pending_count": int(rs.get("pending_count") or 0),
                    "approved_count_recent": int(rs.get("approved_count_recent") or 0),
                    "last_request_id": str(rs.get("last_request_id") or ""),
                    "last_approved_id": str(rs.get("last_approved_id") or ""),
                }
        except Exception:
            pass

    capability_audit_payload: Dict[str, Any] = {
        "ok": False,
        "slot": "A",
        "degraded": True,
        "error": "audit_unavailable",
        "agents": {
            "total": 0,
            "capability_mode": 0,
            "template_legacy": 0,
            "raw_capabilities": 0,
            "pure_legacy": 0,
            "authority_missing": 0,
        },
        "clamp": {
            "total_recent": 0,
            "last_ts": 0,
            "last_agent_id": "",
            "last_reason_code": "",
            "last_warnings": [],
            "by_code": {},
        },
        "deny": {
            "total_recent": 0,
            "last_ts": 0,
            "last_step": "",
            "last_agent_id": "",
            "last_reason_code": "",
            "last_action_id": "",
            "by_code": {},
        },
        "recent_events": [],
        "perf": {
            "cache_ttl_sec": 0,
            "scanned_agents": 0,
            "journal_tail_lines": 0,
            "build_ms": 0,
            "fail_streak": 0,
            "fail_max": 0,
            "audit_mode_forced": "",
            "audit_last_rollback_reason": "",
        },
        "audit_mode_forced": "",
        "audit_last_rollback_reason": "",
    }
    if runtime_capability_audit is not None:
        try:
            built = runtime_capability_audit.build_capability_audit()
            if isinstance(built, dict):
                capability_audit_payload = built
        except Exception as exc:
            capability_audit_payload["error"] = str(exc)

    capability_drift_payload: Dict[str, Any] = {
        "ok": False,
        "slot": "A",
        "degraded": True,
        "error": "drift_unavailable",
        "summary": {
            "scanned_agents": 0,
            "scan_limited": False,
            "mismatches": 0,
            "changed": 0,
            "caps_changed": 0,
            "escalations": 0,
            "last_event_ts": 0,
        },
        "last_event": {
            "ts": 0,
            "agent_id": "",
            "kind": "",
            "severity": "",
            "reason_code": "",
            "old_hash": "",
            "new_hash": "",
            "template_id": "",
            "added": [],
            "removed": [],
        },
        "recent_events": [],
        "perf": {
            "cache_ttl_sec": 0,
            "build_ms": 0,
            "last_seen_size": 0,
            "events_tail_lines": 0,
            "fail_streak": 0,
            "fail_max": 0,
            "mode_forced": "",
            "last_rollback_reason": "",
        },
    }
    if runtime_capability_drift is not None:
        try:
            built = runtime_capability_drift.build_capability_drift()
            if isinstance(built, dict):
                capability_drift_payload = built
        except Exception as exc:
            capability_drift_payload["error"] = str(exc)

    drift_quarantine_payload: Dict[str, Any] = {
        "ok": False,
        "slot": "A",
        "enforced": False,
        "degraded": True,
        "error": "quarantine_unavailable",
        "summary": {
            "active": 0,
            "cleared": 0,
            "set_recent": 0,
            "block_recent": 0,
            "last_set_ts": 0,
            "last_block_ts": 0,
        },
        "last_event": {
            "ts": 0,
            "type": "",
            "agent_id": "",
            "event_id": "",
            "reason_code": "",
            "severity": "",
            "step": "",
        },
        "active_agents_sample": [],
        "perf": {
            "cache_ttl_sec": 0,
            "build_ms": 0,
            "state_size": 0,
            "tail_lines": 0,
            "fail_streak": 0,
            "fail_max": 0,
            "mode_forced": "",
            "last_rollback_reason": "",
        },
    }
    if runtime_drift_quarantine is not None:
        try:
            built = runtime_drift_quarantine.build_drift_quarantine_status()
            if isinstance(built, dict):
                drift_quarantine_payload = built
        except Exception as exc:
            drift_quarantine_payload["error"] = str(exc)

    l4w_payload: Dict[str, Any] = {
        "ok": False,
        "slot": str(drift_quarantine_payload.get("slot") or "A"),
        "enforced": bool(drift_quarantine_payload.get("enforced")),
        "degraded": bool(drift_quarantine_payload.get("degraded")),
        "chain": {
            "agents_tracked": 0,
            "total_records": 0,
            "last_envelope_ts": 0,
            "last_envelope_hash": "",
            "last_prev_hash": "",
            "last_error": "l4w_unavailable",
        },
        "last_clear_l4w": {
            "ts": 0,
            "agent_id": "",
            "quarantine_event_id": "",
            "envelope_hash": "",
            "prev_hash": "",
            "envelope_path": "",
            "envelope_sha256": "",
            "pub_fingerprint": "",
        },
    }
    if isinstance(drift_quarantine_payload.get("l4w"), dict):
        l4w_payload = dict(drift_quarantine_payload.get("l4w") or {})

    integrity_payload: Dict[str, Any] = {
        "ok": False,
        "slot": "A",
        "enforced": False,
        "degraded": True,
        "manifest_ok": False,
        "mismatch_count": 0,
        "last_mismatch": {},
        "last_verify_ts": 0,
        "last_error": "integrity_unavailable",
        "spec_guard": {
            "tracked_agents": 0,
            "tamper_recent": 0,
            "last_tamper": {},
            "last_trusted_write": {},
        },
        "perf": {
            "cache_ttl_sec": 0,
            "fail_streak": 0,
            "fail_max": 0,
            "mode_forced": "",
            "last_rollback_reason": "",
        },
    }
    if runtime_integrity_verifier is not None:
        try:
            built = runtime_integrity_verifier.build_integrity_status()
            if isinstance(built, dict):
                integrity_payload = built
        except Exception as exc:
            integrity_payload["last_error"] = str(exc)

    network_payload: Dict[str, Any] = {
        "offline": bool(_env_bool("ESTER_OFFLINE", True)),
        "deny_installed": False,
        "slot": _runtime_slot(),
        "mode": "A",
        "allow_cidrs": ["127.0.0.1/32", "::1/128"],
        "allow_hosts": ["localhost"],
        "deny_count": 0,
        "last_deny": {},
    }
    if runtime_network_deny is not None:
        try:
            ns = runtime_network_deny.get_stats()
            allow_rules = dict(ns.get("allow") or {})
            allow_cidrs = list(allow_rules.get("cidrs") or ns.get("allow_cidrs") or [])
            allow_hosts = list(allow_rules.get("hosts") or ns.get("allow_hosts") or [])
            network_payload.update(
                {
                    "deny_installed": bool(ns.get("installed")),
                    "mode": str(ns.get("mode") or network_payload["slot"] or "A"),
                    "allow_cidrs": [str(x) for x in allow_cidrs],
                    "allow_hosts": [str(x) for x in allow_hosts],
                    "deny_count": int(ns.get("deny_count") or 0),
                    "last_deny": dict(ns.get("last_deny") or {}),
                }
            )
        except Exception as exc:
            network_payload["last_deny"] = {"error": str(exc)}

    curiosity_payload: Dict[str, Any] = {
        "ok": False,
        "tickets_open": 0,
        "tickets_stale": 0,
        "tickets_resolved_24h": 0,
        "tickets_total": 0,
        "events_total": 0,
        "last_ticket_ts": 0,
        "last_enqueue_ts": 0,
        "last_resolve_ts": 0,
        "by_event": {},
        "by_status": {},
        "last_ticket_id": "",
        "last_error": "curiosity_unavailable",
        "queue": {
            "size": int(queue_payload.get("size") or 0),
            "last_enqueue_id": str(queue_payload.get("last_enqueue_id") or ""),
        },
        "slot": {
            "raw": _runtime_slot(),
            "effective": _runtime_slot(),
            "slot_b_disabled": False,
            "slot_b_err_streak": 0,
            "slot_b_fail_max": 0,
            "fallback_reason": "",
            "fallback_ts": 0,
        },
    }
    if curiosity_unknown_detector is not None:
        try:
            cs = curiosity_unknown_detector.runtime_snapshot()
            if isinstance(cs, dict):
                curiosity_payload.update(
                    {
                        "ok": bool(cs.get("ok")),
                        "tickets_total": int(cs.get("tickets_total") or 0),
                        "tickets_open": int(cs.get("tickets_open") or 0),
                        "tickets_stale": int(cs.get("tickets_stale") or 0),
                        "tickets_resolved_24h": int(cs.get("tickets_resolved_24h") or 0),
                        "events_total": int(cs.get("events_total") or 0),
                        "by_event": dict(cs.get("by_event") or {}),
                        "by_status": dict(cs.get("by_status") or {}),
                        "last_ticket_id": str(cs.get("last_ticket_id") or ""),
                        "last_ticket_ts": int(cs.get("last_ticket_ts") or 0),
                        "last_enqueue_ts": int(cs.get("last_enqueue_ts") or 0),
                        "last_resolve_ts": int(cs.get("last_resolve_ts") or 0),
                        "last_error": str(cs.get("last_error") or ""),
                    }
                )
        except Exception as exc:
            curiosity_payload["last_error"] = str(exc)
    if curiosity_executor is not None:
        try:
            cst = curiosity_executor.runtime_state()
            if isinstance(cst, dict):
                curiosity_payload["slot"] = {
                    "raw": str(cst.get("slot_raw") or _runtime_slot()),
                    "effective": str(cst.get("slot_effective") or _runtime_slot()),
                    "slot_b_disabled": bool(cst.get("slot_b_disabled")),
                    "slot_b_err_streak": int(cst.get("slot_b_err_streak") or 0),
                    "slot_b_fail_max": int(cst.get("slot_b_fail_max") or 0),
                    "fallback_reason": str(cst.get("slot_b_last_fallback_reason") or ""),
                    "fallback_ts": int(cst.get("slot_b_last_fallback_ts") or 0),
                }
        except Exception as exc:
            curiosity_payload["slot"]["fallback_reason"] = str(exc)

    return {
        "ok": True,
        "memory_ready": bool(readiness.get("memory_ready")),
        "degraded_memory_mode": bool(readiness.get("degraded_memory_mode")),
        "memory_paths": readiness.get("memory_paths"),
        "dreams": dreams,
        "initiatives": initiatives,
        "agents": agents_payload,
        "proactivity": proactivity_payload,
        "queue": queue_payload,
        "outbox": outbox_payload,
        "comm_window": comm_payload,
        "oracle_window": oracle_payload,
        "oracle_requests": oracle_requests_payload,
        "oracle_calls": oracle_calls_payload,
        "capability_audit": capability_audit_payload,
        "capability_drift": capability_drift_payload,
        "drift_quarantine": drift_quarantine_payload,
        "l4w": l4w_payload,
        "integrity": integrity_payload,
        "network": network_payload,
        "curiosity": curiosity_payload,
        "companion": companion_payload,
        "last_explained_chain_id": last_explained_chain_id,
        "background": background,
    }
