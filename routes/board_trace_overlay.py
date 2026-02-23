# -*- coding: utf-8 -*-
"""
routes/board_trace_overlay.py - HTML-UI dlya vizualizatsii overleya plana (bez vneshnikh zavisimostey).

MOSTY:
- (Yavnyy) /board/overlay.html - vstavte JSON plana (ili poprobuyte podtyanut /board/data), nazhmite «Podsvetit».
- (Skrytyy #1) Stranitsa ispolzuet /synergy/trace/overlay, tak chto logika rascheta edina s API.
- (Skrytyy #2) Myagkaya degradatsiya: esli /board/data net - prosto ruchnoy vvod.

ZEMNOY ABZATs:
Udobnyy «fonarik»: podsvetit, gde kandidat silnee podkhodit i s kem emu budet legche rabotat.

# c=a+b
"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.responses import HTMLResponse
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

_HTML = """
<!doctype html><html><head><meta charset="utf-8"><title>Overlay</title>
<style>
body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:16px;color:#222}
.card{border:1px solid #ddd;border-radius:12px;padding:12px;margin-bottom:12px;box-shadow:0 1px 2px rgba(0,0,0,.05)}
label{display:block;margin:6px 0}
textarea,input{width:100%}
table{border-collapse:collapse;width:100%}
th,td{border-bottom:1px solid #eee;padding:6px 8px;text-align:left}
.badge{display:inline-block;background:#f5f5f5;border:1px solid #eee;border-radius:8px;padding:2px 6px;margin:0 4px 2px 0}
.tag{display:inline-block;border-radius:6px;padding:2px 6px}
.tag.pp{background:rgba(0,180,60,.14);border:1px solid rgba(0,180,60,.35)}
.tag.p{background:rgba(80,200,80,.10);border:1px solid rgba(80,200,80,.28)}
.tag.z{background:rgba(120,120,120,.08);border:1px solid rgba(120,120,120,.22)}
.tag.m{background:rgba(200,80,80,.10);border:1px solid rgba(200,80,80,.28)}
</style></head><body>
<h2>Podsvetka sostava (Overlay)</h2>
<div class="card">
  <div style="display:grid;grid-template-columns:1fr 320px;gap:12px">
    <div>
      <label>Plan (JSON):<br><textarea id="plan" rows="10" placeholder='{"steps":[{"role":"pilot","candidates":[{"agent_id":"pilot-1","score":0.6}]}],"team":["coordinator-7"]}'></textarea></label>
    </div>
    <div>
      <label>Zadacha (opts.):<br><textarea id="task" rows="3" placeholder="nuzhen bystryy nochnoy pilot FPV"></textarea></label>
      <label>Kandidaty (opts., cherez zapyatuyu):<br><input id="cands" placeholder="pilot-1,pilot-2"></label>
      <label>Komanda (opts., cherez zapyatuyu):<br><input id="team" placeholder="coordinator-7"></label>
      <div style="margin:6px 0">
        <button onclick="calc()">Podsvetit</button>
        <button onclick="pull()">Poprobovat /board/data</button>
        <span id="meta"></span>
      </div>
    </div>
  </div>
</div>
<div class="card" id="out">Zdes poyavitsya podsvetka…</div>
<script>
function csv(v){return v.split(',').map(s=>s.trim()).filter(Boolean)}
function tag(x){return x==='++'?'pp':(x==='+'?'p':(x==='-'?'m':'z'))}
async function pull(){
  try{
    const r=await fetch('/board/data'); const d=await r.json();
    document.getElementById('plan').value = JSON.stringify(d, null, 2);
  }catch(e){ alert('Ne udalos zagruzit /board/data'); }
}
async function calc(){
  let plan={}; try{ plan = JSON.parse(document.getElementById('plan').value || '{}'); }catch(e){ alert('Nevernyy JSON plana'); return; }
  const payload = {
    plan,
    task_text: document.getElementById('task').value || '',
    candidates: csv(document.getElementById('cands').value||''),
    team: csv(document.getElementById('team').value||''),
    top_n: 20
  };
  const r = await fetch('/synergy/trace/overlay',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  const d = await r.json(); if(!d.ok){ alert('Oshibka'); return; }
  const ov = d.overlay || {}; const cand = ov.candidates || {};
  const rows = Object.keys(cand).sort().map(k=>{
    const x = cand[k], ch = x.color_hint||'0';
    const badge = ch==='++'?'Ochen podkhodit':(ch==='+'?'Podkhodit':(ch==='-'?'Slaboe sootvetstvie':'Neytralno'));
    const labs = (x.labels||[]).map(l=>'<span class="badge">'+l+'</span>').join(' ');
    const why  = (x.why||[]).join('; ');
    return `<tr><td>${k}</td><td><span class="tag ${tag(ch)}">${badge}</span></td><td>${x.advice_bias}</td><td>${x.synergy_avg}</td><td>${labs}</td><td>${why}</td></tr>`;
  }).join('');
  document.getElementById('meta').innerHTML = 'team_bonus: <b>'+ (ov.team_bonus??0).toFixed(3) + '</b>';
  document.getElementById('out').innerHTML = `
    <table>
      <thead><tr><th>agent_id</th><th>podsvetka</th><th>bias</th><th>synergy</th><th>yarlyki</th><th>obyasnenie</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="6">Net kandidatov</td></tr>'}</tbody>
    </table>`;
}
</script>
</body></html>
"""

@router.get("/board/overlay.html", response_class=HTMLResponse)
async def board_overlay_html():
    return HTMLResponse(_HTML)

def mount_board_trace_overlay(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app