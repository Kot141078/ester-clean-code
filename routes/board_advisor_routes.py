# -*- coding: utf-8 -*-
"""
routes/board_advisor_routes.py - prostaya HTML-stranitsa dlya vizualnogo ispolzovaniya sovetnika naznacheniy.

MOSTY:
- (Yavnyy) /board/advisor.html - UX dlya /synergy/assign/advice (bez vneshnikh zavisimostey).
- (Skrytyy #1) Nikakikh izmeneniy v orkestratore - eto dop. interfeys poverkh imeyuscheysya ruchki.
- (Skrytyy #2) Est polya dlya task_text, candidates, team - pozvolyaet bystro validirovat sinergiyu «na glaz».

ZEMNOY ABZATs:
Bystryy sposob «prikinut» sostav: vvesti zadachu i lyudey - uvidet luchshikh i bonus sygrannosti komandy.

# c=a+b
"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.responses import HTMLResponse
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

_HTML = """
<!doctype html><html><head><meta charset="utf-8"><title>Synergy Advisor</title>
<style>
body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:16px;color:#222}
.card{border:1px solid #ddd;border-radius:12px;padding:12px;margin-bottom:12px;box-shadow:0 1px 2px rgba(0,0,0,.05)}
label{display:block;margin:6px 0}
table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #eee;padding:6px 8px;text-align:left}
.badge{display:inline-block;background:#f5f5f5;border:1px solid #eee;border-radius:8px;padding:2px 6px;margin:0 4px 2px 0}
</style></head><body>
<h2>Sovetnik naznacheniy</h2>
<div class="card">
  <label>Opisanie zadachi:<br><textarea id="task" rows="3" style="width:100%" placeholder="nuzhen bystryy nochnoy pilot dlya FPV..."></textarea></label>
  <label>Kandidaty (cherez zapyatuyu):<br><input id="cands" style="width:100%" placeholder="pilot-1,pilot-2,pilot-3"></label>
  <label>V komande uzhe (neobyazatelno):<br><input id="team" style="width:100%" placeholder="coordinator-7"></label>
  <button onclick="run()">Podobrat</button>
  <span id="meta"></span>
</div>
<div id="root" class="card">Zdes poyavyatsya rekomendatsii…</div>
<script>
async function run(){
  const task = document.getElementById('task').value;
  const cands = document.getElementById('cands').value.split(',').map(s=>s.trim()).filter(Boolean);
  const team = document.getElementById('team').value.split(',').map(s=>s.trim()).filter(Boolean);
  const payload = {task_text: task, candidates: cands, team: team, top_n: Math.max(1, cands.length || 5)};
  const r = await fetch('/synergy/assign/advice', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  const d = await r.json();
  document.getElementById('meta').innerHTML = 'team_bonus: <b>'+ (d.team_bonus ?? 0).toFixed(3) + '</b>';
  const rows = (d.advice||[]).map(x=>`<tr><td>${x.agent_id}</td><td>${x.score}</td><td>${x.normalized}</td><td>${(x.labels||[]).map(l=>'<span class="badge">'+l+'</span>').join(' ')}</td><td>${(x.why||[]).join('; ')}</td></tr>`).join('');
  document.getElementById('root').innerHTML = `<table><thead><tr><th>agent_id</th><th>score</th><th>norm</th><th>yarlyki</th><th>obyasnenie</th></tr></thead><tbody>${rows}</tbody></table>`;
}
</script>
</body></html>
"""

@router.get("/board/advisor.html", response_class=HTMLResponse)
async def board_advisor_html():
    return HTMLResponse(_HTML)

def mount_board_advisor(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app