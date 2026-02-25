# -*- coding: utf-8 -*-
"""WSGI-guard s rezhimami otveta i endpointami otladki.

Mosty:
- Yavnyy: WSGI ↔ HTTP - oshibki ne maskiruem 204, vozvraschaem 500 s telom.
- Skrytyy #1: Otladka ↔ Routing — /_debug/last_error i /_where.
- Skrytyy #2: Bezopasnost ↔ Logi — redaktiruem potentsialnye sekrety v treysakh.

Zemnoy abzats (inzheneriya):
Kak zamenit “molchalivyy” avtomat v schite na normalnyy: pri KZ on ne prosto
obestochivaet liniyu (204), a zazhigaet indicator (500 + tekst) i pishet v zhurnal.

c=a+b"""
from __future__ import annotations
import os, sys, json, traceback, re
from datetime import datetime
from typing import Callable, Any, Iterable
from flask import Blueprint, jsonify, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("_wsgi_guard_fix", __name__)
_LAST = {"ts": None, "exc": None, "path": None}

_SECRET_RE = re.compile(r"(Authorization:\s*Bearer\s+)[A-Za-z0-9\-\._]+", re.I)

def _redact(text: str) -> str:
    if not isinstance(text, str):
        return text
    return _SECRET_RE.sub(r"\1***", text)

def _make_guard(original_wsgi: Callable[[Any, Any], Iterable[bytes]]) -> Callable[[Any, Any], Iterable[bytes]]:
    mode = os.getenv("ESTER_WSGI_MODE", "dev").lower()  # dev|json|plain|silent
    def guarded_wsgi(environ, start_response):
        try:
            return original_wsgi(environ, start_response)
        except Exception:
            # will save the last stack
            _LAST["ts"] = datetime.utcnow().isoformat()+"Z"
            _LAST["path"] = environ.get("PATH_INFO")
            _LAST["exc"] = traceback.format_exc()
            # vyvesti v stderr (no bez sekretov)
            print(_redact(_LAST["exc"]), file=sys.stderr, flush=True)

            if mode == "silent":
                # if you really need to be silent - but NOT 204, but 500 without a body
                start_response("500 INTERNAL SERVER ERROR", [("Content-Type","text/plain; charset=utf-8")])
                return [b""]

            if mode == "json":
                body = json.dumps({"ok": False, "error": "internal", "trace": _redact(_LAST["exc"])}, ensure_ascii=False).encode("utf-8")
                headers = [("Content-Type","application/json; charset=utf-8")]
                start_response("500 INTERNAL SERVER ERROR", headers)
                return [body]

            if mode == "plain":
                body = _redact(_LAST["exc"]).encode("utf-8")
                headers = [("Content-Type","text/plain; charset=utf-8")]
                start_response("500 INTERNAL SERVER ERROR", headers)
                return [body]

            # dev (default): minimal HTML page
            html = f"""<!doctype html><meta charset="utf-8">
<title>HTTP 500 · Ester</title>
<style>body{{font:14px/1.45 system-ui,Segoe UI,Roboto,Arial;margin:0;background:#0b1020;color:#e5e7eb}}
.wrap{{max-width:980px;margin:24px auto;padding:0 16px}}
pre{{white-space:pre-wrap;background:#111827;border:1px solid #1f2937;border-radius:10px;padding:12px;overflow:auto}}
a{{color:#60a5fa}}</style>
<div class="wrap">
  <h1>Vnutrennyaya oshibka (500)</h1>
  <p>Marshrut: <b>{_LAST["path"]}</b></p>
  <p>Smotri stek nizhe (sekrety vyrezany), libo <a href="/_debug/last_error?format=txt" target="_blank" rel="noopener">/ _debug / last_error</a></p>
  <pre>{_redact(_LAST["exc"])}</pre>
</div>"""
            start_response("500 INTERNAL SERVER ERROR", [("Content-Type","text/html; charset=utf-8")])
            return [html.encode("utf-8")]
    return guarded_wsgi

@bp.get("/_debug/last_error")
def last_error():
    """Vernut posledniy stek (txt|json)."""
    fmt = (current_app.request_class.environ.get("QUERY_STRING") or "").lower()
    if "format=txt" in fmt:
        txt = f'[{_LAST.get("ts")}] {_LAST.get("path")}\n\n{_redact(_LAST.get("exc") or "")}'
        return current_app.response_class(txt, mimetype="text/plain; charset=utf-8")
    return jsonify(ok=True, **_LAST)

@bp.get("/_where")
def where():
    """Show the actual application configuration and list of routes."""
    app_mod = sys.modules.get("__main__")
    app_file = getattr(app_mod, "__file__", None)
    rules = sorted(r.rule for r in current_app.url_map.iter_rules())
    return jsonify(
        ok=True,
        cwd=os.getcwd(),
        app_file=app_file,
        app_root=current_app.root_path,
        template_folder=current_app.template_folder,
        static_folder=current_app.static_folder,
        routes=rules,
        have_portal=("/portal" in rules or "/portal/" in rules),
    )

def register(app):
    """Replace vsgi_app, if not already replaced."""
    if getattr(app, "_ester_guard_patched", False) is False:
        original = app.wsgi_app
        app.wsgi_app = _make_guard(original)
        app._ester_guard_patched = True
    if bp.name not in app.blueprints:
        app.register_blueprint(bp)
    return True