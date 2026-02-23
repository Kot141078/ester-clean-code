# -*- coding: utf-8 -*-
"""
routes/transport_status.py — UI/REST «Transport uzlov».

Marshruty:
  • GET  /admin/transport               — HTML-stranitsa
  • GET  /admin/transport/peers         — JSON: reestr/dostupnost
  • POST /admin/transport/ping          — ping odnogo base_url
  • POST /admin/transport/testmsg       — otpravit test-soobschenie (mode=lan|telegram, payload opts.)

Mosty:
- Yavnyy (Kibernetika v†" UX): odin ekran pokazyvaet «chem Re s kem my govorim».
- Skrytyy 1 (Infoteoriya v†" Giagnostika): bystrye pingi Re ekho-testy, bez tyazhelykh zavisimostey.
- Skrytyy 2 (Praktika v†" Vezopasnost): rezhim AB: A — tolko nablyudenie; B — razreshit otpravku testmsg.

Zemnoy abzats:
Stranitsa tekhnika: vidno sosedey po LAN, mozhno poslat «privet» vsem (ili cherez Telegram), chtoby ubeditsya v svyaznosti.

# c=a+b
"""
from __future__ import annotations

import json
import os
from flask import Blueprint, jsonify, render_template, request

from modules.transport.transport_manager import discover, http_ping, send_test_message  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_transport = Blueprint("transport_status", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_transport.get("/admin/transport")
def page_transport():
    return render_template("transport_status.html", ab=AB)

@bp_transport.get("/admin/transport/peers")
def api_peers():
    try:
        rep = discover()
        return jsonify({"ok": True, **rep})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500

@bp_transport.post("/admin/transport/ping")
def api_ping():
    base = (request.form.get("base") or request.json.get("base") if request.is_json else None or "").strip()
    if not base:
        return jsonify({"ok": False, "error": "base is required"}), 400
    return jsonify(http_ping(base))

@bp_transport.post("/admin/transport/testmsg")
def api_testmsg():
    if AB != "B":
        return jsonify({"ok": False, "error": "AB_MODE!=B"}), 403
    is_json = request.is_json
    mode = (request.form.get("mode") if not is_json else request.json.get("mode", "lan")) or "lan"
    payload_raw = (request.form.get("payload") if not is_json else request.json.get("payload", "")) or ""
    try:
        payload = json.loads(payload_raw) if isinstance(payload_raw, str) and payload_raw.strip().startswith("{") else {"text": str(payload_raw)}
    except Exception:
        payload = {"text": str(payload_raw)}
    rep = send_test_message(mode, payload)
    return jsonify(rep)

def register_transport_status(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_transport)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("transport_status_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/transport")
        def _p():
            return page_transport()

        @pref.get("/admin/transport/peers")
        def _pp():
            return api_peers()

        @pref.post("/admin/transport/ping")
        def _pg():
            return api_ping()

        @pref.post("/admin/transport/testmsg")
        def _pt():
            return api_testmsg()

# app.register_blueprint(pref)
# c=a+b



def register(app):
    app.register_blueprint(bp_transport)
    return app