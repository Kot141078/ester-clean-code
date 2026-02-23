# -*- coding: utf-8 -*-
"""
routes/admin_blueprints.py - karta blyuprintov/routov (JSON + HTML).

MOSTY:
- (Yavnyy) GET /admin/blueprints (JSON) i /admin/blueprints/html (bystryy HTML-prosmotr).
- (Skrytyy #1) Pomogaet lovit konflikty "The name 'ui' is already registered...".
- (Skrytyy #2) Sovmestim s verify_routes_v2 (obschie polya).

ZEMNOY ABZATs:
Panel «skhema schita»: odnim vzglyadom - kakie gruppy marshrutov stoyat i kuda oni vedut.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, render_template_string, current_app as app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("admin_blueprints", __name__, url_prefix="/admin")

def register(app_):
    app_.register_blueprint(bp)

@bp.get("/blueprints")
def get_blueprints():
    bps = []
    for name, b in app.blueprints.items():
        bps.append({"name": name, "import_name": getattr(b, "import_name",""), "url_prefix": getattr(b, "url_prefix","")})
    rules = []
    for r in app.url_map.iter_rules():
        methods = sorted([m for m in r.methods if m not in ("HEAD","OPTIONS")])
        rules.append({"rule": str(r), "endpoint": r.endpoint, "methods": methods})
    return jsonify({"ok": True, "blueprints": bps, "rules": rules})

_HTML = """
<!doctype html><meta charset="utf-8"><title>Blueprints</title>
<style>body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:12px;background:#0b0f14;color:#e5e7eb}
h1{color:#93c5fd} table{border-collapse:collapse;width:100%} td,th{border:1px solid #1f2937;padding:6px}
a{color:#93c5fd;text-decoration:none}</style>
<h1>Blueprints</h1>
<table><tr><th>name</th><th>import</th><th>prefix</th></tr>
{% for name, b in app.blueprints.items() %}
<tr><td>{{ name }}</td><td>{{ b.import_name }}</td><td>{{ b.url_prefix or '' }}</td></tr>
{% endfor %}
</table>
<h1>Rules</h1>
<table><tr><th>rule</th><th>methods</th><th>endpoint</th></tr>
{% for r in app.url_map.iter_rules() %}
  {% set ms = [m for m in r.methods if m not in ('HEAD','OPTIONS')] %}
  <tr><td>{{ r }}</td><td>{{ ','.join(ms) }}</td><td>{{ r.endpoint }}</td></tr>
{% endfor %}
</table>
"""
@bp.get("/blueprints/html")
def blueprints_html():
    return render_template_string(_HTML)
# c=a+b


def register(app):
    app.register_blueprint(bp)
    return app