# -*- coding: utf-8 -*-
"""
modules/gta/copilot.py

Runtime bridge between external GTA telemetry and Ester's live contour.
Design goals:
- No hard dependency on game SDK inside Python side.
- Accept raw telemetry snapshots over HTTP and normalize them.
- Ask Ester (ester_arbitrage) for tactical copilot advice.
- Persist last state/advice for UI and crash-safe diagnostics.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
import zlib
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _root_dir() -> Path:
    # modules/gta/copilot.py -> modules/gta -> modules -> project root
    return Path(__file__).resolve().parents[2]


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except Exception:
        return int(default)


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return float(default)


def _safe_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v or "").strip().lower()
    if not s:
        return bool(default)
    return s in ("1", "true", "yes", "on", "y")


def _stable_chat_id(sid: str) -> int:
    raw = str(sid or "gta-v").strip() or "gta-v"
    if raw.lstrip("-").isdigit():
        try:
            return int(raw)
        except Exception:
            pass
    return int(910000000 + (zlib.adler32(raw.encode("utf-8")) % 100000000))


def _default_state_path() -> Path:
    raw = (os.getenv("GTA_COPILOT_STATE_PATH") or "").strip()
    if raw:
        return Path(raw)
    return _root_dir() / "data" / "gta" / "last_state.json"


def _default_log_path() -> Path:
    raw = (os.getenv("GTA_COPILOT_LOG_PATH") or "").strip()
    if raw:
        return Path(raw)
    return _root_dir() / "data" / "gta" / "advice_log.jsonl"


def _ensure_parent(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    _ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _run_coro_sync(coro: Any) -> Any:
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            try:
                loop.close()
            except Exception:
                pass


def _resolve_arbitrage() -> Tuple[Optional[Any], Optional[Any]]:
    main_mod = sys.modules.get("__main__")
    run_mod = sys.modules.get("run_ester_fixed")
    for mod in (main_mod, run_mod):
        if mod is None:
            continue
        arb = getattr(mod, "ester_arbitrage", None)
        if callable(arb):
            return arb, getattr(mod, "_run_coro_sync", None)
    return None, None


def _normalize_state(raw: Dict[str, Any]) -> Dict[str, Any]:
    now_ms = int(time.time() * 1000)
    state = {
        "ts_ms": _safe_int(raw.get("ts_ms") or raw.get("ts") or now_ms, now_ms),
        "wanted": max(0, min(5, _safe_int(raw.get("wanted"), 0))),
        "hp": max(-1, _safe_int(raw.get("hp"), -1)),
        "armor": max(-1, _safe_int(raw.get("armor"), -1)),
        "in_vehicle": _safe_bool(raw.get("in_vehicle"), False),
        "vehicle": str(raw.get("vehicle") or "").strip(),
        "speed_kmh": max(0.0, _safe_float(raw.get("speed_kmh") or raw.get("speed"), 0.0)),
        "zone": str(raw.get("zone") or "").strip(),
        "street": str(raw.get("street") or "").strip(),
        "objective": str(raw.get("objective") or "").strip(),
        "event": str(raw.get("event") or "").strip(),
        "weapon": str(raw.get("weapon") or "").strip(),
        "x": _safe_float(raw.get("x"), 0.0),
        "y": _safe_float(raw.get("y"), 0.0),
        "z": _safe_float(raw.get("z"), 0.0),
    }

    # Keep small optional context for future role prompts.
    extras: Dict[str, Any] = {}
    for k in ("mission", "target", "risk", "plan", "notes"):
        if k in raw and str(raw.get(k) or "").strip():
            extras[k] = str(raw.get(k)).strip()
    if extras:
        state["extras"] = extras
    return state


def _heuristic_advice(state: Dict[str, Any]) -> str:
    wanted = _safe_int(state.get("wanted"), 0)
    hp = _safe_int(state.get("hp"), -1)
    armor = _safe_int(state.get("armor"), -1)
    in_vehicle = _safe_bool(state.get("in_vehicle"), False)
    speed = _safe_float(state.get("speed_kmh"), 0.0)
    objective = str(state.get("objective") or "").strip()
    zone = str(state.get("zone") or "").strip()

    if wanted >= 4:
        return "High wanted level. Leave main roads, switch vehicles in a quiet area, and use side streets."
    if hp > 0 and hp <= 35:
        return "Low health. Break line of sight first, recover HP/armor, then continue the objective."
    if in_vehicle and speed >= 145:
        return "Speed is too high for city traffic. Reduce pace before intersections and keep a safer route."
    if objective:
        return f"Focus objective: {objective}. Move in short steps and pre-plan your exit route."
    if zone:
        return f"Current zone: {zone}. Use cover and avoid open gunfights without position advantage."
    if armor >= 0 and armor < 30:
        return "Armor is low. Refill protection before taking a high-risk action."
    return "Stay on plan, avoid chaos speed, and always keep one fallback escape path."


def _compose_query(state: Dict[str, Any], user_prompt: str = "") -> str:
    prompt = str(user_prompt or "").strip()
    extras = state.get("extras") if isinstance(state.get("extras"), dict) else {}
    lines = [
        "You are a tactical co-pilot in GTA V (single-player).",
        "Do not provide cheating, exploit, or policy-violating advice.",
        "Give a short plan for the next 10-20 seconds in 3-6 sentences.",
        "",
        "[GTA_STATE]",
        f"wanted={state.get('wanted')} hp={state.get('hp')} armor={state.get('armor')}",
        f"in_vehicle={int(_safe_bool(state.get('in_vehicle')))} vehicle={state.get('vehicle') or '-'}",
        f"speed_kmh={state.get('speed_kmh')} zone={state.get('zone') or '-'} street={state.get('street') or '-'}",
        f"weapon={state.get('weapon') or '-'} event={state.get('event') or '-'} objective={state.get('objective') or '-'}",
        f"pos=({state.get('x'):.1f},{state.get('y'):.1f},{state.get('z'):.1f})",
    ]
    if extras:
        lines.append("extras=" + json.dumps(extras, ensure_ascii=False))
    lines.extend(["[/GTA_STATE]", ""])
    if prompt:
        lines.append("Player request:")
        lines.append(prompt)
    else:
        lines.append("If context is unclear, ask exactly one clarifying question at the end.")
    return "\n".join(lines).strip()


_LOCK = threading.Lock()
_RUNTIME: Dict[str, Any] = {
    "ingest_count": 0,
    "advice_count": 0,
    "last_ingest_ts": 0.0,
    "last_advice_ts": 0.0,
    "last_state": {},
    "last_advice": "",
    "last_provider": "",
}


def _snapshot_runtime() -> Dict[str, Any]:
    with _LOCK:
        return {
            "ingest_count": int(_RUNTIME.get("ingest_count", 0)),
            "advice_count": int(_RUNTIME.get("advice_count", 0)),
            "last_ingest_ts": float(_RUNTIME.get("last_ingest_ts", 0.0)),
            "last_advice_ts": float(_RUNTIME.get("last_advice_ts", 0.0)),
            "last_state": dict(_RUNTIME.get("last_state") or {}),
            "last_advice": str(_RUNTIME.get("last_advice") or ""),
            "last_provider": str(_RUNTIME.get("last_provider") or ""),
        }


def _save_runtime() -> None:
    snap = _snapshot_runtime()
    try:
        _write_json(_default_state_path(), snap)
    except Exception:
        pass


def _min_interval_sec() -> float:
    return max(0.2, _safe_float(os.getenv("GTA_COPILOT_MIN_INTERVAL_SEC"), 2.5))


def status(full: bool = False) -> Dict[str, Any]:
    snap = _snapshot_runtime()
    out = {
        "ok": True,
        "ingest_count": snap["ingest_count"],
        "advice_count": snap["advice_count"],
        "last_ingest_ts": snap["last_ingest_ts"],
        "last_advice_ts": snap["last_advice_ts"],
        "last_provider": snap["last_provider"],
        "has_state": bool(snap["last_state"]),
        "has_advice": bool(snap["last_advice"]),
        "min_interval_sec": _min_interval_sec(),
    }
    if full:
        out["last_state"] = snap["last_state"]
        out["last_advice"] = snap["last_advice"]
    return out


def get_last_state() -> Dict[str, Any]:
    return _snapshot_runtime().get("last_state") or {}


def get_last_advice() -> Dict[str, Any]:
    snap = _snapshot_runtime()
    return {
        "text": snap.get("last_advice") or "",
        "provider": snap.get("last_provider") or "",
        "ts": snap.get("last_advice_ts") or 0.0,
    }


def _update_state(state: Dict[str, Any]) -> None:
    now = time.time()
    with _LOCK:
        _RUNTIME["ingest_count"] = int(_RUNTIME.get("ingest_count", 0)) + 1
        _RUNTIME["last_ingest_ts"] = now
        _RUNTIME["last_state"] = dict(state or {})
    _save_runtime()


def ask_advice(
    state: Dict[str, Any],
    *,
    user_prompt: str = "",
    sid: str = "gta-v",
    user_id: str = "gta-player",
    user_name: str = "Owner",
    force: bool = False,
) -> Dict[str, Any]:
    now = time.time()
    snap = _snapshot_runtime()
    if (not force) and (now - float(snap.get("last_advice_ts") or 0.0) < _min_interval_sec()):
        return {
            "ok": True,
            "cached": True,
            "advice": str(snap.get("last_advice") or ""),
            "provider": str(snap.get("last_provider") or "cache"),
            "state": state,
        }

    composed = _compose_query(state, user_prompt=user_prompt)
    provider = ""
    answer = ""

    arb, run_sync = _resolve_arbitrage()
    if callable(arb):
        try:
            coro = arb(
                user_text=composed,
                user_id=str(user_id or "gta-player"),
                user_name=str(user_name or "Owner"),
                chat_id=_stable_chat_id(sid),
                address_as=str(user_name or "Player"),
                tone_context="GTA_CO_PILOT",
                file_context="",
            )
            out = run_sync(coro) if callable(run_sync) else _run_coro_sync(coro)
            answer = str(out or "").strip()
            provider = "hivemind"
        except Exception:
            answer = ""
            provider = ""

    if not answer:
        answer = _heuristic_advice(state)
        provider = provider or "heuristic"

    row = {
        "ts": now,
        "sid": sid,
        "user_id": user_id,
        "user_name": user_name,
        "provider": provider,
        "state": state,
        "prompt": user_prompt,
        "advice": answer,
    }
    try:
        _append_jsonl(_default_log_path(), row)
    except Exception:
        pass

    with _LOCK:
        _RUNTIME["advice_count"] = int(_RUNTIME.get("advice_count", 0)) + 1
        _RUNTIME["last_advice_ts"] = now
        _RUNTIME["last_provider"] = provider
        _RUNTIME["last_advice"] = answer
    _save_runtime()

    return {"ok": True, "cached": False, "advice": answer, "provider": provider, "state": state}


def ingest(
    payload: Dict[str, Any],
    *,
    ask: bool = False,
    user_prompt: str = "",
    sid: str = "gta-v",
    user_id: str = "gta-player",
    user_name: str = "Owner",
    force: bool = False,
) -> Dict[str, Any]:
    raw_state: Dict[str, Any]
    if isinstance(payload.get("state"), dict):
        raw_state = payload.get("state") or {}
    else:
        raw_state = payload

    state = _normalize_state(raw_state or {})
    _update_state(state)

    if ask:
        out = ask_advice(
            state,
            user_prompt=user_prompt,
            sid=sid,
            user_id=user_id,
            user_name=user_name,
            force=force,
        )
        out["ingested"] = True
        return out
    return {"ok": True, "ingested": True, "state": state}

