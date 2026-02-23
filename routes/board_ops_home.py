# -*- coding: utf-8 -*-
"""
routes/board_ops_home.py - «Tsentr upravleniya»: svodka kanalov, ssylki na bordy, tumblery ENV.

MOSTY:
- (Yavnyy) /admin/control.html - edinaya panel operatoru/inzheneru.
- (Skrytyy #1) Podtyagivaet metriki iz observability.messaging_stats i sostoyanie ENV iz /admin/runtime/env.
- (Skrytyy #2) Nikakikh vneshnikh bibliotek - chistyy HTML/JS.

ZEMNOY ABZATs:
Odna stranitsa - i vse klyuchevye mesta pod rukoy: dostavka soobscheniy, roli, sovetnik, overley i nastroyki.

# c=a+b
"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.responses import HTMLResponse
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

_HTML = """
<!doctype html><html><head><meta charset="utf-8"><title>Ester • Tsentr upravleniya</title>
<style>
body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:16px;color:#222}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.card{border:1px solid #ddd;border-radius:12px;padding:12px;box-shadow:0 1px 2px rgba(0,0,0,.05)}
h2{margin:0 0 12px 0} h3{margin:0 0 8px 0}
table{border-collapse:collapse;width:100%} th,td{border-bottom:1px solid #eee;padding:6px 8px;text-align:left}
.btn{padding:6px 10px;border:1px solid #ddd;border-radius:8px;background:#f9f9f9;cursor:pointer}
.bad{color:#c33} .ok{color:#0a7} .muted{color:#666}
a.tile{display:block;border:1px solid #eee;border-radius:10px;padding:10px;text-decoration:none;color:#222;background:linear-gradient(180deg,#fff,#fafafa)}
a.tile:hover{box-shadow:0 1px 6px rgba(0,0,0,.08)}
.kv{display:grid;grid-template-columns:180px 1fr;gap:4px}
</style></head><body>
<h2>Ester • Tsentr upravleniya</h2>
<div class="grid">
  <div class="card">
    <h3>Svodka kanalov</h3>
    <div id="metrics">Zagruzhaem…</div>
    <div style="margin-top:8px">
      <a class="tile" href="/board/messaging.html">Borda kanalov</a>
      <a class="tile" href="/admin/webhooks">Vebkhuki</a>
    </div>
  </div>
  <div class="card">
    <h3>Roli i sinergiya</h3>
    <div class="kv">
      <div>-</div><div><a class="tile" href="/board/roles.html">Roli i affinnost</a></div>
      <div>-</div><div><a class="tile" href="/board/advisor.html">Sovetnik (UI)</a></div>
      <div>-</div><div><a class="tile" href="/board/assignments.html">Podbor sostava (what-if)</a></div>
      <div>-</div><div><a class="tile" href="/board/overlay.html">Podsvetka plana (overlay)</a></div>
    </div>
  </div>
  <div class="card">
    <h3>Email</h3>
    <a class="tile" href="/email/preview.html">Generator pisem</a>
  </div>
  <div class="card">
    <h3>Eksport</h3>
    <div class="kv">
      <div>Outbox (TG/WA):</div><div><a class="tile" href="/export/outbox.csv">Skachat CSV</a></div>
      <div>Mail outbox:</div><div><a class="tile" href="/export/mail_outbox.csv">Skachat CSV</a></div>
      <div>Graf affinnosti:</div><div><a class="tile" href="/export/roles_edges.csv">Skachat CSV</a></div>
    </div>
  </div>
  <div class="card">
    <h3>Parametry (runtime)</h3>
    <div id="env">Zagruzhaem…</div>
  </div>
</div>
<script>
async function loadMetrics(){
  const r = await fetch('/board/messaging/stats'); const d = await r.json();
  const c=d.channels, q=d.queue;
  document.getElementById('metrics').innerHTML = `
    <div class="kv">
      <div>Ochered:</div><div><b>${q.pending_total}</b> (k dedlaynu: ${q.pending_due}, prosrocheno: <span class="${q.overdue_due>0?'bad':''}">${q.overdue_due}</span>)</div>
      <div>Telegram/24ch:</div><div>${c.telegram.sent_24h}/${c.telegram.fail_24h}</div>
      <div>WhatsApp/24ch:</div><div>${c.whatsapp.sent_24h}/${c.whatsapp.fail_24h}</div>
    </div>`;
}
async function loadEnv(){
  const r = await fetch('/admin/runtime/env'); const d = await r.json();
  const rows = (d.entries||[]).map(e=>{
    return `<tr><td>${e.key}</td><td><input id="env_${e.key}" value="${(e.value||'').replaceAll('"','&quot;')}" style="width:100%"></td><td>${e.live?'<span class="ok">live</span>':'<span class="muted">restart</span>'}</td><td>${e.desc||''}</td></tr>`;
  }).join('');
  document.getElementById('env').innerHTML = `
    <table><thead><tr><th>Klyuch</th><th>Znachenie</th><th>Effekt</th><th>Opisanie</th></tr></thead><tbody>${rows}</tbody></table>
    <div style="margin-top:8px"><button class="btn" onclick="saveEnv()">Save</button></div>`;
}
async function saveEnv(){
  const r0 = await fetch('/admin/runtime/env'); const d0 = await r0.json();
  const payload = {};
  (d0.entries||[]).forEach(e=>{
    payload[e.key] = document.getElementById('env_'+e.key).value;
  });
  const r = await fetch('/admin/runtime/env',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  const d = await r.json();
  alert('Sokhraneno. '+(d.changed||[]).length+' parametrov obnovleno.'
        + '\\n'+((d.entries||[]).some(x=>!x.live)?'Chast nastroek vstupit posle restarta.':''));
}
loadMetrics(); setInterval(loadMetrics, 10000);
loadEnv();
</script>
</body></html>
"""

@router.get("/admin/control.html", response_class=HTMLResponse)
async def admin_control_html():
    return HTMLResponse(_HTML)

def mount_board_ops_home(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app