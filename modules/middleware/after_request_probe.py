# -*- coding: utf-8 -*-
"""
Wrap every after_request / after_app_request to:
- log offender returning None
- normalize to a valid Response so Flask doesn't crash
AB: ESTER_AFTER_PROBE_AB (default: B enabled)
"""
from __future__ import annotations
import os, inspect, types, io
from functools import wraps
from flask import current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_AB = os.getenv("ESTER_AFTER_PROBE_AB", "B").upper()
_LOG_PATH = None

def _log(msg: str):
    try:
        root = os.getenv("ESTER_DATA_ROOT") or "data"
        os.makedirs(root, exist_ok=True)
        path = os.path.join(root, "bringup_after_chain.log")
        global _LOG_PATH
        _LOG_PATH = path
        with open(path, "a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        pass

def _wrap_fn(app, fn, origin: str):
    mod = getattr(fn, "__module__", "?")
    name = getattr(fn, "__name__", str(fn))
    ident = f"{origin}:{mod}.{name}"

    @wraps(fn)
    def _wrapped(resp):
        try:
            out = fn(resp)
        except Exception as e:
            _log(f"[ERR] {ident} raised {e.__class__.__name__}: {e}")
            # keep original resp if possible
            try:
                return resp or app.response_class(b"", 204)
            except Exception:
                return app.response_class(b"", 204)

        if out is None:
            _log(f"[WARN] {ident} returned None; normalized to Response")
            try:
                return resp or app.response_class(b"", 204)
            except Exception:
                return app.response_class(b"", 204)
        return out
    _wrapped.__wrapped_by__ = "after_request_probe"
    return _wrapped

def _already_wrapped(fn) -> bool:
    return getattr(fn, "__wrapped_by__", "") == "after_request_probe"

def register(app):
    if _AB != "B":
        return False

    # 1) Wrap already-registered after_request funcs (global & blueprints)
    for bp, fn_list in list(app.after_request_funcs.items()):
        for i, fn in enumerate(list(fn_list)):
            if not _already_wrapped(fn):
                fn_list[i] = _wrap_fn(app, fn, f"{'app' if bp is None else 'bp:'+bp}")

    # 2) Monkeypatch app.after_request decorator to wrap future registrations
    orig_after_request = app.after_request
    def _after_request_patch(f):
        return orig_after_request(_wrap_fn(app, f, "app/late"))
    app.after_request = _after_request_patch

    # 3) For each existing blueprint – patch its after_app_request decorator
    for bp_name, bp in app.blueprints.items():
        orig_bp_after = getattr(bp, "after_app_request", None)
        if orig_bp_after:
            def _make_patch(bp_orig):
                def _patch(f):
                    return bp_orig(_wrap_fn(app, f, f"bp/late:{bp_name}"))
                return _patch
            bp.after_app_request = _make_patch(orig_bp_after)

    _log("[INFO] after_request probe installed")
    return True