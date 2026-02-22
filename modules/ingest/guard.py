# -*- coding: utf-8 -*-
"""
Ingest guard: local token-bucket + durable JSON state + fail-closed submit proxy.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError

from modules.ingest.common import persist_dir
from modules.net_guard import allow_network, deny_payload


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or default)
    except Exception:
        return int(default)


def _parse_backoff(value: str) -> List[int]:
    out: List[int] = []
    for p in str(value or "").split(","):
        p = p.strip()
        if not p:
            continue
        try:
            v = int(p)
        except Exception:
            continue
        if v > 0:
            out.append(v)
    return out or [500, 1000, 2000, 5000]


def _db_path() -> str:
    configured = (os.getenv("INGEST_GUARD_DB") or "").strip()
    if configured:
        path = configured
    else:
        path = os.path.join(persist_dir(), "ingest", "guard.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def _defaults() -> Dict[str, Any]:
    return {
        "default_rate": _int_env("INGEST_DEFAULT_RATE", 60),
        "default_burst": _int_env("INGEST_BURST", 120),
        "default_backoff_ms": _parse_backoff(os.getenv("INGEST_BACKOFF_MS", "500,1000,2000,5000")),
    }


_STATE: Dict[str, Any] = {
    "updated": int(time.time()),
    "last_reset": int(time.time()),
    **_defaults(),
    "sources": {},
}


def _load() -> None:
    path = _db_path()
    if not os.path.isfile(path):
        _save()
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            _STATE.update(loaded)
            _STATE.setdefault("sources", {})
            _STATE.setdefault("default_rate", _defaults()["default_rate"])
            _STATE.setdefault("default_burst", _defaults()["default_burst"])
            _STATE.setdefault("default_backoff_ms", _defaults()["default_backoff_ms"])
            _STATE.setdefault("last_reset", int(time.time()))
    except Exception:
        # keep existing in-memory defaults
        pass


def _save() -> None:
    _STATE["updated"] = int(time.time())
    with open(_db_path(), "w", encoding="utf-8") as f:
        json.dump(_STATE, f, ensure_ascii=False, indent=2)


def _now() -> float:
    return time.time()


def _ensure_source(source: str) -> Dict[str, Any]:
    src = str(source or "default")
    defaults = _defaults()
    rec = _STATE["sources"].setdefault(
        src,
        {
            "rate": int(_STATE.get("default_rate", defaults["default_rate"])),
            "burst": int(_STATE.get("default_burst", defaults["default_burst"])),
            "tokens": float(_STATE.get("default_burst", defaults["default_burst"])),
            "last": _now(),
            "ok": 0,
            "err": 0,
            "failures": 0,
            "backoff": list(_STATE.get("default_backoff_ms", defaults["default_backoff_ms"])),
        },
    )
    rec.setdefault("rate", int(_STATE.get("default_rate", defaults["default_rate"])))
    rec.setdefault("burst", int(_STATE.get("default_burst", defaults["default_burst"])))
    rec.setdefault("tokens", float(rec.get("burst", 1)))
    rec.setdefault("last", _now())
    rec.setdefault("ok", 0)
    rec.setdefault("err", 0)
    rec.setdefault("failures", 0)
    rec.setdefault("backoff", list(_STATE.get("default_backoff_ms", defaults["default_backoff_ms"])))
    return rec


def _refill(rec: Dict[str, Any]) -> None:
    rate = max(1.0, float(rec.get("rate", 1)))
    burst = max(1.0, float(rec.get("burst", 1)))
    tokens = float(rec.get("tokens", burst))
    last = float(rec.get("last", _now()))
    elapsed = max(0.0, _now() - last)
    tokens = min(burst, tokens + elapsed * (rate / 60.0))
    rec["tokens"] = tokens
    rec["last"] = _now()


def cron_reset() -> Dict[str, Any]:
    _load()
    reset_hours = max(1, _int_env("CRON_RESET_HOURS", 24))
    now_ts = int(time.time())
    if now_ts - int(_STATE.get("last_reset", now_ts)) >= reset_hours * 3600:
        for rec in _STATE.get("sources", {}).values():
            rec["tokens"] = float(rec.get("burst", _STATE.get("default_burst", 120)))
            rec["ok"] = 0
            rec["err"] = 0
            rec["failures"] = 0
        _STATE["last_reset"] = now_ts
        _save()
    return {"ok": True, "reset_time": int(_STATE.get("last_reset", now_ts))}


def config(source: str, rate_per_min: int, burst: int, backoff: Optional[List[int]] = None) -> Dict[str, Any]:
    _load()
    rec = _ensure_source(source)
    rec["rate"] = max(1, int(rate_per_min))
    rec["burst"] = max(1, int(burst))
    rec["tokens"] = min(float(rec.get("tokens", rec["burst"])), float(rec["burst"]))
    if backoff:
        rec["backoff"] = [int(x) for x in backoff if int(x) > 0]
    _save()
    return {
        "ok": True,
        "source": str(source),
        "rate": int(rec["rate"]),
        "burst": int(rec["burst"]),
        "backoff": list(rec.get("backoff") or _STATE.get("default_backoff_ms", [])),
    }


def get_config() -> Dict[str, Any]:
    _load()
    src_cfg = {}
    for name, rec in (_STATE.get("sources") or {}).items():
        src_cfg[str(name)] = {
            "rate": int(rec.get("rate", _STATE.get("default_rate", 60))),
            "burst": int(rec.get("burst", _STATE.get("default_burst", 120))),
            "backoff": list(rec.get("backoff") or _STATE.get("default_backoff_ms", [])),
        }
    return {
        "ok": True,
        "default_rate": int(_STATE.get("default_rate", 60)),
        "default_burst": int(_STATE.get("default_burst", 120)),
        "default_backoff_ms": list(_STATE.get("default_backoff_ms", [500, 1000, 2000, 5000])),
        "sources": src_cfg,
    }


def set_config(default_rate: Any = None, default_burst: Any = None, sources: Any = None) -> Dict[str, Any]:
    _load()
    if default_rate is not None:
        try:
            _STATE["default_rate"] = max(1, int(default_rate))
        except Exception:
            pass
    if default_burst is not None:
        try:
            _STATE["default_burst"] = max(1, int(default_burst))
        except Exception:
            pass
    if isinstance(sources, dict):
        for source, cfg in sources.items():
            if not isinstance(cfg, dict):
                continue
            config(
                str(source),
                int(cfg.get("rate", _STATE.get("default_rate", 60))),
                int(cfg.get("burst", _STATE.get("default_burst", 120))),
                cfg.get("backoff"),
            )
    _save()
    return get_config()


def penalize(source: str, code: int, multiplier: float = 1.0) -> Dict[str, Any]:
    _load()
    rec = _ensure_source(source)
    _refill(rec)
    penalty = max(1.0, float(multiplier or 1.0))
    # Higher penalties for server/load errors.
    if int(code) in (429, 500, 502, 503, 504):
        penalty *= 2.0
    rec["tokens"] = max(0.0, float(rec.get("tokens", 0.0)) - penalty)
    rec["err"] = int(rec.get("err", 0)) + 1
    rec["failures"] = int(rec.get("failures", 0)) + 1
    _save()
    return {
        "ok": True,
        "source": str(source),
        "code": int(code),
        "tokens": round(float(rec.get("tokens", 0.0)), 3),
        "err": int(rec.get("err", 0)),
        "failures": int(rec.get("failures", 0)),
    }


def check_and_consume(source: str, cost: int = 1) -> Dict[str, Any]:
    _load()
    cron_reset()
    rec = _ensure_source(source)
    _refill(rec)

    cost = max(0, int(cost or 0))
    allowed = float(rec.get("tokens", 0.0)) >= float(cost)
    retry_after = 0

    if allowed:
        rec["tokens"] = float(rec.get("tokens", 0.0)) - float(cost)
        rec["ok"] = int(rec.get("ok", 0)) + 1
    else:
        rec["err"] = int(rec.get("err", 0)) + 1
        rec["failures"] = int(rec.get("failures", 0)) + 1
        rate_per_sec = max(0.001, float(rec.get("rate", 1)) / 60.0)
        need = max(0.0, float(cost) - float(rec.get("tokens", 0.0)))
        retry_after = max(1, int(need / rate_per_sec))

    _save()
    return {
        "ok": True,
        "allowed": bool(allowed),
        "left": round(float(rec.get("tokens", 0.0)), 3),
        "retry_after_sec": int(retry_after),
        "cap": int(rec.get("burst", _STATE.get("default_burst", 120))),
        "refill_per_min": int(rec.get("rate", _STATE.get("default_rate", 60))),
        "ok_count": int(rec.get("ok", 0)),
        "err_count": int(rec.get("err", 0)),
    }


def state(clean_old: bool = False) -> Dict[str, Any]:
    _load()
    if clean_old:
        stale_sec = max(60, _int_env("INGEST_GUARD_STALE_SEC", 7 * 24 * 3600))
        now_ts = _now()
        keep: Dict[str, Any] = {}
        for source, rec in (_STATE.get("sources") or {}).items():
            if now_ts - float(rec.get("last", now_ts)) <= stale_sec:
                keep[str(source)] = rec
        _STATE["sources"] = keep
        _save()
    return {
        "ok": True,
        "sources": _STATE.get("sources", {}),
        "default_rate": int(_STATE.get("default_rate", 60)),
        "default_burst": int(_STATE.get("default_burst", 120)),
        "default_backoff_ms": list(_STATE.get("default_backoff_ms", [500, 1000, 2000, 5000])),
        "last_reset": int(_STATE.get("last_reset", int(time.time()))),
    }


def submit(source: str, payload: Dict[str, Any], cost: int = 1) -> Dict[str, Any]:
    check_res = check_and_consume(source, cost)
    if not check_res.get("allowed"):
        return {
            "ok": False,
            "error": "rate_limited",
            "retry_sec": int(check_res.get("retry_after_sec") or 1),
            "guard": check_res,
        }

    url = (os.getenv("INGEST_SUBMIT_URL") or "http://127.0.0.1:8000/ingest/submit").strip()
    if not allow_network(url):
        return deny_payload(url, target="ingest_submit")

    body = json.dumps(payload or {}).encode("utf-8")
    req = urlrequest.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlrequest.urlopen(req, timeout=20) as resp:  # nosec B310 guarded by allow_network
            raw = resp.read().decode("utf-8", errors="replace")
            code = int(getattr(resp, "status", 200))
    except HTTPError as e:
        penalize(source, int(getattr(e, "code", 500)), multiplier=1.0)
        backoff = (_ensure_source(source).get("backoff") or [1000])[0]
        return {
            "ok": False,
            "error": "submit_failed",
            "code": int(getattr(e, "code", 500)),
            "backoff_ms": int(backoff),
            "detail": str(e),
        }
    except URLError as e:
        penalize(source, 503, multiplier=1.0)
        backoff = (_ensure_source(source).get("backoff") or [1000])[0]
        return {
            "ok": False,
            "error": "submit_failed",
            "code": 503,
            "backoff_ms": int(backoff),
            "detail": str(e),
        }
    except Exception as e:
        penalize(source, 500, multiplier=1.0)
        backoff = (_ensure_source(source).get("backoff") or [1000])[0]
        return {
            "ok": False,
            "error": "submit_failed",
            "code": 500,
            "backoff_ms": int(backoff),
            "detail": str(e),
        }

    if code in (429, 500, 502, 503, 504):
        penalize(source, code, multiplier=1.0)
        backoff = (_ensure_source(source).get("backoff") or [1000])[0]
        return {
            "ok": False,
            "error": "submit_failed",
            "code": code,
            "backoff_ms": int(backoff),
            "detail": f"HTTP {code}",
        }

    try:
        parsed = json.loads(raw) if raw.strip() else {"ok": True}
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return {"ok": True, "raw": raw}


def sync_with_peers() -> Dict[str, Any]:
    # Intentionally local-only in closed_box phase.
    return {"ok": True, "skipped": True, "reason": "offline_only"}


def receive_sync(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Local merge endpoint for future use; no network side effects.
    _load()
    srcs = payload.get("sources") if isinstance(payload, dict) else None
    if isinstance(srcs, dict):
        for source, rec in srcs.items():
            if not isinstance(rec, dict):
                continue
            cur = _ensure_source(str(source))
            cur["tokens"] = max(float(cur.get("tokens", 0.0)), float(rec.get("tokens", 0.0)))
            cur["ok"] = int(cur.get("ok", 0)) + int(rec.get("ok", 0))
            cur["err"] = int(cur.get("err", 0)) + int(rec.get("err", 0))
            cur["failures"] = int(cur.get("failures", 0)) + int(rec.get("failures", 0))
    _save()
    return {"ok": True, "merged_sources": len((srcs or {})) if isinstance(srcs, dict) else 0}


def _bootstrap_state() -> None:
    """Load persisted state on import without breaking module import."""
    try:
        _load()
    except Exception as exc:
        _STATE["boot_error"] = f"{exc.__class__.__name__}: {exc}"
        _STATE.setdefault("sources", {})


_bootstrap_state()
