# -*- coding: utf-8 -*-
"""routes/board_roles_routes.py - borda roles: lyudi, yarlyki, vektor; proverka affinnosti.

MOSTY:
- (Yavnyy) /board/roles.json → spisok profiley (obrezannyy vektor), /board/roles.html → view bystraya proverka pary.
- (Skrytyy #1) Affiniti pary berem iz roles.edges.get_edge() (zatukhanie uzhe uchteno).
- (Skrytyy #2) HTML bez zavisimostey - udobno pod air-gap.

ZEMNOY ABZATs:
Kto u nas “veteran”, kto “skorostnik”, kto “peregovorschik”, i kakova “pritertost” mezhdu dvumya - vse pod rukoy.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, FastAPI, Query
from fastapi.responses import JSONResponse, HTMLResponse

from roles.store import list_people
from roles.edges import get_edge
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

def _short_vec(v: Dict[str,float]) -> Dict[str,float]:
    # we will show only the key axes
    keys = ["experience","reaction","calm","comm","lead","tech","law","med","creative","stamina","availability"]
    return {k: round(float(v.get(k,0.0)),2) for k in keys if k in v}

@router.get("/board/roles.json")
async def board_roles_json(limit: int = 300):
    people = list_people(limit=limit)
    out=[]
    for p in people:
        out.append({
            "agent_id": p["agent_id"],
            "labels": p.get("labels",[])[:5],
            "vector": _short_vec(p.get("vector") or {}),
            "samples": int(p.get("samples_cnt") or 0),
            "updated_ts": int(p.get("updated_ts") or 0),
        })
    return JSONResponse({"ok": True, "people": out})

_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Roles Board</title>
<style>
body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:16px;color:#222}
.card{border:1px solid #ddd;border-radius:12px;padding:12px;margin-bottom:12px;box-shadow:0 1px 2px rgba(0,0,0,.05)}
small{color:#666} table{border-collapse:collapse;width:100%} th,td{border-bottom:1px solid #eee;padding:6px 8px;text-align:left}
label{margin-right:8px}
.badge{display:inline-block;background:#f5f5f5;border:1px solid #eee;border-radius:8px;padding:2px 6px;margin:0 4px 2px 0}
</style></head><body>
<h2>Roli i affinnost</h2>
<div class="card">
  <div>
    <label>A: <input id="a" placeholder="agent_id A"></label>
    <label>B: <input id="b" placeholder="agent_id B"></label>
    <button onclick="check()">Check affinnost</button>
    <span id="aff"></span>
  </div>
</div>
<div id="root" class="card">Zagruzhaem…</div>
<script>
async function load(){
  const r=await fetch('/board/roles.json'); const d=await r.json();
  const rows=d.people.map(p=>{
    const lab=(p.labels||[]).map(x=>`<span class="badge">${x}</span>`).join(' ');
    return `<tr><td>${p.agent_id}</td><td>${lab}</td><td><small>${Object.entries(p.vector||{}).map(([k,v])=>k+': '+v).join(', ')}</small></td><td>${p.samples}</td></tr>`;
  }).join('');
  document.getElementById('root').innerHTML = `
    <table><thead><tr><th>agent_id</th><th>yarlyki</th><th>vektor (klyuchi)</th><th>samples</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}
async function check(){
  const a=document.getElementById('a').value.trim(), b=document.getElementById('b').value.trim();
  if(!a||!b){return}
  const r=await fetch('/board/roles/pair_affinity?a='+encodeURIComponent(a)+'&b='+encodeURIComponent(b));
  const d=await r.json();
  document.getElementById('aff').innerHTML='Affinnost: <b>'+d.weight.toFixed(3)+'</b> (updated: '+(d.updated_ts||0)+')';
}
load(); setInterval(load, 15000);
</script></body></html>"""

@router.get("/board/roles.html", response_class=HTMLResponse)
async def board_roles_html():
    return HTMLResponse(_HTML)

@router.get("/board/roles/pair_affinity")
async def board_roles_pair_affinity(a: str = Query(""), b: str = Query("")):
    if not a or not b: 
        return JSONResponse({"ok": False, "error": "a and b required"}, status_code=400)
    e = get_edge(a,b)
    return JSONResponse({"ok": True, **e})

def mount_board_roles(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app