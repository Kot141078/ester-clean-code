# -*- coding: utf-8 -*-
"""
routes/board_channels_routes.py - borda kanalov (JSON + legkiy HTML).

MOSTY:
- (Yavnyy) /board/messaging/stats → JSON; /board/messaging.html → mini-dashbord na fetch() bez vneshnikh zavisimostey.
- (Skrytyy #1) Stranitsa ne trebuet shablonizatorov i CDN - chistyy HTML/JS, bystryy render.
- (Skrytyy #2) Dannye berutsya iz observability.messaging_stats bez novykh zavisimostey.

ZEMNOY ABZATs:
Bystro uvidet: «ne shtormit li» dostavku, ne kopitsya li ochered i chto chasche vsego lomaetsya.

# c=a+b
"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from observability.messaging_stats import collect_messaging_stats
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

@router.get("/board/messaging/stats")
async def board_messaging_stats():
    return JSONResponse(collect_messaging_stats())

_HTML = """
<!doctype html><html><head><meta charset="utf-8"><title>Messaging Board</title>
<style>
body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:16px;color:#222}
.card{border:1px solid #ddd;border-radius:12px;padding:12px;margin-bottom:12px;box-shadow:0 1px 2px rgba(0,0,0,.05)}
h2{margin:0 0 8px 0} table{border-collapse:collapse;width:100%}
th,td{border-bottom:1px solid #eee;padding:6px 8px;text-align:left} .muted{color:#666}
.ok{color:#0a7} .bad{color:#c33}
.kv{display:grid;grid-template-columns:180px 1fr;gap:6px}
</style></head><body>
<h2>Kanaly soobscheniy</h2>
<div id="root" class="card">Zagruzhaem…</div>
<script>
async function load(){
  const r = await fetch('/board/messaging/stats'); const d = await r.json();
  const c = d.channels, q=d.queue, l=d.log;
  function chRow(name, x){
    const rate1 = (x.sent_1h + x.fail_1h) ? Math.round(100*x.sent_1h/(x.sent_1h+x.fail_1h)) : 100;
    const rate24 = (x.sent_24h + x.fail_24h) ? Math.round(100*x.sent_24h/(x.sent_24h+x.fail_24h)) : 100;
    const err = (x.top_errors||[]).map(e=>`${e.code}:${e.count}`).join(', ') || '-';
    return `<tr><td>${name}</td><td>${x.sent_1h}/${x.fail_1h} <span class="${rate1>=95?'ok':'bad'}">(${rate1}%)</span></td>
            <td>${x.sent_24h}/${x.fail_24h} <span class="${rate24>=95?'ok':'bad'}">(${rate24}%)</span></td>
            <td>${err}</td></tr>`;
  }
  document.getElementById('root').innerHTML = `
    <div class="kv">
      <div>Ochered vsego:</div><div><b>${q.pending_total}</b> (k dedlaynu: ${q.pending_due}, prosrocheno: <span class="${q.overdue_due>0?'bad':''}">${q.overdue_due}</span>)</div>
      <div>Sent/Fail za 24ch:</div><div>${l.sent_24h}/${l.fail_24h}</div>
      <div class="muted">ts:</div><div class="muted">${new Date(d.ts*1000).toLocaleString()}</div>
    </div>
    <table style="margin-top:12px">
      <thead><tr><th>Kanal</th><th>1 chas</th><th>24 chasa</th><th>Top oshibok</th></tr></thead>
      <tbody>
        ${chRow('Telegram', c.telegram)}
        ${chRow('WhatsApp', c.whatsapp)}
      </tbody>
    </table>`;
}
load(); setInterval(load, 10000);
</script></body></html>
"""

@router.get("/board/messaging.html", response_class=HTMLResponse)
async def board_messaging_html():
    return HTMLResponse(_HTML)

def mount_board_channels(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app