# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, datetime, traceback
from typing import Callable, Iterable, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = os.getenv("ESTER_WSGI_GUARD_AB", "B").upper()

def _log(msg: str) -> None:
    try:
        base = os.getenv("ESTER_DATA_ROOT", "data")
        os.makedirs(base, exist_ok=True)
        p = os.path.join(base, "bringup_after_chain.log")
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass

def _safe_json_start(start_response: Callable, status_code: int, payload: dict) -> Iterable[bytes]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    start_response(f"{status_code} {'OK' if status_code<400 else 'ERROR'}", [
        ("Content-Type", "application/json; charset=utf-8"),
        ("X-Ester-Guard", "wsgi_alias")
    ])
    return [body]

def _safe_empty(start_response: Callable, status: str = "204 No Content") -> Iterable[bytes]:
    start_response(status, [("X-Ester-Guard", "wsgi_alias")])
    return [b""]

def register(app):
    # Veshaem guard tolko kogda yavno vklyuchen B-slot
    if AB != "B":
        _log("wsgi_guard_alias: skipped (AB!=B)")
        return

    original_wsgi = app.wsgi_app

    def guarded_wsgi(environ, start_response):
        path = environ.get("PATH_INFO", "") or ""
        try:
            return original_wsgi(environ, start_response)
        except BaseException as e:
            # Tolko dlya aliasov i favikonki prevraschaem 500 v bezopasnyy otvet
            if path.startswith("/_alias/portal/health"):
                _log(f"guarded catch @ {path}: {e.__class__.__name__}: {e}")
                return _safe_json_start(start_response, 200, {"ok": False, "guard": "alias", "error": str(e)})
            if path.startswith("/_alias/portal"):
                _log(f"guarded catch @ {path}: {e.__class__.__name__}: {e}")
                # Prostaya HTML-zaglushka, chtoby stranitsa ne padala
                html = "<!doctype html><meta charset='utf-8'><title>Ester Portal (guard)</title><h1>Ester Portal</h1><p>Guarded fallback - original handler failed.</p>"
                start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("X-Ester-Guard", "wsgi_alias")])
                return [html.encode("utf-8")]
            if "favicon" in path or path.endswith("/_alias/favicon.ico"):
                _log(f"guarded catch @ {path}: {e.__class__.__name__}: {e}")
                return _safe_empty(start_response, "204 No Content")
            # Inache - obychnoe povedenie
            raise

    app.wsgi_app = guarded_wsgi
    _log("wsgi_guard_alias: installed")