# routes/portal_media.py
# -*- coding: utf-8 -*-
"""
routes/portal_media.py - stranitsa «Sozdat fleshku Ester» (HTML teper v strokovom literale, a ne «syroy» v .py).

Mosty:
- Yavnyy (UI ↔ Portable/USB): chelovek zapuskaet podgotovku nositelya i zapis arkhiva/dampa.
- Skrytyy 1 (Operatsii ↔ Bezopasnost): UI ozhidaet JWT (iz /auth/ui) i shlet ego v zagolovke.
- Skrytyy 2 (Memory ↔ Inzheneriya): sostoyanie agenta mozhno posmotret odnoy knopkoy.

Zemnoy abzats:
Rout GET /portal/media otdaet HTML; JS obschaetsya s /self/usb/* i /portal/media/* (esli realizovano). Bez «syrogo» HTML v .py - Python bolshe ne pytaetsya parsit U+2014 kak kod.

# c=a+b
"""
from __future__ import annotations

from flask import Blueprint, Response, jsonify, request
import json
import time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("portal_media", __name__)

# HTML perenesen v strokovoy literal (vzyato iz dampa)
_HTML = '''<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  <title>Ester - Sozdat fleshku</title>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <style>
    body{font-family:system-ui,Arial,sans-serif;margin:0;padding:16px;background:#0b0f14;color:#e6eef7}
    h1{font-size:20px;margin:0 0 12px}
    section{background:#111826;border:1px solid #273244;border-radius:12px;padding:16px;margin:12px 0}
    button,input,select{background:#1b2432;color:#e6eef7;border:1px solid #38465c;border-radius:8px;padding:8px 12px}
    button:hover{filter:brightness(1.1)}
    .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
    table{width:100%;border-collapse:collapse;margin-top:8px}
    th,td{border-bottom:1px solid #243042;padding:8px 6px;text-align:left}
    .ok{color:#9BE28D}.err{color:#ff8a8a}.muted{color:#9aa9bd}
    .chip{display:inline-block;padding:2px 8px;border:1px solid #38465c;border-radius:999px;margin-left:6px}
    .hint{font-size:12px;color:#9aa9bd}
    .mono{font-family:ui-monospace,Consolas,monospace}
  </style>
</head>
<body>
  <h1>Sozdat fleshku Ester</h1>

  <section id="auth">
    <div class="row">
      <span class="hint">JWT dlya REST /self/usb/*</span>
      <input id="jwt" placeholder="vstavte JWT (ili otkroyte /auth/ui)" class="mono" style="min-width:380px">
      <button onclick="saveJWT()">Save</button>
      <a href="/auth/ui" target="_blank" class="chip">Otkryt /auth/ui</a>
    </div>
    <div class="hint">Token khranitsya tolko v pamyati stranitsy (localStorage: ester_jwt).</div>
  </section>

  <section>
    <div class="row">
      <button onclick="loadUsb()">Obnovit spisok USB</button>
      <span id="usb_count" class="chip muted">-</span>
    </div>
    <table id="usb_tbl"><thead><tr><th>Mount</th><th>Deystviya</th></tr></thead><tbody></tbody></table>
  </section>

  <section>
    <div class="row">
      <label>Fayl arkhiva (CID.zip): <input type="file" id="archive_file" accept=".zip"></label>
      <label>Fayl dampa (ester_dump.zip): <input type="file" id="dump_file" accept=".zip,.7z,.tar,.gz"></label>
      <label>Kuda: 
        <select id="mount_sel"></select>
      </label>
      <button onclick="deploy()">Razvernut</button>
      <span id="deploy_status" class="chip muted">gotov</span>
    </div>
  </section>

  <section>
    <div class="row">
      <button onclick="loadState()">Pokazat sostoyanie agenta</button>
    </div>
    <pre id="state" class="mono" style="white-space:pre-wrap"></pre>
  </section>

<script>
const LS_KEY='ester_jwt';
function jwt(){ return localStorage.getItem(LS_KEY)||'' }
function saveJWT(){ localStorage.setItem(LS_KEY, document.getElementById('jwt').value.trim()); alert('JWT sokhranen'); }
function hdrs(){ const h={'Content-Type':'application/json'}; if(jwt()) h['Authorization']='Bearer '+jwt(); return h; }

async function loadUsb(){
  const r = await fetch('/self/usb/list', {headers: hdrs()});
  const j = await r.json().catch(()=>({ok:false,error:'bad json'}));
  const tb = document.querySelector('#usb_tbl tbody'); tb.innerHTML='';
  const sel = document.getElementById('mount_sel'); sel.innerHTML='';
  if(!j.ok){ tb.innerHTML = `<tr><td colspan="2" class="err">${j.error||'error'}</td></tr>`; return; }
  const arr = j.roots||[];
  document.getElementById('usb_count').textContent = arr.length+' nositeley';
  arr.forEach(m => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td class="mono">${m}</td>
      <td class="row">
        <button data-m="${m}">Podgotovit /ESTER</button>
        <button data-m2="${m}">Otformatirovat FAT32</button>
        <button data-sel="${m}">Vybrat</button>
      </td>`;
    tr.querySelector('[data-m]').onclick = ()=>prepare(m);
    tr.querySelector('[data-m2]').onclick = ()=>formatFAT(m);
    tr.querySelector('[data-sel]').onclick = ()=>{ document.getElementById('mount_sel').value = m; };
    tb.appendChild(tr);
    const opt = document.createElement('option'); opt.value=m; opt.textContent=m; sel.appendChild(opt);
  });
}

async function prepare(mount){
  const r = await fetch('/self/usb/prepare', {method:'POST', headers: hdrs(), body: JSON.stringify({mount})});
  const j = await r.json().catch(()=>({ok:false,error:'bad json'}));
  alert(j.ok?'Gotovo: '+(j.root||''):'Oshibka: '+(j.error||''));
}

async function formatFAT(mount){
  const r = await fetch('/self/usb/format', {method:'POST', headers: hdrs(), body: JSON.stringify({mount, fs:'fat32'})});
  const j = await r.json().catch(()=>({ok:false,error:'bad json'}));
  alert(j.ok?'Formatirovano':'Oshibka: '+(j.error||''));
}

async function deploy(){
  const sel = document.getElementById('mount_sel'); const mount = sel.value;
  if(!mount){ alert('Snachala obnovite spisok USB i vyberite nositel'); return; }
  const fd = new FormData();
  fd.append('mount', mount);
  const af = document.getElementById('archive_file'); if(af.files.length) fd.append('archive_file', af.files[0]);
  const df = document.getElementById('dump_file'); if(df.files.length) fd.append('dump_file', df.files[0]);
  const r = await fetch('/portal/media/deploy', {method:'POST', body: fd});
  const j = await r.json().catch(()=>({ok:false,error:'bad json'}));
  document.getElementById('deploy_status').textContent = j.ok ? 'OK' : 'ERR';
  alert(j.ok?'Uspekh':'Oshibka: '+(j.error||j.stderr||''));
}

async function loadState(){
  const r = await fetch('/portal/media/state');
  const j = await r.json().catch(()=>({ok:false,error:'bad json'}));
  document.getElementById('state').textContent = JSON.stringify(j, null, 2);
}

// init
document.getElementById('jwt').value = jwt();
loadUsb().catch(()=>{});
</script>
</body>
</html>
'''

