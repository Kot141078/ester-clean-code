# -*- coding: utf-8 -*-
"""
routes/admin_index.py - edinyy portal admin-stranits i karta marshrutov.

MOSTY:
- Yavnyy: (UI ↔ Vse moduli) /admin i JSON-karta marshrutov dlya zhivoy navigatsii.
- Skrytyy #1: (Nablyudaemost ↔ Infrastruktura) ispolzuem current_app.url_map dlya svodki.
- Skrytyy #2: (UX ↔ Podderzhka) bystryy poisk po pravilam/endpointam cherez /admin/query.

ZEMNOY ABZATs:
Eto «glavnoe menyu»: odno mesto, gde vidny vse admin-stranitsy i bazovaya svodka.
Nikakikh opasnykh vychisleniy na urovne importa - vse s defoltami i proverkami.

# c=a+b
"""
from __future__ import annotations

import os
from typing import Any, Dict, List
from flask import Blueprint, current_app, jsonify, render_template, render_template_string, request
from jinja2 import TemplateNotFound
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("admin_index", __name__)

def _s(x: Any, default: str = "") -> str:
    v = "" if x is None else str(x)
    return v if v != "None" else default

def _routes_snapshot() -> Dict[str, Any]:
    rules: List[Dict[str, Any]] = []
    admins: List[Dict[str, Any]] = []
    app = current_app  # type: ignore[attr-defined]
    for r in app.url_map.iter_rules():  # type: ignore[attr-defined]
        item = {
            "rule": str(r),
            "endpoint": _s(r.endpoint),
            "methods": sorted([m for m in r.methods or [] if m not in {"HEAD", "OPTIONS"}]),
        }
        rules.append(item)
        if str(r).startswith("/admin"):
            admins.append(item)
    return {
        "ok": True,
        "counts": {"all": len(rules), "admin": len(admins)},
        "admins": sorted(admins, key=lambda x: x["rule"]),
        "routes": sorted(rules, key=lambda x: x["rule"]),
    }


def _pick_portal_template() -> str:
    candidates = [
        "portal.html",
        "portal1.html",
        "portal_mind.html",
        "portal_media.html",
        "portal_video.html",
        "memory_portal.html",
    ]
    for name in candidates:
        try:
            current_app.jinja_env.get_or_select_template(name)  # type: ignore[attr-defined]
            return name
        except TemplateNotFound:
            continue
        except Exception:
            continue
    return "portal.html"

@bp.get("/admin/routes")
def admin_routes():
    return jsonify(_routes_snapshot())

@bp.post("/admin/query")
def admin_query():
    d = request.get_json(force=True, silent=True) or {}
    q = _s(d.get("q")).lower()
    topk = int(d.get("topk", 10) or 10)
    snap = _routes_snapshot()
    pool = snap["routes"]
    if q:
        pool = [r for r in pool if (q in r["rule"].lower()) or (q in (r["endpoint"] or "").lower())]
    return jsonify({"ok": True, "items": pool[:max(1, topk)]})

@bp.get("/admin")
def admin_index_page():
    # ENV svodka - bezopasnye defolty (isklyuchaem None+None)
    info = {
        "env": {
            "APP_NAME": _s(os.getenv("APP_NAME", "Ester")),
            "ENV": _s(os.getenv("ENV", "dev")),
            "LMSTUDIO_BASE_URL": _s(os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")),
            "LMSTUDIO_CHAT_MODEL": _s(os.getenv("LMSTUDIO_CHAT_MODEL", "openai/gpt-oss-20b")),
        },
        "counts": _routes_snapshot()["counts"],
        "portal_url": "/admin/portal",
    }
    try:
        return render_template("admin_index.html", info=info)
    except Exception:
        # Vstroennaya stranitsa - bez vneshnikh zavisimostey
        return render_template_string("""
<!doctype html><html lang="ru"><meta charset="utf-8">
<title>Admin - Ester</title>
<style>
body{font:14px/1.4 system-ui,Segoe UI,Roboto,Arial,sans-serif;margin:24px}
h1{margin:0 0 6px 0} .card{border:1px solid #ddd;border-radius:12px;padding:16px;max-width:1040px}
pre{background:#fafafa;border:1px solid #eee;border-radius:8px;padding:12px;white-space:pre-wrap}
a{color:#06c;text-decoration:none} a:hover{text-decoration:underline}
.small{opacity:.7}
</style>
<div class="card">
  <h1>Ester - Admin</h1>
  <div class="small">ENV: {{info.env.ENV}}; LM: {{info.env.LMSTUDIO_BASE_URL}} / {{info.env.LMSTUDIO_CHAT_MODEL}}</div>
  <p><b>Bystrye ssylki:</b>
    <a href="/admin/portal">Portal</a> ·
    <a href="/admin/ingest">Ingest</a> ·
    <a href="/docs/env">ENV</a> ·
    <a href="/docs/routes">Marshruty</a> ·
    <a href="/ui/thinking">Thinking UI</a> ·
    <a href="/memory/backup/admin">Backups</a> ·
    <a href="/memory/cycle/admin">Memory Cycle</a>
  </p>
  <h3>Karta (/admin/routes)</h3>
  <pre id="routes">(zagruzka...)</pre>
</div>
<script>
async function load(){
  const r = await fetch('/admin/routes'); const j = await r.json();
  document.getElementById('routes').textContent = JSON.stringify(j,null,2);
}
load();
</script>""", info=info)


@bp.get("/admin/portal")
def admin_portal_page():
    template_name = _pick_portal_template()
    return render_template(template_name)

def register(app):
    app.register_blueprint(bp)

# finalnaya stroka
# c=a+b
