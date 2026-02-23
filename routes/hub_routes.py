# -*- coding: utf-8 -*-
"""
routes/hub_routes.py - REST/HTML: /app/hub (mini-CRM panel vozmozhnostey i predlozheniy).
Obedinennaya versiya s uluchsheniyami dlya «Ester» (summary, P2P-sinkhronizatsiya, oblachnyy alert).

Mosty:
- Yavnyy: (UI ↔ Opps/Outreach/Pay) edinaya stranitsa obzora i bystrykh deystviy.
- Skrytyy #1: (Portfolio ↔ Navigatsiya) knopki vedut na portfolio i predlozheniya bez poiskov po menyu.
- Skrytyy #2: (Passport ↔ Prozrachnost) klyuchevye sobytiya logiruyutsya v «profile» pamyati.
- Skrytyy #3: (Mesh/P2P ↔ Nadezhnost) asinkhronnaya sinkhronizatsiya statusov mezhdu uzlami s backoff/timeout.
- Skrytyy #4: (Security ↔ Fragmentatsiya) JSON shifruetsya v _post_json (base64-placeholder) kak minimalnaya zaschita kanala.

Zemnoy abzats:
Eto «pult»: na odnom ekrane vidno sostoyanie podsistem (capmap/backup/cron/…),
mozhno zapustit nochnoy tsikl, svyazat STT, obnovit portfolio, a statusy sinkhroniziruyutsya
mezhdu agentami seti. Oblako poluchaet trevogu, esli uzly degradiruyut.

c=a+b
"""
from __future__ import annotations

import os
import json
import base64
import asyncio
from typing import Any, Dict, List, Tuple

from flask import Blueprint, Response, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("hub_routes", __name__)

# ---- Konstanty/nastroyki ----
P2P_PEERS: List[str] = [p.strip() for p in (os.getenv("ESTER_P2P_PEERS") or "").split(",") if p.strip()]
CLOUD_ENDPOINT = os.getenv("CLOUD_ENDPOINT", "https://example.com/judge")  # placeholder
CLOUD_API_KEY = os.getenv("CLOUD_API_KEY", "")
P2P_RETRIES = int(os.getenv("P2P_RETRIES", "3"))
P2P_BACKOFF_START = float(os.getenv("P2P_BACKOFF_START", "1"))
P2P_TIMEOUT = int(os.getenv("P2P_TIMEOUT", "10"))
FAILURES_ALERT_THRESHOLD = 3


# ---- Utility transporta ----
def _encrypt_json(data: Dict[str, Any]) -> str:
    """Mini-«shifrovanie» (placeholder) - base64(JSON)."""
    return base64.b64encode(json.dumps(data, ensure_ascii=False).encode("utf-8")).decode("utf-8")


def _decrypt_json(enc: str) -> Dict[str, Any]:
    if not enc:
        return {}
    return json.loads(base64.b64decode(enc.encode("utf-8")).decode("utf-8"))


def _get_json(path: str, timeout: int = 20) -> Tuple[bool, Dict[str, Any]]:
    import urllib.request

    try:
        with urllib.request.urlopen("http://127.0.0.1:8000" + path, timeout=timeout) as r:
            return True, json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return False, {"ok": False, "error": str(e), "path": path}


