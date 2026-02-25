# -*- coding: utf-8 -*-
"""routes/board_assignments_routes.py - legkaya "what-if" borda: kandidaty, komanda, reyting i poparnaya sygrannost.

MOSTY:
- (Yavnyy) /board/assignments.html - UI, ispolzuyuschiy /synergy/trace/extras dlya raschetov.
- (Skrytyy #1) Vizualiziruet pairwise sygrannost (tablitsa/teplovaya mini-setka) bez vneshnikh bibliotek.
- (Skrytyy #2) Ne trebuet izmeneniy bordy roley - eto otdelnaya stranitsa dlya interaktivnoy prikidki sostava.

ZEMNOY ABZATs:
Za minutu mozhno “poschupat” komandu: kto luchshe podkhodit po profilyu i naskolko lyudi priterty drug k drugu.

# c=a+b"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.responses import HTMLResponse
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Assignments What-If</title>
<style>
body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:16px;color:#222}
.card{border:1px solid #ddd;border-radius:12px;padding:12px;margin-bottom:12px;box-shadow:0 1px 2px rgba(0,0,0,.05)}
label{display:block;margin:6px 0} table{border-collapse:collapse;width:100%}
th,td{border-bottom:1px solid #eee;padding:6px 8px;text-align:left} .badge{display:inline-block;background:#f5f5f5;border:1px solid #eee;border-radius:8px;padding:2px 6px;margin:0 4px 2px 0}
.cell{padding:4px 6px;border-radius:6px;display:inline-block;min-width:40px;text-align:center}
</style></head><body>
<h2>Podbor sostava (what-if)</h2>
<div class="card">
  <label>Description zadachi:<br><textarea id="task" rows="2" style="width:100%" placeholder="nuzhen bystryy nochnoy pilot FPV..."></textarea></label>
  <label>Kandidaty (cherez zapyatuyu):<br><input id="cands" style="width:100%" placeholder="pilot-1,pilot-2,pilot-3"></label>
  <label>V komande uzhe (cherez zapyatuyu):<br><input id="team" style="width:100%" placeholder="coordinator-7,observer-2"></label>
  <button onclick="run()">Rasschitat</button> <span id="meta"></span>
</div>
<div class="card" id="rank">Zdes poyavitsya reyting kandidatov…</div>
<div class="card" id="grid">Zdes poyavitsya sygrannost...</div>
<script>
function csv(id){return document.getElementById(id).value.split(',').map(s=>s.trim()).filter(Boolean)}
function heat(x){ // x in [0..1]
  const v=Math.max(0,Math.min(1,Number(x)||0));
  const g = Math.round(255*(1-v));
  const r = Math.round(255*(v));
  return 'background:rgba('+r+','+g+',80,0.15);border:1px solid rgba('+r+','+g+',80,0.35);';
}
async function run(){
  const payload = {task_text: document.getElementById('task').value, candidates: csv('cands'), team: csv('team'), top_n: Math.max(1, csv('cands').length||5)};
  const r = await fetch('/synergy/trace/extras', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  const d = await r.json(); if(!d.ok){alert('Oshibka');return}
  document.getElementById('meta').innerHTML = 'team_bonus: <b>'+ (d.team_bonus??0).toFixed(3) + '</b>';
  // rating
  const rows = (d.advice||[]).map(x=>`<tr><td>${x.agent_id}</td><td>${x.score}</td><td>${x.normalized}</td><td>${(x.labels||[]).map(l=>'<span class="badge">'+l+'</span>').join(' ')}</td><td>${(x.why||[]).join('; ')}</td></tr>`).join('');
  document.getElementById('rank').innerHTML = `<h3>Reyting</h3><table><thead><tr><th>agent_id</th><th>score</th><th>norm</th><th>yarlyki</th><th>obyasnenie</th></tr></thead><tbody>${rows}</tbody></table>`;
  // sygrannost
  const people = Array.from(new Set([...(payload.candidates||[]), ...(payload.team||[])]));
  let html = '<h3>Poparnaya sygrannost</h3><table><thead><tr><th></th>'+people.map(p=>'<th>'+p+'</th>').join('')+'</tr></thead><tbody>';
  for(let i=0;i<people.length;i++){
    html += '<tr><th>'+people[i]+'</th>';
    for(let j=0;j<people.length;j++){
      if(i===j){ html+='<td>-</td>'; continue; }
      const key = (people[i] < people[j]) ? (people[i]+'__'+people[j]) : (people[j]+'__'+people[i]);
      const v = Number((d.pairwise||{})[key] || 0).toFixed(3);
      html += '<td><span class="cell" style="'+heat(Number(v))+'">'+v+'</span></td>';
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  document.getElementById('grid').innerHTML = html;
}
</script>
</body></html>"""

@router.get("/board/assignments.html", response_class=HTMLResponse)
async def board_assignments_html():
    return HTMLResponse(_HTML)

def mount_board_assignments(app: FastAPI) -> None:
    app.include_router(router)
# c=a+b


def register(app):
    app.include_router(router)
    return app