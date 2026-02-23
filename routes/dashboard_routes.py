# -*- coding: utf-8 -*-
"""
routes/dashboard_routes.py - REST/HTML: /app/dashboard (mini-panel upravleniya).

Mosty:
- Yavnyy: (Veb ↔ Operatsii) HTML-svodka klyuchevykh statusov/schetchikov.
- Skrytyy #1: (Samokarta ↔ Navigatsiya) glubzhe vedem ssylkami na JSON-ruchki.
- Skrytyy #2: (Cron ↔ Kontrol) pokazyvaet, vklyuchen li CRON i skolko zadach.

Zemnoy abzats:
Kak pribornaya panel v avto: skorosti ne pribavlyaet, no daet uverennost - vse vidno.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, Response
import json, urllib.request, os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("dashboard_routes", __name__)

def register(app):
    app.register_blueprint(bp)

def _get(path: str, timeout: int=20)->dict:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000"+path, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return {"ok": False}

def _html():
    title=os.getenv("APP_TITLE","Ester Control Panel")
    mp=_get("/self/map"); passport_ok=os.path.isfile(os.getenv("PASSPORT_LOG","data/passport/log.jsonl"))
    media=_get("/media/video/status"); cron=_get("/cron/list"); p2p=_get("/p2p/bloom/status"); watch=_get("/watch/status")
    def yn(v): return "✅" if v else "⚠️"
    body=f"""<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
    <style>body{{font-family:system-ui;padding:18px}} .card{{border:1px solid #ddd;border-radius:12px;padding:12px;margin:8px 0}}</style></head>
    <body><h1>{title}</h1>
    <div class="card"><h3>Samokarta</h3>
      <p>Marshrutov: {len((mp.get('info') or {}).get('routes',[]))} · Ekshenov: {len((mp.get('info') or {}).get('actions',[]))}</p>
      <a href="/self/map">JSON</a>
    </div>
    <div class="card"><h3>Profile</h3><p>Fayl: {yn(passport_ok)}</p></div>
    <div class="card"><h3>Media</h3><p>ffprobe: {yn(media.get('ffprobe'))} · yt-dlp: {yn(media.get('ytdlp'))} · whisper: {yn(media.get('whisper'))}</p></div>
    <div class="card"><h3>Cron</h3><p>Zadach: {len((cron.get('jobs') or [])) if cron.get('jobs') else 0}</p></div>
    <div class="card"><h3>P2P Bloom</h3><p>added≈ {p2p.get('added','?')} · fpr≈ {p2p.get('fpr_est','?')}</p></div>
    <div class="card"><h3>Watch</h3><p>diry: {(watch.get('dirs') or [])} · maski: {(watch.get('patterns') or [])} · uchteno: {watch.get('count',0)}</p></div>
    </body></html>"""
    return body

@bp.route("/app/dashboard", methods=["GET"])
def app_dashboard():
    return Response(_html(), mimetype="text/html; charset=utf-8")
# c=a+b