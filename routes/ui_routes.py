# -*- coding: utf-8 -*-
"""routes/ui_routes.py - prostoy UI dlya “samolechki” (panel na /ui/autofix).

New:
  • Spisok modeley (pull iz /autofix/llm/models).
  • Pole vybora modeli (sokhranenie v ENV vnutri protsessa).
  • Mini-chat k LM Studio (cherez /autofix/llm/chat).
  • Puls statusa + GPU s avtoobnovleniem.

Mosty:
  • Yavnyy: (Arkhitektura PO ↔ Ekspluatatsiya) - interfeys upravleniya refleksami.
  • Skrytye: (Infoteoriya ↔ Nablyudaemost), (Anatomiya ↔ Motorika).

Zemnoy abzats:
  Eto "schitok" s tumblerami: vybrat model, progret, otpravit testovyy zapros i videt, shevelitsya li GPU.

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ui_bp = Blueprint("ui", __name__, url_prefix="/ui")
bp = ui_bp

_HTML = """<!doctype html>
<html><head>
<meta charset="utf-8"/>
<title>Ester - Autofix</title>
<style>
 body{font-family:system-ui,Segoe UI,Roboto,Arial;sans-serif;margin:20px;color:#111;}
 h1{margin:0 0 12px 0;}
 .row{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px;}
 .card{border:1px solid #ddd;border-radius:12px;padding:12px;min-width:280px;box-shadow:0 1px 4px rgba(0,0,0,.05);}
 .ok{color:#0a0}
 .fail{color:#a00}
 button{padding:8px 12px;border-radius:10px;border:1px solid #888;background:#fafafa;cursor:pointer}
 input[type=text], select, textarea{padding:8px;border-radius:8px;border:1px solid #aaa;min-width:320px}
 textarea{min-height:90px;width:100%}
 code{background:#f5f5f5;padding:2px 6px;border-radius:6px}
 .mono{font-family:ui-monospace,Consolas,Menlo,monospace;}
 small{color:#555}
</style>
</head><body>
<h1>🩺 Ester - Autofix</h1>

<div class="row">
  <div class="card">
    <b>Status</b>
    <div id="status" class="mono">loading...</div>
    <div><small id="events"></small></div>
  </div>
  <div class="card">
    <b>GPU</b>
    <div id="gpu" class="mono">n/a</div>
  </div>
  <div class="card">
    <b>LM Studio</b>
    <div id="lm" class="mono">n/a</div>
    <div class="row">
      <button onclick="warmup()">Warmup</button>
      <button onclick="ping()">Ping</button>
      <button onclick="discover()">Discover</button>
    </div>
  </div>
</div>

<div class="card">
  <b>Model</b><br/>
  <div class="row">
    <select id="models" onchange="onModelChange()"><option>(zagruzka...)</option></select>
  </div>
  <div class="row">
    <input id="apikey" type="text" placeholder="LMSTUDIO_API_KEY (esli trebuetsya)"/>
  </div>
  <div class="row">
    <button onclick="saveEnv()">Save v protsesse</button>
  </div>
  <small>Baza beretsya iz <code>LMSTUDIO_BASE_URL</code>. Etot UI menyaet ENV tolko <i>v tekuschem protsesse</i>.</small>
</div>

<div class="card" style="max-width:900px">
  <b>Mini-chat</b><br/>
  <div class="row">
    <textarea id="prompt">Skazhi “gotovo” i ostanovis.</textarea>
  </div>
  <div class="row">
    <button onclick="sendChat()">Otpravit</button>
  </div>
  <div id="chatOut" class="mono"></div>
</div>

<script>
const BASE = location.origin;

async function jget(p){ const r = await fetch(BASE+p); return r.json(); }
async function jpost(p,body){ const r = await fetch(BASE+p,{method:'POST',headers:{'Content-Type':'application/json'}, body: JSON.stringify(body||{})}); return r.json(); }

async function refresh(){
  try{
    const s = await jget('/autofix/status');
    const st = s.state || {};
    const n = st.net||{}, l = st.lmstudio||{}, d = st.discover||{};
    let html = '';
    html += `net: <b class="${n.ok?'ok':'fail'}">${n.ok?'ok':'fail'}</b> (${n.detail||''})<br/>`;
    html += `lmstudio: <b class="${l.ok?'ok':'fail'}">${l.ok?'ok':'fail'}</b> (${l.detail||''})<br/>`;
    html += `discover: <b class="${d.ok?'ok':'fail'}">${d.ok?'ok':'fail'}</b> (${d.detail||''})<br/>`;
    html += `cycles: ${st.cycles||0}`;
    document.getElementById('status').innerHTML = html;

    const ev = (st.events||[]).slice(-5).map(e => new Date(e.ts*1000).toLocaleTimeString() + ' ' + e.topic).join(' • ');
    document.getElementById('events').innerText = ev;

    const g = st.gpu || {};
    if(g.ok && g.gpus && g.gpus.length){
      document.getElementById('gpu').innerText = g.gpus.map((r,i)=>`#${i}: util=${r.util}% mem=${r.mem_used}/${r.mem_total} MB`).join('\\n');
    } else {
      document.getElementById('gpu').innerText = g.error ? ('ERR: '+g.error) : 'n/a';
    }

    const m = await jget('/autofix/llm/status');
    document.getElementById('lm').innerText = `base=${m.base||''} model=${m.model||'auto'}`;

    await loadModels();
  }catch(e){
    document.getElementById('status').innerText = 'error '+e;
  }
}

async function loadModels(){
  const m = await jget('/autofix/llm/models');
  const sel = document.getElementById('models'); sel.innerHTML='';
  const arr = (m.models||[]);
  if(!arr.length){ sel.innerHTML='<option>(modeley net)</option>'; return; }
  for(const id of arr){
    const o = document.createElement('option'); o.value=id; o.textContent=id; sel.appendChild(o);
  }
}

async function onModelChange(){
  const model = document.getElementById('models').value;
  if(model){ await jpost('/autofix/apply', {action:'set_env', kv:{LMSTUDIO_MODEL:model}}); }
}

async function warmup(){ const r = await jpost('/autofix/llm/warmup',{}); alert(JSON.stringify(r,null,2)); refresh(); }
async function ping(){ const r = await jpost('/autofix/ping',{}); alert(JSON.stringify(r,null,2)); refresh(); }
async function discover(){ const r = await jpost('/autofix/discover',{}); alert(JSON.stringify(r,null,2)); refresh(); }

async function saveEnv(){
  const kv = {};
  const k = document.getElementById('apikey').value.trim(); if(k) kv['LMSTUDIO_API_KEY']=k;
  const m = document.getElementById('models').value.trim(); if(m) kv['LMSTUDIO_MODEL']=m;
  const r = await jpost('/autofix/apply', {action:'set_env', kv});
  alert(JSON.stringify(r,null,2)); refresh();
}

async function sendChat(){
  const prompt = document.getElementById('prompt').value;
  const r = await jpost('/autofix/llm/chat', {prompt, max_tokens:128, temperature:0.2});
  document.getElementById('chatOut').innerText = JSON.stringify(r, null, 2);
}

setInterval(refresh, 5000);
refresh();
</script>
</body></html>"""

@ui_bp.route("/autofix", methods=["GET"])
def ui_autofix():
    return Response(_HTML, mimetype="text/html")

def register(app):
    app.register_blueprint(bp)
# c=a+b