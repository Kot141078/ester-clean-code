# -*- coding: utf-8 -*-
"""
routes/email_routes.py — REST dlya generatsii i otpravki pisem + HTML predprosmotr.

MOSTY:
- (Yavnyy) /email/compose → generatsiya (uchet profilya po keys), /email/send → SMTP otpravka, /email/styles → spravka.
- (Skrytyy #1) Pri generatsii podtyagivaet profil po contact_key→agent_id (roles.store), kak i v soobscheniyakh.
- (Skrytyy #2) HTML-stranitsa /email/preview.html — bystryy UI bez vneshnikh zavisimostey.

ZEMNOY ABZATs:
Ester pishet pisma «v temu»: pravilnyy ton dlya advokata/shkolnika/druga, akkuratnaya tema i struktura. I — otpravlyaet.

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, FastAPI, Body
from fastapi.responses import JSONResponse, HTMLResponse
import os

from messaging.email_compose import compose_email
from messaging.email_smtp import send_email as _send_email
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

@router.post("/email/compose")
async def email_compose(payload: Dict[str, Any] = Body(...)):
    keys = [str(k) for k in (payload.get("keys") or [])]
    intent = str(payload.get("intent") or "")
    ctx = payload.get("context") or {}
    kind = payload.get("kind")
    if not keys or not intent:
        return JSONResponse({"ok": False, "error": "keys and intent required"}, status_code=400)
    res = compose_email(keys, intent, ctx, kind_hint=kind)
    return JSONResponse({"ok": True, **res})

@router.post("/email/send")
async def email_send(payload: Dict[str, Any] = Body(...)):
    to = [str(x) for x in (payload.get("to") or [])]
    subject = str(payload.get("subject") or "")
    text = payload.get("text")
    html = payload.get("html")
    if not to or not subject or not (text or html):
        return JSONResponse({"ok": False, "error": "to[], subject, and text or html required"}, status_code=400)
    res = _send_email(to, subject, text=text, html=html)
    return JSONResponse({"ok": True, **res})

@router.get("/email/styles")
async def email_styles():
    return JSONResponse({"ok": True, "styles": ["lawyer","student","friend","business","default"]})

_HTML = """
<!doctype html><html><head><meta charset="utf-8"><title>Email Compose</title>
<style>
body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:16px;color:#222}
.card{border:1px solid #ddd;border-radius:12px;padding:12px;margin-bottom:12px;box-shadow:0 1px 2px rgba(0,0,0,.05)}
label{display:block;margin:6px 0}
textarea,input{width:100%}
small{color:#666}
</style></head><body>
<h2>Generator pisem</h2>
<div class="card">
  <label>Klyuchi auditorii (cherez zapyatuyu, naprimer <code>email:lawyer@example.com, telegram:42</code>)<br>
    <input id="keys" placeholder="email:lawyer@example.com">
  </label>
  <label>Komu pishem (stil):<br>
    <select id="kind"><option value="">auto</option><option>lawyer</option><option>student</option><option>friend</option><option>business</option></select>
  </label>
  <label>Zamysel pisma (intent):<br>
    <textarea id="intent" rows="3" placeholder="Nuzhen ekspress-analiz dogovora do chetverga."></textarea>
  </label>
  <details><summary>Kontekst (neobyazatelno)</summary>
    <label>Detali:<br><input id="details" placeholder="dogovor na 4 stranitsy, pravki v razdele 3.2"></label>
    <label>Deystvie (CTA):<br><input id="cta" placeholder="Soobschite, pozhaluysta, smozhete li do 14:00"></label>
    <label>Dedlayn:<br><input id="deadline" placeholder="chetverg 14:00"></label>
  </details>
  <button onclick="compose()">Sgenerirovat</button>
</div>
<div id="draft" class="card" style="display:none">
  <h3>Chernovik</h3>
  <div><b>Tema:</b> <span id="subj"></span></div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:8px">
    <div><h4>Tekst</h4><pre id="text" style="white-space:pre-wrap"></pre></div>
    <div><h4>HTML</h4><iframe id="html" style="width:100%;height:240px;border:1px solid #eee;border-radius:8px"></iframe></div>
  </div>
  <details style="margin-top:8px"><summary>Diagnostika</summary><pre id="trace"></pre></details>
  <div style="margin-top:8px">
    <label>Otpravit na adresa (cherez zapyatuyu):<br><input id="to" placeholder="lawyer@example.com"></label>
    <button onclick="send()">Otpravit</button>
    <span id="sendres"></span>
  </div>
</div>
<script>
async function compose(){
  const keys = document.getElementById('keys').value.split(',').map(s=>s.trim()).filter(Boolean);
  const intent = document.getElementById('intent').value;
  const kind = document.getElementById('kind').value || null;
  const ctx = {details: document.getElementById('details').value, cta: document.getElementById('cta').value, deadline: document.getElementById('deadline').value};
  const r = await fetch('/email/compose',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({keys:int(keys), intent, context:ctx, kind})});
  async function int(a){return a}
  const d = await r.json();
  if(!d.ok){alert('Oshibka: '+(d.error||'unknown')); return}
  document.getElementById('subj').textContent = d.subject || '';
  document.getElementById('text').textContent = d.text || '';
  const html_ifr = document.getElementById('html').contentWindow.document;
  html_ifr.open(); html_ifr.write(d.html || '<p>(pusto)</p>'); html_ifr.close();
  document.getElementById('trace').textContent = JSON.stringify({style:d.style, labels:d.labels, trace:d.trace}, null, 2);
  document.getElementById('draft').style.display='block';
}
async function send(){
  const to = document.getElementById('to').value.split(',').map(s=>s.trim()).filter(Boolean);
  const subject = document.getElementById('subj').textContent;
  const text = document.getElementById('text').textContent;
  const html = document.getElementById('html').contentWindow.document.body.parentElement.outerHTML;
  const r = await fetch('/email/send',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({to, subject, text, html})});
  const d = await r.json();
  document.getElementById('sendres').textContent = d.ok ? ('OK: '+d.sent+' / fail '+d.failed) : ('Oshibka: '+(d.error||'unknown'));
}
</script>
</body></html>
"""

@router.get("/email/preview.html", response_class=HTMLResponse)
async def email_preview():
    return HTMLResponse(_HTML)

def mount_email_routes(app: FastAPI) -> None:
    app.include_router(router)