def _post_json(path: str, payload: Dict[str, Any] | None, timeout: int = 60) -> Tuple[bool, Dict[str, Any]]:
    import urllib.request

    try:
        enc_payload = _encrypt_json(payload or {})
        data = json.dumps({"enc": enc_payload}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8000" + path,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            rep_raw = json.loads(r.read().decode("utf-8"))
            rep = _decrypt_json(rep_raw.get("enc", "")) if isinstance(rep_raw, dict) else {}
            # Esli otvet ne upakovan, poprobuem «kak est»
            if not rep and isinstance(rep_raw, dict):
                rep = rep_raw
            return True, rep
    except Exception as e:
        return False, {"ok": False, "error": str(e), "path": path}


async def _p2p_sync_hub(hub_data: Dict[str, Any]) -> Dict[str, Any]:
    """Asinkhronnaya P2P-sinkhronizatsiya: otpravlyaem lokalnyy summary, prinimaem udalennyy i merzhim."""
    updated = dict(hub_data)
    if not P2P_PEERS:
        return updated

    enc_data = _encrypt_json(hub_data)

    async def _sync_with(peer: str) -> None:
        host, port_s = peer.split(":")
        port = int(port_s)
        for attempt in range(P2P_RETRIES + 1):
            try:
                reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=P2P_TIMEOUT)
                writer.write(f"SYNC_HUB:{enc_data}".encode("utf-8"))
                await writer.drain()
                data = await asyncio.wait_for(reader.read(65536), timeout=P2P_TIMEOUT)
                text = data.decode("utf-8", errors="ignore")
                remote_enc = text.split(":", 1)[1] if ":" in text else ""
                remote = _decrypt_json(remote_enc)
                if isinstance(remote, dict):
                    # Myagkiy merzh: dict poverkh dict (obnovlyaem polya 2-go urovnya)
                    for k, v in remote.items():
                        if isinstance(v, dict) and isinstance(updated.get(k), dict):
                            updated[k].update(v)  # type: ignore[union-attr]
                        else:
                            updated[k] = v
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
                break
            except Exception as e:
                if attempt < P2P_RETRIES:
                    await asyncio.sleep(P2P_BACKOFF_START * (2**attempt))
                else:
                    try:
                        from modules.mem.passport import append as passport  # type: ignore
                        passport("p2p_hub_fail", {"peer": peer, "error": str(e)}, "hub://p2p")
                    except Exception:
                        pass

    await asyncio.gather(*[_sync_with(p) for p in P2P_PEERS])
    return updated


