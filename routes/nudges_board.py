# -*- coding: utf-8 -*-
"""
routes/nudges_board.py - JSON-metriki i HTML-vidzhet dlya bordy.

MOSTY:
- (Yavnyy) /board/nudges/metrics - JSON-agregaty; /board/nudges/widget - prostaya panel s avtoobnovleniem.
- (Skrytyy #1) Mozhno vstroit <iframe src="/board/nudges/widget"> v suschestvuyuschuyu bordu bez ee pravok.
- (Skrytyy #2) Formaty sovmestimy: te zhe polya metrics(), rasshireny «overdue_due».

ZEMNOY ABZATs:
Legkiy vidzhet daet operatoram momentalnoe ponimanie: skolko «gorit», skolko ushlo, skolko zakrylos.

# c=a+b
"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from nudges.store import board_metrics
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

@router.get("/board/nudges/metrics")
async def nudges_metrics():
    return JSONResponse(board_metrics())

@router.get("/board/nudges/widget", response_class=HTMLResponse)
async def nudges_widget():
    html = """
<!doctype html><html><head><meta charset="utf-8"><title>Nudges Widget</title>
<style>body{font-family:system-ui,Arial;margin:0} .card{padding:12px 16px;border-bottom:1px solid #eee}
h3{margin:8px 0} .row{display:flex;gap:20px} .num{font:700 28px/1.2 sans-serif} .muted{color:#777;font-size:12px}
</style></head><body>
<div class="card"><h3>Nudges · Metriki</h3><div id="ts" class="muted"></div></div>
<div class="card row"><div><div class="num" id="pending_total">-</div><div class="muted">v ocheredi</div></div>
<div><div class="num" id="pending_due">-</div><div class="muted">srochnykh</div></div>
<div><div class="num" id="overdue_due">-</div><div class="muted">prosrochennykh</div></div>
<div><div class="num" id="sent_24h">-</div><div class="muted">otpravleno (24ch)</div></div>
<div><div class="num" id="fail_24h">-</div><div class="muted">sboev (24ch)</div></div></div>
<div class="card"><div class="muted">zakryto (prichiny): <span id="closed"></span></div></div>
<script>
async function tick(){
  try{
    const r = await fetch('/board/nudges/metrics'); const j = await r.json();
    for (const k of ['pending_total','pending_due','overdue_due','sent_24h','fail_24h']){
      const el = document.getElementById(k); if (el) el.textContent = j[k];
    }
    document.getElementById('ts').textContent = 'obnovleno: ' + new Date(j.ts*1000).toLocaleString();
    const closed = j.closed_reasons || {};
    document.getElementById('closed').textContent = Object.entries(closed).map(([k,v])=>k+': '+v).join(', ') || '-';
  }catch(e){}
}
tick(); setInterval(tick, 5000);
</script></body></html>
"""
    return HTMLResponse(html)

def mount_nudges_board(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app