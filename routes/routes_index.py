# -*- coding: utf-8 -*-
# routes/routes_index.py
"""
routes/routes_index.py — udobnaya HTML-stranitsa so spiskom marshrutov (v dopolnenie k /routes JSON).

Put:
  • GET /routes_index.html — tablitsa vsekh pravil Flask (bez HEAD/OPTIONS), s metodami Re endpoint.

Sovmestimost:
  • Ne konfliktuet s /routes (JSON v app.py). R egistriruetsya cherez register_all.py, esli esche ne podklyuchen.

Zemnoy abzats (inzheneriya):
Eto «lineyka klemm» na raspredelitelnom schite: odnim vzglyadom vidno, chto podklyucheno i gde mozhet byt konflikt.

Mosty:
- Yavnyy (Kibernetika v†" Arkhitektura): povyshaet nablyudaemost — prosche upravlyat sistemoy.
- Skrytyy 1 (Infoteoriya v†" Interfeysy): strukturirovannyy vyvod snizhaet kognitivnuyu nagruzku pri revyu.
- Skrytyy 2 (Anatomiya v†" PO): kak karta sosudov — vidno magistrali Re otvetvleniya.

# c=a+b
"""
from __future__ import annotations

from flask import Blueprint, current_app, render_template_string
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_routes_index = Blueprint("routes_index", __name__)

HTML = """<!doctype html>
<meta charset="utf-8"/>
<title>Marshruty</title>
<style>
body{font:14px/1.5 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;padding:16px;background:#0b0e11;color:#e6eef7}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #243140;padding:6px 8px}
th{background:#121821;text-align:left}
tbody tr:nth-child(odd){background:#0b0f15}
code{color:#9bd}
.badge{display:inline-block;border:1px solid #2a3244;border-radius:999px;padding:2px 8px;margin-right:4px;color:#a1a7b1}
</style>
<h1>Spisok marshrutov</h1>
<table>
<thead><tr><th>Rule</th><th>Methods</th><th>Endpoint</th></tr></thead>
<tbody>
{% for r in routes -%}
<tr>
  <td><code>{{ r.rule }}</code></td>
  <td>
    {% for m in r.methods -%}
      <span class="badge">{{ m }}</span>
    {% endfor -%}
  </td>
  <td><code>{{ r.endpoint }}</code></td>
</tr>
{% endfor -%}
</tbody>
</table>
"""

@bp_routes_index.get("/routes_index.html")
def routes_index_page():
    routes = []
    for r in current_app.url_map.iter_rules():
        methods = sorted([m for m in r.methods if m not in {"HEAD", "OPTIONS"}])
        routes.append({"rule": str(r), "endpoint": r.endpoint, "methods": methods})
    routes.sort(key=lambda x: x["rule"])
    return render_template_string(HTML, routes=routes)



def register(app):
    app.register_blueprint(bp_routes_index)
    return app
