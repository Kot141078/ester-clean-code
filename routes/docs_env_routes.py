# -*- coding: utf-8 -*-
"""routes/docs_env_routes.py - /docs/env (JSON/HTML) - mini-doki po ENV.

Mosty:
- Yavnyy: (UI/Dokumentatsiya ↔ Rantaym) odin adres dlya prosmotra okruzheniya.
- Skrytyy #1: (Survival/Hub ↔ Podskazka) help pri perenose/nastroyke.
- Skrytyy #2: (Cron/Smoke ↔ Diagnostika) polezno vklyuchat v otchety.

Zemnoy abzats:
Nuzhno ponyat “na kakikh nastroykakh zhivem seychas” - otkryvaem /docs/env.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, Response, request
import html
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("docs_env_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.docs.env_index import index as _idx  # type: ignore
except Exception:
    _idx=None  # type: ignore

@bp.route("/docs/env", methods=["GET"])
def api_env():
    if _idx is None: 
        return jsonify({"ok": False, "error":"env_docs_unavailable"}), 500
    data=_idx()
    if (request.args.get("format","json") or "json").lower()=="html":
        rows=[]
        for it in data.get("items",[]):
            rows.append(f"<tr><td><code>{html.escape(it['key'])}</code></td><td>{html.escape(it['type'])}</td><td>{html.escape(it['desc'])}</td><td><code>{html.escape(str(it.get('value','')))}</code></td></tr>")
        html_doc=f"""<!doctype html><meta charset="utf-8"><title>ENV - Ester</title>
<style>body{{font:14px system-ui;background:#0f1115;color:#e5e7eb}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #222;padding:6px}}th{{background:#151922}}</style>
<h1>ENV - Ester</h1><table><thead><tr><th>KEY</th><th>TYPE</th><th>DESC</th><th>VALUE</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>"""
        return Response(html_doc, mimetype="text/html; charset=utf-8")
    return jsonify(data)
# c=a+b