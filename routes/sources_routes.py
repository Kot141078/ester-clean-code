# -*- coding: utf-8 -*-
"""
routes/sources_routes.py - REST-most dlya podachi stimulov myshleniya v shinu.

Endpoynty (JWT):
  POST /sources/dialog        {"source":"ui|api|ext","user":"...", "text":"..."}
  POST /sources/telegram      {"user":"...", "chat":"...", "text":"..."}        # esli khochesh pryamoy push iz tg-pollera
  POST /sources/file_read     {"path":"...", "sha256":"...", "size":123}        # signal ob obrabotannom fayle
  POST /sources/web_discovery {"query":"...", "url":"...", "title":"..."}       # uchityvaetsya tolko pri ALLOW_WEB=1
  POST /sources/heartbeat     - ruchnoy tik «podumat seychas»
  GET  /sources/status        - counters + env flagi

Vzaimodeystvie:
  • Publikuet sobytiya v modules.events_bus: dialog.message / telegram.message / ingest.file / web.discovery.
  • Vorker modules.always_thinker podpisan na eti sobytiya i initsiiruet reflect_once.

# c=a+b
"""
from __future__ import annotations

import os
from flask import jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore

from modules import events_bus
from modules.always_thinker import start_background, consume_once
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ALLOW_WEB = bool(int(os.getenv("ALLOW_WEB", "0")))

def _ok():
    return jsonify({"ok": True})

def register_sources_routes(app, url_prefix: str = "/sources"):
    # avtozapusk vorkera «vsegda dumat»
    try:
        start_background()
    except Exception:
        pass

    @app.get(f"{url_prefix}/status")
    @jwt_required()
    def status():
        return jsonify({
            "ok": True,
            "allow_web": ALLOW_WEB,
        })

    @app.post(f"{url_prefix}/dialog")
    @jwt_required()
    def dialog():
        data = request.get_json(force=True)
        events_bus.append("dialog.message", {"payload": {
            "source": data.get("source") or "ui", "user": data.get("user"), "text": data.get("text")}})
        return _ok()

    @app.post(f"{url_prefix}/telegram")
    @jwt_required()
    def telegram():
        data = request.get_json(force=True)
        events_bus.append("telegram.message", {"payload": {
            "user": data.get("user"), "chat": data.get("chat"), "text": data.get("text")}})
        return _ok()

    @app.post(f"{url_prefix}/file_read")
    @jwt_required()
    def file_read():
        data = request.get_json(force=True)
        events_bus.append("ingest.file", {"payload": {
            "path": data.get("path"), "sha256": data.get("sha256"), "size": data.get("size")}})
        return _ok()

    @app.post(f"{url_prefix}/web_discovery")
    @jwt_required()
    def web_discovery():
        data = request.get_json(force=True)
        if not ALLOW_WEB:
            return jsonify({"ok": False, "error": "web disabled (ALLOW_WEB=0)"}), 403
        events_bus.append("web.discovery", {"payload": {
            "query": data.get("query"), "url": data.get("url"), "title": data.get("title")}})
        return _ok()

    @app.post(f"{url_prefix}/heartbeat")
    @jwt_required()
    def heartbeat():
        # razovaya obrabotka ocheredi + myagkaya refleksiya (cherez vorker)
        rep = consume_once(limit=int((request.get_json(silent=True) or {}).get("limit") or 200))
        return jsonify(rep)


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
def register(app):
    # vyzyvaem suschestvuyuschiy register_sources_routes(app) (url_prefix beretsya po umolchaniyu vnutri funktsii)
    return register_sources_routes(app)

# === /AUTOSHIM ===