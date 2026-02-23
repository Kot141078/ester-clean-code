
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, sys, io, traceback
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

WSGI_GUARD_AB = os.getenv("ESTER_WSGI_GUARD_AB", "B").upper()

class _WSGIGuard(object):
    """
    WSGI-midlvar, spasaet ot TypeError: 'NoneType' object is not callable
    (kogda gde-to v after_request vernuli None).
    Dlya aliasov/favikonki prinuditelno daet bezopasnyy otvet.
    """
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "") or ""
        try:
            return self.app(environ, start_response)
        except TypeError as e:
            # Tipichnyy sluchay "response(environ, start_response)" na None
            # Otdaem bezopasnuyu zaglushku, bez padeniya, i logiruem v data/bringup_after_chain.log
            _log_guard("TypeError", path, e)
            status, body = _safe_status_body(path)
            headers = [("Content-Type", "text/plain; charset=utf-8"),
                       ("X-Ester-WSGI-Guard", "sanitized")]
            start_response(status, headers)
            return [body]
        except Exception as e:
            # Dlya aliasov i favikonki — ne daem 500; dlya ostalnogo — probrasyvaem
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
    """
    Podklyuchenie cherez auto-register: app.wsgi_app = _WSGIGuard(app.wsgi_app)
    """
    if WSGI_GUARD_AB == "B":
        app.wsgi_app = _WSGIGuard(app.wsgi_app)