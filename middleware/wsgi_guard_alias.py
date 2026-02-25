
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, sys, io, traceback
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

WSGI_GUARD_AB = os.getenv("ESTER_WSGI_GUARD_AB", "B").upper()

class _WSGIGuard(object):
    """WSGI-midlvar, save ot TypeError: 'NoneType' object is not callable
    (kogda somewhere-to v after_request vernuli None).
    Dlya aliasov/favikonki prinuditelno daet bezopasnyy otvet."""
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "") or ""
        try:
            return self.app(environ, start_response)
        except TypeError as e:
            # A typical case of "response(environ, start_response)" on Nona
            # We give a safe plug, without falling, and log it to data/bringup_after_chain.log
            _log_guard("TypeError", path, e)
            status, body = _safe_status_body(path)
            headers = [("Content-Type", "text/plain; charset=utf-8"),
                       ("X-Ester-WSGI-Guard", "sanitized")]
            start_response(status, headers)
            return [body]
        except Exception as e:
            # For aliases and favicons - does not give 500; for the rest - forward
            if path.startswith("/_alias/") or path.endswith("/favicon.ico") or "favicon" in path:
                _log_guard("Exception", path, e)
                status, body = _safe_status_body(path)
                headers = [("Content-Type", "text/plain; charset=utf-8"),
                           ("X-Ester-WSGI-Guard", "fallback")]
                start_response(status, headers)
                return [body]
            raise

def _safe_status_body(path):
    if "favicon" in path:
        return "204 No Content", b""
    if path.startswith("/_alias/"):
        return "200 OK", b"OK"
    return "204 No Content", b""

def _log_guard(kind, path, exc):
    try:
        os.makedirs("data", exist_ok=True)
        with io.open("data/bringup_after_chain.log", "a", encoding="utf-8") as f:
            f.write(u"[WSGI-GUARD] %s at %s: %s\n" % (kind, path, repr(exc)))
    except Exception:
        pass

def register(app):
    """Connection via auto-register: app.vsgi_app = _VSGIGuard(app.vsgi_app)"""
    if WSGI_GUARD_AB == "B":
        app.wsgi_app = _WSGIGuard(app.wsgi_app)