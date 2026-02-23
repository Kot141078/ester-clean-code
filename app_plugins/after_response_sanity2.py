# -*- coding: utf-8 -*-
"""
WSGI sanity guard that guarantees a callable response and logs the path.
Catches the infamous 'NoneType is not callable' and returns a small 500 text
instead of letting the stack explode in middleware.
AB flag: ESTER_AFTER_SANITY2_AB (A|B), default B = enabled
Log path: data/bringup_verbose.log
"""
from __future__ import annotations
import os, datetime
from typing import Callable, Iterable
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_AB = os.getenv("ESTER_AFTER_SANITY2_AB", "B").upper() or "B"
_LOG = os.path.join(os.getenv("ESTER_DATA_ROOT", "data"), "bringup_verbose.log")

def _log(msg: str) -> None:
    try:
        os.makedirs(os.path.dirname(_LOG), exist_ok=True)
        with open(_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {msg}\n")
    except Exception:
        pass

class _SanityWSGI:
    def __init__(self, inner: Callable):
        self.inner = inner

    def __call__(self, environ, start_response) -> Iterable[bytes]:
        try:
            return self.inner(environ, start_response)
        except TypeError as e:
            if "NoneType" in str(e) and "callable" in str(e):
                path = environ.get("PATH_INFO", "?")
                _log(f"SanityWSGI: intercepted None response at {path}")
                status = "500 Internal Server Error"
                headers = [("Content-Type", "text/plain; charset=utf-8")]
                start_response(status, headers)
                return [f"Internal error (sanitized). Path={path}\n".encode("utf-8")]
            raise

def register(app) -> None:
    # register() API is consistent with other app_plugins.*
    if _AB == "B":
        app.wsgi_app = _SanityWSGI(app.wsgi_app)  # type: ignore[attr-defined]