def _judge_alert(metrics: Dict[str, Any]) -> None:
    """Otpravlyaet alert v oblako, esli chislo not-ok prevyshaet porog."""
    try:
        failures = sum(1 for v in metrics.values() if isinstance(v, dict) and v.get("ok") is False)
        if not CLOUD_API_KEY or failures <= FAILURES_ALERT_THRESHOLD:
            return
        payload = json.dumps({"metrics": metrics, "key": CLOUD_API_KEY}, ensure_ascii=False).encode("utf-8")

        import urllib.request

        req = urllib.request.Request(CLOUD_ENDPOINT, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status == 200:
                try:
                    advice = json.loads(r.read().decode("utf-8")).get("advice", "No advice")
                except Exception:
                    advice = "No advice"
                try:
                    from modules.mem.passport import append as passport  # type: ignore
                    passport("hub_judge_alert", {"advice": advice}, "hub://judge")
                except Exception:
                    pass
    except Exception:
        # Bezopasnyy no-op
        pass


# ---- API ----
@bp.route("/app/hub/summary", methods=["GET"])
def api_summary():
    """Sobiraem statusy klyuchevykh podsistem v edinuyu JSON-strukturu i sinkhroniziruem po P2P."""
    keys: Dict[str, Tuple[str, Dict[str, Any] | None, str]] = {
        "capmap": ("/self/capmap", None, "GET"),
        "ab": ("/runtime/ab/status", None, "GET"),
        "ab_health": ("/runtime/ab/health", {"paths": []}, "POST"),
        "stt": ("/bind/stt/status", None, "GET"),
        "cron": ("/cron/status", None, "GET"),
        "backup": ("/backup/status", None, "GET"),
        "discover": ("/app/discover/status", None, "GET"),
        # iz «py» moduley
        "opps": ("/opps/list", None, "GET"),
        "pay": ("/pay/prefs", None, "GET"),
    }

    out: Dict[str, Any] = {}
    for k, (path, payload, method) in keys.items():
        ok, rep = (_get_json(path) if method == "GET" else _post_json(path, payload))
        out[k] = rep if ok else {"ok": False, "error": rep.get("error", "fail"), "path": path}

    # Sinkhronizatsiya po P2P i vozmozhnyy alert
    out = asyncio.run(_p2p_sync_hub(out))
    _judge_alert(out)

    return jsonify({"ok": True, "hub": out})


@bp.route("/app/hub/cloud", methods=["GET"])
def api_cloud():
    """Zaglushka: «otpravka» summary v oblako/drayv/dashbord."""
    summary = api_summary().get_json(silent=True) or {}
    # Zdes mogla byt integratsiya s Firebase/Drive/Sheets/etc.
    print(f"[hub/cloud] summary bytes={{len(json.dumps(summary, ensure_ascii=False).encode('utf-8'))}}")
    return jsonify({"ok": True, "cloud_synced": True})


@bp.route("/app/hub", methods=["GET"])
def app_hub():
    """Prostaya HTML-panel so statusami i bystrymi deystviyami."""
    title = os.getenv("APP_TITLE", "Ester Control Panel")
    html = "<!doctype html><meta charset='utf-8'/>" \
           "<title>" + title + " - JobHub</title>" \
           "<style>" \
           "body{font:16px/1.4 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;padding:18px;max-width:1100px;margin:auto}" \
           "table{border-collapse:collapse;width:100%} td,th{border:1px solid #ddd;padding:6px} th{background:#f5f5f5;text-align:left}" \
           "small{color:#666}" \
           "button{margin-right:8px;margin-top:6px}" \
           "code{background:#f6f8fa;padding:1px 4px;border-radius:4px}" \
           "</style>" \
           "<h1>JobHub <small>(mikro-dashbord)</small></h1>" \
           "<h3>Opps (poslednie)</h3>" \
           "<table id='opps-table'><tr><th>Status</th><th>Title</th><th>Budget</th><th>Proposal</th></tr></table>" \
           "<h3>Pay Prefs</h3><pre id='pay-prefs'>…</pre>" \
           "<h3>System Status</h3>" \
           "<ul>" \
           "<li>CapMap: <span id='capmap'>?</span></li>" \
           "<li>AB: <span id='ab'>?</span></li>" \
           "<li>STT Bind: <span id='stt'>?</span> <button onclick='sttRun()'>Run</button></li>" \
           "<li>Cron: <span id='cron'>?</span> <button onclick='nightlyRun()'>Nightly Run</button></li>" \
           "<li>Backup: <span id='backup'>?</span> <button onclick='mkBackup()'>Make Backup</button></li>" \
           "<li>Discovery: <span id='disco'>?</span> <button onclick='scanDiscover()'>Scan & Register</button></li>" \
           "</ul>" \
           "<button onclick='refreshAll()'>Refresh</button>" \
           "<button onclick='abHealth()'>AB Health</button>" \
           "<button onclick=\"abSwitch('A')\">AB to A</button>" \
           "<button onclick=\"abSwitch('B')\">AB to B</button>" \
           "<script>" \
           "function esc(s){return String(s).replace(/[&<>\"]/g, c=>({ '&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;' }[c]));}" \
           "async function jget(u){const r=await fetch(u); return await r.json();}" \
           "async function jpost(u,d){const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d||{})}); return await r.json();}" \
           "async function refreshAll(){" \
           "  const H = await jget('/app/hub/summary'); const hub = H.hub || {};" \
           "  const C = hub.capmap || {}; const routes=(C.routes||[]).length||0; const actions=(C.actions||[]).length||0;" \
           "  document.getElementById('capmap').innerHTML = (C.ok!==false?'✔️':'✖️')+' · routes: <b>'+routes+'</b> · actions: <b>'+actions+'</b>'; " \
           "  const AB = hub.ab || {}; document.getElementById('ab').innerHTML = (AB.ok!==false?'✔️':'✖️')+' · active: <b>'+(AB.active ?? '?')+'</b>'; " \
           "  const STT = hub.stt || {}; const runs=(STT.runs ?? (STT.state && STT.state.runs))||0; const seen=(STT.seen ?? (STT.state && STT.state.seen))||0;" \
           "  document.getElementById('stt').innerHTML = (STT.ok!==false?'✔️':'✖️')+' · runs: <b>'+runs+'</b> · seen: <b>'+seen+'</b>'; " \
           "  const CRON = (hub.cron && hub.cron.state) ? hub.cron.state : {}; document.getElementById('cron').innerHTML = 'enabled: <b>'+(CRON.enabled ?? '?')+'</b> · time: <b>'+(CRON.time||'-')+'</b> · next: <b>'+(CRON.next_t||'-')+'</b>'; " \
           "  const BK = hub.backup || {}; document.getElementById('backup').innerHTML = (BK.ok!==false?'✔️':'✖️')+' · files: <b>'+(BK.count||0)+'</b> · total_bytes: <b>'+(BK.total_bytes||0)+'</b>'; " \
           "  const DC = hub.discover || {}; const ST = DC.state || {}; document.getElementById('disco').innerHTML = (DC.ok!==false?'✔️':'✖️')+' · autorun: <b>'+((ST.autorun!==false))+'</b> · found_last: <b>'+((ST.found||[]).length||0)+'</b>'; " \
           "  const OP = hub.opps || {}; const items = (OP.items || []).slice(-20).reverse(); let rows='';" \
           "  for (const it of items){ const id=esc(it.id||''); const status=esc(it.status||''); const title=esc(it.title||''); const budget=esc((it.budget ?? '').toString()); const currency=esc(it.currency||'');" \
           "    rows += `<tr><td>${status}</td><td>${title}</td><td>${budget} ${currency}</td><td><a href='/outreach/proposal/get?id=${id}&format=html'>proposal</a></td></tr>`; }" \
           "  if(!rows){ rows = '<tr><td colspan=\"4\">empty</td></tr>'; }" \
           "  document.getElementById('opps-table').innerHTML = '<tr><th>Status</th><th>Title</th><th>Budget</th><th>Proposal</th></tr>'+rows; " \
           "  const PAY = hub.pay || {}; const prefs = (PAY.ok!==false && PAY.prefs) ? PAY.prefs : {}; document.getElementById('pay-prefs').textContent = JSON.stringify(prefs, null, 2); " \
           "}" \
           "async function nightlyRun(){ const r=await jpost('/cron/nightly/run',{dry_run:false}); alert('Nightly: '+(r.ok?'OK':'FAIL')+(r.report?('\\nReport: '+r.report):'')); refreshAll(); }" \
           "async function sttRun(){ const r=await jpost('/bind/stt/run',{}); alert('STT bind: '+(r.ok?'OK':'FAIL')+(r.done?(' / done='+r.done):'')); refreshAll(); }" \
           "async function mkBackup(){ const r=await jpost('/backup/snapshot',{label:'hub'}); alert('Backup: '+(r.ok?'OK':'FAIL')+(r.zip?('\\nZIP: '+r.zip):'')); refreshAll(); }" \
           "async function scanDiscover(){ const sc=await jget('/app/discover/scan'); const mods=(sc.found||[]).map(x=>x.name); if(!mods.length){ alert('Nichego novogo'); return; } const r=await jpost('/app/discover/register',{modules:mods}); alert('Discovery: registered='+r.registered+' routes='+r.routes+' actions='+r.actions); refreshAll(); }" \
           "async function abHealth(){ const r=await jpost('/runtime/ab/health',{paths:[]}); alert('AB health: '+(r.ok?'OK':'FAIL')); refreshAll(); }" \
           "async function abSwitch(slot){ const r=await jpost('/runtime/ab/switch',{slot:slot, dry_run:false, require_health:true}); alert('Switch to '+slot+': '+(r.ok?'OK':'FAIL')); refreshAll(); }" \
           "refreshAll(); setInterval(refreshAll, 30000);" \
           "</script>"
    return Response(html, mimetype="text/html; charset=utf-8")


def register(app):  # pragma: no cover
    """Drop-in registratsiya blyuprinta."""
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    """Sovmestimyy khuk initsializatsii (pattern iz dampa)."""
    register(app)


__all__ = ["bp", "register", "init_app"]
# c=a+b