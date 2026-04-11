# <repo-root>\routes\root_fallback.py
# Polnyy fayl

from flask import Blueprint, Response, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("root_fallback", __name__)

_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Ester - bezopasnaya startovaya</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root { --fg:#111; --muted:#666; --link:#0645ad; --br:#e5e5e5; --bg:#fff; }
    * { box-sizing: border-box; }
    body { margin:24px; font:14px/1.5 system-ui, Segoe UI, Roboto, Arial, sans-serif; color:var(--fg); background:var(--bg); }
    .wrap { max-width:1080px; margin-inline:auto; }
    .card { border:1px solid var(--br); border-radius:14px; padding:18px; margin-bottom:16px; }
    h1 { margin:0 0 8px 0; font-size:22px; }
    h2 { margin:16px 0 8px 0; font-size:16px; }
    a { color:var(--link); text-decoration:none; }
    a:hover { text-decoration:underline; }
    .grid { display:grid; grid-template-columns: repeat(auto-fit,minmax(240px,1fr)); gap:12px; }
    .muted { color:var(--muted); }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Ester - bezopasnaya startovaya</h1>
      <p class="muted">Stranitsa otdaetsya modulem <span class="mono">routes/root_fallback.py</span> dlya perekhvata <span class="mono">/</span>, chtoby isklyuchit HTTP 500.</p>
      <p>Diagnostika: <a href="/_safe/ping">/_safe/ping</a> ·
         <a href="/_safe/routes">/_safe/routes</a> ·
         <a href="/_safe/healthz">/_safe/healthz</a> ·
         <a href="/_safe/readyz">/_safe/readyz</a> ·
         <a href="/_safe/portal">/_safe/portal</a></p>
    </div>

    <div class="grid">
      <div class="card">
        <h2>Navigatsiya</h2>
        <ul>
          <li><a href="/routes_index.html">/routes_index.html</a></li>
          <li><a href="/ui">/ui</a></li>
          <li><a href="/portal">/portal</a> (if available portal)</li>
        </ul>
      </div>

      <div class="card">
        <h2>Podskazka</h2>
        <p class="muted">Esli osnovnoy portal padaet, ispolzuyte <span class="mono">/_safe/portal</span>.</p>
      </div>
    </div>
  </div>
</body>
</html>"""

@bp.before_app_request
def _serve_root_safely():
    if request.path == "/":
        return Response(_HTML, mimetype="text/html", headers={"Cache-Control": "no-store"})

def register(app):
    app.register_blueprint(bp)