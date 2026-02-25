# -*- coding: utf-8 -*-
"""/portal_min — ultra-simple portal bez zavisimostey.
Nuzhen tolko dlya bystroy proverki, what routing zhiv.

Mosty:
- Yavnyy: Flask ↔ HTML.
- Skrytye: Diagnostika↔Ekspluatatsiya (bystrye ssylki /health, /portal), UI↔API (fetch /health).

Zemnoy abzats:
This is kontrolnaya lampa “SET EST”. Esli ona gorit - rozetka rabochaya.

c=a+b"""
from __future__ import annotations
from flask import Blueprint, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("portal_min", __name__)

HTML = """<!doctype html><meta charset="utf-8">
<title>Ester · portal_min</title>
<style>
:root{--bg:#0b1020;--fg:#e5e7eb;--muted:#94a3b8;--border:#1f2937}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,Segoe UI,Roboto,Arial}
.wrap{max-width:900px;margin:28px auto;padding:0 16px}
.card{background:#111827;border:1px solid var(--border);border-radius:12px;padding:16px}
a.btn{display:inline-block;border:1px solid var(--border);background:#0f172a;color:var(--fg);
      padding:8px 10px;border-radius:10px;text-decoration:none;margin-right:8px}
pre{white-space:pre-wrap;background:#0f172a;border:1px solid var(--border);border-radius:10px;padding:10px}
</style>
<div class="wrap">
  <div class="card">
    <h1>Portal (minimalnyy)</h1>
    <p>
      <a class="btn" href="/health" target="_blank" rel="noopener">/health</a>
      <a class="btn" href="/portal" target="_blank" rel="noopener">/portal</a>
      <a class="btn" href="/_where" target="_blank" rel="noopener">/_where</a>
    </p>
    <pre id="out">loading ...</pre>
  </div>
</div>
<script>
(async()=>{
  try{
    const r = await fetch('/health', {headers:{'Accept':'application/json'}, cache:'no-store'});
    document.getElementById('out').textContent = r.ok ? JSON.stringify(await r.json(),null,2)
                                                      : ('HTTP '+r.status+' '+await r.text());
  }catch(e){ document.getElementById('out').textContent='Set nedostupna: '+e; }
})();
</script>"""

@bp.get("/portal_min")
def portal_min():
    return Response(HTML, mimetype="text/html; charset=utf-8")

def register(app):
    if bp.name not in app.blueprints:
        app.register_blueprint(bp)
    return True