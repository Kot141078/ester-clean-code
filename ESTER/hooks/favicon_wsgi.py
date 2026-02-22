# Lightweight WSGI hook to serve /favicon.ico with a tiny PNG, avoiding noisy 204s.
# Safe to import multiple times; patching is idempotent.

import base64
from typing import Callable, Iterable, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PNG_BYTES = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAA4AAAAOCAYAAAAfSC3RAAAAHElEQVQoka3MMQEAIAwDsZ/9v8S0hQ0g4h4gI3kJzC8Qb5V4Jwqg9p8JwAAAABJRU5ErkJggg==")

def _favicon_app(environ, start_response):
    headers = [
        ("Content-Type", "image/png"),
        ("Cache-Control", "public, max-age=86400"),
        ("Content-Length", str(len(PNG_BYTES))),
    ]
    start_response("200 OK", headers)
    return [PNG_BYTES]

def _wrap_flask_wsgI_app():
    try:
        from flask import Flask  # type: ignore
    except Exception:
        return

    orig = getattr(Flask, "wsgi_app", None)
    if orig is None:
        return

    # Avoid double-patching
    if getattr(Flask, "_ester_favicon_wrapped", False):
        return

    def wrapped(self, environ, start_response):
        path = environ.get("PATH_INFO") or ""
        if path == "/favicon.ico":
            return _favicon_app(environ, start_response)
        return orig(self, environ, start_response)

    Flask.wsgi_app = wrapped  # type: ignore[attr-defined]
    setattr(Flask, "_ester_favicon_wrapped", True)

def _wrap_dispatcher_call():
    # If a DispatcherMiddleware is used directly, wrap its __call__ too.
    try:
        from werkzeug.middleware.dispatcher import DispatcherMiddleware  # type: ignore
    except Exception:
        return
    orig_call = getattr(DispatcherMiddleware, "__call__", None)
    if orig_call is None:
        return
    if getattr(DispatcherMiddleware, "_ester_favicon_wrapped", False):
        return
    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO") or ""
        if path == "/favicon.ico":
            return _favicon_app(environ, start_response)
        return orig_call(self, environ, start_response)
    DispatcherMiddleware.__call__ = __call__  # type: ignore[method-assign]
    setattr(DispatcherMiddleware, "_ester_favicon_wrapped", True)

def install():
    _wrap_flask_wsgI_app()
    _wrap_dispatcher_call()

# Auto-install on import
install()