@bp.route("/portal/media", methods=["GET"])
def portal_media_page() -> Response:
    return Response(_HTML, mimetype="text/html; charset=utf-8")

@bp.route("/portal/media/state", methods=["GET"])
def portal_media_state():
    # Legkiy status; pri nalichii sobstvennykh sborok mozhno rasshirit
    return jsonify({"ok": True, "ts": int(time.time())})

@bp.route("/portal/media/deploy", methods=["POST"])
def portal_media_deploy():
    """
    Pri nalichii moduley «portable/replica» mozhno zdes vypolnit realnuyu zapis.
    Seychas - bezopasnyy otvet (ne ronyaet UI), chtoby ubrat 500.
    """
    try:
        mount = request.form.get("mount") or ""
        if not mount:
            return jsonify({"ok": False, "error": "mount_required"}), 400
        # Pytaemsya delegirovat, esli est integratsiya
        try:
            from modules.portable.usb import deploy as usb_deploy  # type: ignore
            res = usb_deploy(mount, request.files)
            return jsonify({"ok": True, **(res or {})})
        except Exception:
            # Net enterprise-moduley - myagkiy otkaz
            return jsonify({"ok": False, "error": "portable_unavailable"}), 501
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

def register_routes(app, seen_endpoints=None):
    app.register_blueprint(bp)


def register(app):
    app.register_blueprint(bp)
    return app