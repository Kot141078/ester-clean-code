# -*- coding: utf-8 -*-
"""
routes/lan_reply.py - HTTP priemnik LAN-kvitantsiy.

Marshruty:
  • POST /lan/reply     - telo: JSON kvitantsii; HMAC mozhno v zagolovke X-Signature (hex) ili v pole "sig"

Otvet:
  {"ok":true, "saved":true, "applied":true|false, "overlay":true|false}

Mosty:
- Yavnyy (HTTP ↔ Podtverzhdenie): prostoy REST-vkhod dlya LAN-otvetov.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): vozvraschaem, smogli li primenit k ocheredi.
- Skrytyy 2 (Praktika ↔ Sovmestimost): pri otsutstvii sekreta rabotaem v doveritelnom LAN.

Zemnoy abzats:
Kak priemnaya okoshka: prinyal talon, postavil pechat i razlozhil po papkam.

# c=a+b
"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, request

from modules.lan_reply.protocol import normalize, verify  # type: ignore
from modules.lan_reply.inbox import save_receipt, add_log  # type: ignore
from modules.hybrid.dispatcher_adapter import apply_receipt  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_lan = Blueprint("lan_reply", __name__)

@bp_lan.post("/lan/reply")
def lan_reply():
    secret = os.getenv("LAN_REPLY_SECRET") or None
    obj = request.get_json(silent=True) or {}
    try:
        obj = normalize(obj)
    except Exception as e:
        return jsonify({"ok": False, "error": f"normalize:{e}"}), 400
    sig = request.headers.get("X-Signature") or None
    if not verify(obj, secret, sig):
        add_log("http_bad_sig", {"obj": obj})
        return jsonify({"ok": False, "error": "bad-signature"}), 403
    saved = save_receipt(obj)
    applied = apply_receipt(obj)
    return jsonify({"ok": True, "saved": bool(saved.get("ok")), **applied})

def register_lan_reply(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_lan)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("lan_reply_pref", __name__, url_prefix=url_prefix)

        @pref.post("/lan/reply")
        def _p(): return lan_reply()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_lan)
    return app