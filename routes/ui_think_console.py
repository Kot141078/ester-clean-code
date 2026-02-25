# -*- coding: utf-8 -*-
"""routes/ui_think_console.py - prostaya HTML-panel upravleniya "dvigatelem mysley".

Mosty:
- Yavnyy (UI ↔ Mysl): start/stop/status/ochered zadach v dva klika.
- Skrytyy #1 (Kibernetika ↔ Ekonomiya): regulirovka nice/max_workers dlya uvazheniya resursov.
- Skrytyy #2 (Anatomiya ↔ PO): kak remote dykhaniya: visible rhythm (queue/status) i mozhno “vdokh/vydokh”.

Zemnoy abzats:
This is “ruchka gaza” Ester. Kogda tebe nuzhen PK - ubiraem gaz (stop). Kogda mozhno - daem kholostoy khod (start).
Knopki “konsolidatsiya pamyati”, “psevdo-indeksatsiya” i “zametka” - dlya bystroy proverki.

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("think_ui", __name__, url_prefix="")

def register(app):
    app.register_blueprint(bp)

@bp.get("/think_ui")
def think_ui_page() -> Response:
    html = """<!doctype html><html lang="en"><meta charset="utf-8">
<title>Ester - Dvigatel mysley</title>
<style>
body{font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;max-width:980px;margin:32px auto;padding:0 14px}
h1{font-size:22px;margin:0 0 8px}
.row{margin:8px 0}
input,button,select{padding:8px 10px;border:1px solid #bbb;border-radius:10px}
button{cursor:pointer;background:#f5f5f5}
.card{border:1px solid #e4e4e4;border-radius:14px;padding:12px;margin:12px 0}
pre{background:#fafafa;border:1px solid #eee;padding:10px;border-radius:8px;white-space:pre-wrap}
small{opacity:.75}
</style>
<h1>Ester - Dvigatel mysley</h1>
<div class="card">
  <div class="row">impl:
    <select id="impl"><option>A</option><option>B</option></select>
     max_workers: <input id="workers" type="number" min="1" max="16" value="2">
     nice_ms: <input id="nice" type="number" min="0" max="1000" value="25">
     <button onclick="cfg()">Primenit</button>
  </div>
  <div class="row">
    <button onclick="start()">Start</button>
    <button onclick="stop()">Stop</button>
    <button onclick="stat()">Status</button>
  </div>
  <pre id="out">-</pre>
</div>

<div class="card">
  <div class="row"><b>Bystrye zadachi</b></div>
  <div class="row">
    <button onclick="task('note',{note:document.getElementById('note').value||'Privet iz UI'})">Zametka</button>
    <input id="note" placeholder="Tekst zametki" style="width:60%">
  </div>
  <div class="row">
    <button onclick="task('consolidate_memory',{})">Konsolidatsiya pamyati</button>
    <button onclick="task('build_index',{strategy:'auto'})">Psevdo-indeksatsiya</button>
  </div>
</div>

<script>
async function j(url,method='GET',body=null){
  const opt={method,headers:{'Content-Type':'application/json'}};
  if(body) opt.body=JSON.stringify(body);
  const r=await fetch(url,opt); let txt=await r.text();
  try{txt=JSON.stringify(JSON.parse(txt),null,2)}catch(e){}
  document.getElementById('out').textContent=txt;
}

function cfg(){ j('/think_boot/config','POST', {
  impl: document.getElementById('impl').value,
  max_workers: parseInt(document.getElementById('workers').value||'2'),
  nice_ms: parseInt(document.getElementById('nice').value||'25')
}); }

function start(){ j('/think_boot/start','POST'); }
function stop(){ j('/think_boot/stop','POST'); }
function stat(){ j('/think_boot/status','GET'); }

function task(kind,extra){ const p=Object.assign({kind},extra||{}); j('/think_boot/task','POST',p); }
</script>
</html>"""
    return Response(html, mimetype="text/html; charset=utf-8")
# c=a+b