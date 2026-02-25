# -*- coding: utf-8 -*-
"""routes/capmap_routes.py - REST/HTML: /self/capmap (json + html)

Mosty:
- Yavnyy: (Veb ↔ Self) edinaya tochka obzora vozmozhnostey.
- Skrytyy #1: (Profile ↔ Trassirovka) snimok fiksiruetsya.
- Skrytyy #2: (Planning ↔ Volya) opora dlya resheniy i obyasnimosti.

Zemnoy abzats:
Otkryli stranitsu - i srazu vidno, what dostupno seychas: knopki, route, peremennye, artefakty.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, current_app, Response
import html, json, time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("capmap_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.self.capmap import build as _build  # type: ignore
except Exception:
    _build=None  # type: ignore

@bp.route("/self/capmap", methods=["GET"])
def api_json():
    if _build is None: return jsonify({"ok": False, "error":"capmap_unavailable"}), 500
    return jsonify(_build(current_app))

@bp.route("/self/capmap/html", methods=["GET"])
def api_html():
    if _build is None: return Response("<h1>capmap_unavailable</h1>", mimetype="text/html; charset=utf-8"), 500
    data=_build(current_app)
    if not data.get("ok"): return Response("<h1>capmap_error</h1>", mimetype="text/html; charset=utf-8"), 500
    cm=data["capmap"]
    rows=""
    for r in cm["routes"]:
        rows+=f"<tr><td>{html.escape(','.join(r['methods']))}</td><td>{html.escape(r['rule'])}</td><td class='muted'>{html.escape(r['endpoint'])}</td></tr>"
    acts=""
    for a in cm["actions"]:
        acts+=f"<tr><td>{html.escape(a['name'])}</td><td class='muted'>{html.escape(json.dumps(a.get('inputs',{}), ensure_ascii=False))}</td><td>{a.get('weight',1)}</td></tr>"
    env=""
    for k,v in sorted(cm["env"].items()):
        env+=f"<tr><td>{html.escape(k)}</td><td>{html.escape(v)}</td></tr>"
    head="""<!doctype html><meta charset="utf-8"><title>Ester CapMap</title>
<style>
body{font-family:system-ui;margin:0}
header{padding:14px 20px;background:#111;color:#fff}
.wrap{padding:16px}
h2{margin-top:24px}
table{border-collapse:collapse;width:100%}
td,th{border:1px solid #ddd;padding:6px}
.muted{color:#666;font-size:12px}
</style>"""
    body=f"<header><h1>CapMap - {time.strftime('%Y-%m-%d %H:%M:%S')}</h1></header><div class='wrap'>"
    body+=f"<h2>Routes ({len(cm['routes'])})</h2><table><tr><th>Method</th><th>Rule</th><th>Endpoint</th></tr>{rows or '<tr><td colspan=3>empty</td></tr>'}</table>"
    body+=f"<h2>Actions ({len(cm['actions'])})</h2><table><tr><th>Name</th><th>Inputs</th><th>W</th></tr>{acts or '<tr><td colspan=3>empty</td></tr>'}</table>"
    body+=f"<h2>ENV ({len(cm['env'])})</h2><table><tr><th>Key</th><th>Value</th></tr>{env or '<tr><td colspan=2>empty</td></tr>'}</table>"
    body+=f"<h2>Artifacts</h2><pre>{html.escape(json.dumps(cm['artifacts'], ensure_ascii=False, indent=2))}</pre>"
    body+="</div>"
    return Response(head+body, mimetype="text/html; charset=utf-8")
# c=a+b