# -*- coding: utf-8 -*-
"""HTTP-plagin trassirovki myshleniya Ester.

Invarianty:
- Ne menyaet tela otvetov.
- Ne lomaet suschestvuyuschie marshruty.
- Rabotaet tolko pri vklyuchenii ESTER_THINK_TRACE_AB.
"""
from __future__ import annotations

from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from flask import request, g
except Exception:  # pragma: no cover
    request = None  # type: ignore
    g = None  # type: ignore

try:
    from modules.ester import thinking_trace_adapter as _trace  # type: ignore
except Exception:  # pragma: no cover
    _trace = None  # type: ignore


def _match(path: str) -> bool:
    p = path or ""
    return "/ester/thinking/once" in p


def _extract_json_body() -> Dict[str, Any]:
    if request is None:
        return {}
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def register(app) -> None:  # pragma: no cover
    if request is None or _trace is None or not hasattr(_trace, "is_enabled"):
        return

    @app.before_request
    def _tt_before():
        try:
            if not _trace.is_enabled():
                return
            if not _match(request.path or ""):
                return
            if g is not None:
                setattr(g, "_ester_thinking_trace_payload", _extract_json_body())
        except Exception:
            return

    @app.after_request
    def _tt_after(response):
        try:
            if not _trace.is_enabled():
                return response
            if not _match(request.path or ""):
                return response
            payload = getattr(g, "_ester_thinking_trace_payload", {}) if g is not None else {}
            body: Dict[str, Any] = {}
            try:
                if hasattr(response, "is_json") and response.is_json:
                    body = response.get_json(silent=True) or {}
            except Exception:
                body = {}
            if isinstance(payload, dict) and isinstance(body, dict):
                _trace.record(payload, body)
            return response
        except Exception:
            return response


__all__ = ["register"]