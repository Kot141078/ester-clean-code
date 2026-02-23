# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
try:
    from flask import request, g
except Exception:  # pragma: no cover
    request = None  # type: ignore
    g = None  # type: ignore
try:
    from modules.thinking import memory_flow_adapter as _mf  # type: ignore
except Exception:  # pragma: no cover
    _mf = None  # type: ignore

def _should_hook_path(path: str) -> bool:
    p = path or ""
    if "/ester/thinking/once" in p:
        return True
    if "/chat" in p or "/api/chat" in p or "/ester/chat" in p:
        return True
    return False

def _extract_prompt_from_request() -> str:
    if request is None:
        return ""
    txt = ""
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    if isinstance(data, dict):
        for key in ("prompt", "q", "query", "input", "text", "message"):
            v = data.get(key)
            if isinstance(v, str) and v.strip():
                txt = v.strip()
                break
    if not txt:
        q = request.args.get("q", "").strip()
        if q:
            txt = q
    if not isinstance(txt, str):
        return ""
    return txt.strip()

def _extract_reply_from_response(response: Any):
    try:
        if hasattr(response, "is_json") and response.is_json:
            body = response.get_json(silent=True) or {}
            if isinstance(body, dict):
                for key in ("reply", "answer", "text", "output", "completion"):
                    v = body.get(key)
                    if isinstance(v, str) and v.strip():
                        return v.strip()
    except Exception:
        return None
    return None

def register(app) -> None:  # pragma: no cover
    if request is None or _mf is None or not hasattr(_mf, "is_enabled"):
        return

    @app.before_request
    def _memory_flow_before():
        try:
            if not _mf.is_enabled():
                return
            path = request.path or ""
            if not _should_hook_path(path):
                return
            prompt = _extract_prompt_from_request()
            if not prompt:
                return
            recall = _mf.safe_recall(prompt)
            if g is not None:
                setattr(g, "ester_memory_flow_recall", recall)
        except Exception as e:
            try:
                if hasattr(_mf, "_rollback"):
                    _mf._rollback(f"before_request_error:{e!r}")  # type: ignore[attr-defined]
            except Exception:
                pass

    @app.after_request
    def _memory_flow_after(response):
        try:
            if not _mf.is_enabled():
                return response
            path = request.path or ""
            if not _should_hook_path(path):
                return response
            prompt = _extract_prompt_from_request()
            reply = _extract_reply_from_response(response)
            recall = getattr(g, "ester_memory_flow_recall", None) if g is not None else None
            _mf.record_dialog(
                prompt,
                reply,
                meta={
                    "path": path,
                    "status": getattr(response, "status_code", None),
                    "has_recall": bool(isinstance(recall, dict) and recall.get("ok")),
                    "recall_src": (recall or {}).get("src") if isinstance(recall, dict) else None,
                },
            )
            try:
                if isinstance(recall, dict) and recall.get("ok"):
                    items = recall.get("items") or []
                    response.headers["X-Ester-Memory-Recall"] = str(len(items))
            except Exception:
                pass
            return response
        except Exception as e:
            try:
                if hasattr(_mf, "_rollback"):
                    _mf._rollback(f"after_request_error:{e!r}")  # type: ignore[attr-defined]
            except Exception:
                pass
            return response

__all__ = ["register"]