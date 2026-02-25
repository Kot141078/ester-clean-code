# -*- coding: utf-8 -*-
"""routes/admin_webhooks_routes.py - mini-panel upravleniya webkhukami (Telegram setWebhook).

MOSTY:
- (Yavnyy) GET /admin/webhooks → HTML-forma; POST /admin/webhooks/telegram/set → vyzyvaet setWebhook with secret_token.
- (Skrytyy #1) Ispolzuet tot zhe token/bazu, what adapter Telegram; oshibok Meta/WA ne delaet - tam nastroyka iz konsoli.
- (Skrytyy #2) Stranitsa podskazyvaet aktualnyy URL webkhuka i sekret - udobno dlya DevOps.

ZEMNOY ABZATs:
Odin klik - i bot nachinaet prinimat vkhodyaschie: bez ruchnogo curl i kopipasty.

# c=a+b"""
from __future__ import annotations

import os, json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from fastapi import APIRouter, FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse
from modules.security.net_guard import deny_payload, is_outbound_network_allowed
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

API_BASE = os.getenv("TELEGRAM_BOT_API_BASE","https://api.telegram.org").rstrip("/")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN","")
SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET","")
DEFAULT_URL = os.getenv("TELEGRAM_WEBHOOK_URL","")

router = APIRouter()

def _tg_call(method: str, payload: dict) -> tuple[int, dict]:
    if not is_outbound_network_allowed():
        return (403, dict(deny_payload("telegram_webhook")))
    if not TOKEN:
        return (0, {"ok": False, "error": "no token"})
    url = f"{API_BASE}/bot{TOKEN}/{method}"
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type":"application/json"})
    try:
        with urlopen(req, timeout=10) as r:
            return (int(r.getcode()), json.loads(r.read().decode("utf-8") or "{}"))
    except HTTPError as e:
        try: data = json.loads(e.read().decode("utf-8") or "{}")
        except Exception: data = {"ok": False, "description": str(e)}
        return (int(e.code), data)
    except URLError as e:
        return (0, {"ok": False, "description": str(e)})

_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Webhooks</title>
<style>body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:16px;color:#222}
.card{border:1px solid #ddd;border-radius:12px;padding:12px;margin-bottom:12px;box-shadow:0 1px 2px rgba(0,0,0,.05)}
label{display:block;margin:6px 0}</style></head><body>
<h2>Vebkhuki</h2>
<div class="card">
  <h3>Telegram setWebhook</h3>
  <form method="post" action="/admin/webhooks/telegram/set">
    <label>URL webkhuka (obychno https://<host>/webhooks/telegram)
      <input name="url" style="width:480px" value="{url}">
    </label>
    <div>secret_token: <code>{secret}</code></div>
    <button type="submit">Postavit webkhuk</button>
  </form>
  <p><small>Posle ustanovki Telegram budet prisylat apdeyty na <code>/webhooks/telegram</code> s zagolovkom <code>X-Telegram-Bot-Api-Secret-Token</code>.</small></p>
</div>
<div class="card">
  <h3>WhatsApp Cloud</h3>
  <p>Vebkhuk nastraivaetsya v Meta Developers Console. Etot servis uzhe umeet prinimat verify i sobytiya na <code>/webhooks/whatsapp</code>. Ispolzuyte your <code>WHATSAPP_VERIFY_TOKEN</code>.</p>
</div>
</body></html>"""

@router.get("/admin/webhooks", response_class=HTMLResponse)
async def admin_webhooks_page():
    return HTMLResponse(_HTML.format(url=DEFAULT_URL, secret=SECRET or "<none>"))

@router.post("/admin/webhooks/telegram/set")
async def admin_webhooks_tg_set(url: str = Form(...)):
    payload = {"url": url.strip(), "secret_token": SECRET, "allowed_updates": ["message","edited_message","callback_query"]}
    code, data = _tg_call("setWebhook", payload)
    if code == 403 and str(data.get("error")) == "network_denied":
        return JSONResponse(data, status_code=403)
    ok = 200 <= code < 300 and bool(data.get("ok"))
    return JSONResponse({"ok": ok, "http_status": code, "raw": data})

def mount_admin_webhooks(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app
