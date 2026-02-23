# -*- coding: utf-8 -*-
"""
routes/lmstudio_routes.py - kompaktnaya konsol dlya LM Studio (UI + API).

Zachem:
- Ubeditsya, chto imenno LM Studio otvechaet (Ping/Models).
- Govorit s modelyu v chitabelnom vide (ne syroe JSON).
- Bez vneshnikh zavisimostey: esli net requests - ispolzuem urllib.

Mosty:
- Yavnyy: (Infrastruktura ↔ UX) - diagnosticheskiy UI poverkh OpenAI-sovmestimogo API.
- Skrytyy #1: (Nadezhnost ↔ Setevye protokoly) - myagkie taymauty i podrobnye oshibki.
- Skrytyy #2: (Samoobsluzhivanie ↔ Nablyudaemost) - schetchiki tokenov, podskazki po GPU.

Zemnoy abzats:
Ty otkryvaesh /ui/lm, zhmesh Ping - vidish spisok modeley iz LM Studio.
Vybiraesh model - zadaesh vopros - poluchaesh krasivyy otvet i usage.
Esli GPU «ne shevelitsya», sdelay dlinnee zapros/otvet, vklyuchi bolshuyu model,
ili uvelich max_tokens - togda grafik poydet vverkh.

# c=a+b
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, Optional, Tuple
from flask import Blueprint, current_app, jsonify, request, render_template_string  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("lmstudio_console", __name__)

# ---------- nizkourovnevyy HTTP klient (requests | urllib) ----------

def _lm_base() -> str:
    return os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/")

def _auth_header() -> Dict[str, str]:
    key = os.getenv("LMSTUDIO_API_KEY", "").strip()
    return {"Authorization": f"Bearer {key}"} if key else {}

def _http_get(path: str, timeout: float = 10.0) -> Tuple[int, Dict[str, Any]]:
    url = f"{_lm_base()}{path}"
    headers = {"Accept": "application/json"}
    headers.update(_auth_header())
    try:
        try:
            import requests  # type: ignore
            r = requests.get(url, headers=headers, timeout=timeout)
            code = r.status_code
            try:
                data = r.json()
            except Exception:
                data = {"raw": r.text}
            return code, data
        except Exception:
            # fallback na urllib
            import urllib.request, urllib.error  # type: ignore
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = resp.getcode()
                body = resp.read().decode("utf-8", "replace")
                try:
                    data = json.loads(body)
                except Exception:
                    data = {"raw": body}
                return code, data
    except Exception as e:
        return 599, {"error": str(e), "url": url}

def _http_post(path: str, payload: Dict[str, Any], timeout: float = 60.0) -> Tuple[int, Dict[str, Any]]:
    url = f"{_lm_base()}{path}"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    headers.update(_auth_header())
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        try:
            import requests  # type: ignore
            r = requests.post(url, headers=headers, data=body, timeout=timeout)
            code = r.status_code
            try:
                data = r.json()
            except Exception:
                data = {"raw": r.text}
            return code, data
        except Exception:
            import urllib.request, urllib.error  # type: ignore
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = resp.getcode()
                body2 = resp.read().decode("utf-8", "replace")
                try:
                    data = json.loads(body2)
                except Exception:
                    data = {"raw": body2}
                return code, data
    except Exception as e:
        return 599, {"error": str(e), "url": url, "payload": payload}

# ---------- API ----------

@bp.get("/api/lm/ping")
def api_lm_ping():
    code, data = _http_get("/models")
    ok = (200 <= code < 300) and isinstance(data, dict)
    return jsonify({"ok": ok, "code": code, "base": _lm_base(), "data": data})

@bp.get("/api/lm/models")
def api_lm_models():
    code, data = _http_get("/models")
    models = []
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        for m in data["data"]:
            mid = m.get("id") if isinstance(m, dict) else None
            if mid:
                models.append(mid)
    return jsonify({"ok": 200 <= code < 300, "code": code, "base": _lm_base(), "models": models, "raw": data})

@bp.post("/api/lm/chat")
def api_lm_chat():
    """
    Tonkiy proksi k /v1/chat/completions LM Studio.
    Vkhod JSON:
      {model, system, prompt, temperature, max_tokens}
    """
    j = request.get_json(silent=True) or {}
    model = j.get("model") or "gpt-oss-20b"
    system_prompt = j.get("system") or "You are Ester - a helpful local assistant."
    user_prompt = j.get("prompt") or ""
    temperature = float(j.get("temperature") or 0.3)
    max_tokens = int(j.get("max_tokens") or 256)

    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    t0 = time.time()
    code, data = _http_post("/chat/completions", payload, timeout=max(60.0, max_tokens * 0.5))
    dt = time.time() - t0

    # Dostaem cheloveko-chitaemyy otvet
    text = ""
    usage = {}
    if isinstance(data, dict):
        try:
            choices = data.get("choices") or []
            if choices:
                msg = (choices[0] or {}).get("message") or {}
                text = (msg.get("content") or "").strip()
            usage = data.get("usage") or {}
        except Exception:
            pass

    return jsonify({
        "ok": 200 <= code < 300,
        "code": code,
        "latency_sec": round(dt, 3),
        "model": model,
        "text": text,
        "usage": usage,
        "raw": data
    })

# ---------- UI ----------

@bp.get("/ui/lm")
def ui_lm_console():
    base = _lm_base()
    api_key_note = "LMSTUDIO_API_KEY set" if os.getenv("LMSTUDIO_API_KEY") else "LMSTUDIO_API_KEY not set (OK)"
    html = f"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  <title>Ester - LM Studio Console</title>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Arial; margin:16px; }}
    h1 {{ margin: 6px 0 12px; }}
    .row {{ display:flex; gap:12px; flex-wrap:wrap; }}
    .card {{ border:1px solid #e2e2e2; border-radius:12px; padding:12px; flex:1 1 380px; box-shadow:0 1px 2px rgba(0,0,0,.04); }}
    textarea, select, input[type=number] {{ width:100%; box-sizing:border-box; font-family:inherit; }}
    button {{ padding:8px 12px; border-radius:8px; border:1px solid #ccc; background:#fafafa; cursor:pointer; }}
    button:hover {{ background:#f0f0f0; }}
    .muted {{ color:#666; font-size:12px; }}
    .mono  {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; white-space:pre-wrap; }}
    .ok    {{ color:#0a6; font-weight:600; }}
    .bad   {{ color:#c00; font-weight:600; }}
    .tiny  {{ font-size:12px; }}
  </style>
</head>
<body>
  <h1>Ester - LM Studio Console</h1>
  <div class="row">
    <div class="card" style="max-width:460px">
      <div><b>LM Studio</b></div>
      <div class="tiny">base: <span class="mono">{base}</span></div>
      <div class="tiny">{api_key_note}</div>
      <div style="margin-top:8px; display:flex; gap:8px;">
        <button onclick="ping()">Ping</button>
        <button onclick="models()">Models</button>
      </div>
      <div id="diag" class="mono tiny" style="margin-top:8px;"></div>
    </div>

    <div class="card">
      <div><b>Chat s modelyu</b></div>
      <label class="tiny">Model</label>
      <select id="model"></select>
      <div class="row" style="gap:8px; margin-top:6px;">
        <div style="flex:1;">
          <label class="tiny">Temperatura</label>
          <input id="temp" type="number" step="0.1" min="0" max="2" value="0.3"/>
        </div>
        <div style="flex:1;">
          <label class="tiny">Max tokens</label>
          <input id="maxtok" type="number" min="1" max="8192" value="256"/>
        </div>
      </div>
      <label class="tiny" style="margin-top:6px; display:block;">System prompt</label>
      <textarea id="sys" rows="3">You are Ester - a helpful local assistant. Answer briefly and clearly in the user's language.</textarea>
      <label class="tiny" style="margin-top:6px; display:block;">Vopros</label>
      <textarea id="q" rows="4">Privet! Rasskazhi, chto ty vidish o moem LM Studio i kak mne proverit zagruzku GPU?</textarea>
      <div style="margin-top:8px;">
        <button onclick="ask()">Sprosit</button>
      </div>
      <div id="ans" class="mono" style="margin-top:8px;"></div>
      <details style="margin-top:8px;">
        <summary class="tiny">Syroy otvet</summary>
        <pre id="raw" class="mono tiny"></pre>
      </details>
    </div>
  </div>

<script>
async function ping() {{
  const r = await fetch('/api/lm/ping');
  const j = await r.json();
  const ok = j.ok ? 'ok' : 'bad';
  document.getElementById('diag').innerHTML =
    `<span class="${{ok}}">${{j.ok ? 'OK' : 'FAIL'}}</span> code=${{j.code}}; base=${{j.base}}`;
}}
async function models() {{
  const r = await fetch('/api/lm/models');
  const j = await r.json();
  const sel = document.getElementById('model');
  sel.innerHTML = '';
  (j.models || []).forEach(m => {{
    const o = document.createElement('option');
    o.value = o.textContent = m;
    sel.appendChild(o);
  }});
  document.getElementById('diag').innerText = JSON.stringify(j, null, 2);
}}
async function ask() {{
  const model = document.getElementById('model').value || 'gpt-oss-20b';
  const temperature = parseFloat(document.getElementById('temp').value || '0.3');
  const max_tokens = parseInt(document.getElementById('maxtok').value || '256');
  const system = document.getElementById('sys').value;
  const prompt = document.getElementById('q').value;
  document.getElementById('ans').textContent = '…';
  const r = await fetch('/api/lm/chat', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{model, system, prompt, temperature, max_tokens}})
  }});
  const j = await r.json();
  document.getElementById('ans').textContent = j.text || `(net teksta; code=${{j.code}})`;
  document.getElementById('raw').textContent = JSON.stringify(j, null, 2);
}}
window.addEventListener('load', models);
</script>
</body>
</html>"""
    return render_template_string(html)

def register_routes(app):
    app.register_blueprint(bp)

# c=a+b


def register(app):
    app.register_blueprint(bp)
    return app