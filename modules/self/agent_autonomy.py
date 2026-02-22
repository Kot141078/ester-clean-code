# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, Optional

from flask import current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_STATUS: Dict[str, Any] = {
    "enabled": False,
    "started": False,
    "thread": None,
    "interval_sec": None,
    "last_tick_ts": None,
    "last_result": None,
}

_LOCK = threading.Lock()

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


def status() -> Dict[str, Any]:
    with _LOCK:
        return dict(_STATUS)


def tick_once(app, reason: str = "manual") -> Dict[str, Any]:
    """
    One autonomy tick:
      - ensure default manifest exists (in memory)
      - run a lightweight health "need" via suite ops agent
    """
    from routes.mvp_agents_manifest_routes import ensure_default_active
    ensure_default_active()

    # Call suite run internally (no external HTTP)
    tc = app.test_client()
    payload = {"id": "est.ops.health_mvp.v1", "input": {"reason": reason, "check": "basic"}}
    resp = tc.post(
        "/mvp/agents/suite/run",
        data=json.dumps(payload),
        content_type="application/json; charset=utf-8",
    )
    try:
        res = resp.get_json()
    except Exception:
        res = {"ok": False, "error": "no_json"}

    out = {
        "ok": True,
        "reason": reason,
        "suite_call": res,
    }
    with _LOCK:
        _STATUS["last_tick_ts"] = int(time.time())
        _STATUS["last_result"] = out
    return out


def _loop(app, interval: int):
    while True:
        try:
            with app.app_context():
                out = tick_once(app, reason="background")
                try:
                    ok = bool(out.get("ok")) if isinstance(out, dict) else False
                    _mirror_background_event(
                        f"[AUTONOMY_TICK] ok={int(ok)}",
                        "agent_autonomy",
                        "tick",
                    )
                except Exception:
                    pass
        except Exception as e:
            try:
                current_app.logger.warning(f"[autonomy] tick failed: {e}")
            except Exception:
                pass
            try:
                _mirror_background_event(
                    f"[AUTONOMY_TICK_ERROR] {e}",
                    "agent_autonomy",
                    "tick_error",
                )
            except Exception:
                pass
            with _LOCK:
                _STATUS["last_tick_ts"] = int(time.time())
                _STATUS["last_result"] = {"ok": False, "error": str(e)}
        time.sleep(max(5, interval))


def init_app(app):
    enabled = os.getenv("ESTER_AUTONOMY_ENABLE", "0") == "1"
    interval = int(os.getenv("ESTER_AUTONOMY_INTERVAL_SEC", "60") or "60")

    with _LOCK:
        _STATUS["enabled"] = bool(enabled)
        _STATUS["interval_sec"] = interval

    if not enabled:
        return True

    # prevent double-start (reloader)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        pass

    if app.config.get("ESTER_AUTONOMY_STARTED"):
        return True

    t = threading.Thread(target=_loop, args=(app, interval), daemon=True, name="ester-autonomy")
    t.start()
    app.config["ESTER_AUTONOMY_STARTED"] = True
    with _LOCK:
        _STATUS["started"] = True
        _STATUS["thread"] = "ester-autonomy"
    app.logger.info(f"[autonomy] started (interval={interval}s)")
    try:
        _mirror_background_event(
            f"[AUTONOMY_START] interval={interval}",
            "agent_autonomy",
            "start",
        )
    except Exception:
        pass
    return True