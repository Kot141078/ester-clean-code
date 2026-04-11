# <repo-root>\routes\safe_diag_routes.py
# Polnyy fayl

from flask import Blueprint, Response, current_app, request
import html
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("safe_diag", __name__, url_prefix="/_safe")

@bp.get("/ping")
def ping():
    return Response("pong", mimetype="text/plain")

@bp.get("/healthz")
def healthz():
    return Response("ok", mimetype="text/plain")

@bp.get("/readyz")
def readyz():
    return Response("ready", mimetype="text/plain")

@bp.get("/routes")
def routes():
    rows = []
    for rule in sorted(current_app.url_map.iter_rules(), key=lambda r: r.rule):
        methods = ",".join(sorted(m for m in rule.methods if m in {"GET","POST","PUT","PATCH","DELETE"}))
        rows.append(f"<tr><td><code>{html.escape(rule.rule)}</code></td><td>{html.escape(methods)}</td><td>{html.escape(rule.endpoint)}</td></tr>")
    body = f"""<!doctype html><meta charset="utf-8"><title>/_safe/routes</title>
    <style>body{{font:14px/1.4 system-ui,Segoe UI,Roboto,Arial}}table{{border-collapse:collapse}}
    td,th{{border:1px solid #ddd;padding:6px 8px}}code{{background:#f6f8fa;padding:.1em .3em;border-radius:4px}}</style>
    <h1>Zaregistrirovannye marshruty</h1>
    <table><thead><tr><th>Rule</th><th>Methods</th><th>Endpoint</th></tr></thead>
    <tbody>{''.join(rows)}</tbody></table>"""
    return Response(body, mimetype="text/html")

@bp.get("/env")
def env():
    cfg = dict(current_app.config)
    safe_cfg = {k: v for k, v in cfg.items() if not any(s in k.upper() for s in ("SECRET", "KEY", "TOKEN", "PASS"))}
    lines = ["[config]"] + [f"{k}={safe_cfg[k]}" for k in sorted(safe_cfg)] + ["", "[env]"]
    for k in sorted(os.environ):
        if any(s in k.upper() for s in ("SECRET", "KEY", "TOKEN", "PASS")):
            continue
        lines.append(f"{k}={os.environ[k]}")
    return Response("\n".join(lines), mimetype="text/plain")

@bp.route("/echo", methods=["GET","POST","PUT","PATCH","DELETE"])
def echo():
    info = [
        f"method={request.method}",
        f"path={request.path}",
        f"args={dict(request.args)}",
        f"json={request.get_json(silent=True)}",
        "headers:"
    ] + [f"  {k}: {v}" for k, v in request.headers.items()]
    return Response("\n".join(info), mimetype="text/plain")

def register(app):
    app.register_blueprint(bp)