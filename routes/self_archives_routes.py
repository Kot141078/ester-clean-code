# -*- coding: utf-8 -*-
"""routes/self_archives_routes.py - P2P-obmen sobstvennymi arkhivami (CID) s unifitsirovannoy HMAC-autentifikatsiey.

Mosty:
  • (P2P-guard ↔ Arkhivy) edinyy mekhanizm podpisi umenshaet raskhozhdeniya v zaschite raznykh zon.
Skrytye mosty:
  • (Manifest ↔ Arkhiv) marshruty /manifest i /archive ispolzuyut odnu i tu zhe verifikatsiyu.  :contentReference[oaicite:11]{index=11}
  • (Testy ↔ Servis) sovmestim s test_p2p_sign_script i curl-generatsiey iz scripts/p2p_sign.py.  :contentReference[oaicite:12]{index=12} :contentReference[oaicite:13]{index=13}

Zemnoy abzats: “ruchka sklada” - vydaet manifest/arkhiv tolko tem, kto predyavil pravilnuyu nakladnuyu (podpis), pri etom starye nakladnye esche chitayutsya.

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, send_file

from modules.selfmanage.archive import archive_path
from modules.selfmanage.manifest import load_manifest
from security.p2p_signature import HDR_TS, verify_any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

p2p_self_bp = Blueprint("p2p_self", __name__, url_prefix="/p2p/self")


def _check_or_401(method: str, path: str):
    ok, err = verify_any(
        request.headers, method, path, request.get_data(cache=True, as_text=False) or b""
    )
    if not ok:
        return jsonify({"ok": False, "error": err or "auth failed"}), 401
    return None


@p2p_self_bp.post("/announce")
def p2p_announce():
    fail = _check_or_401("POST", "/p2p/self/announce")
    if fail:
        return fail
    data = request.get_json(force=True, silent=True) or {}
    cid = str(data.get("cid") or "")
    if not cid:
        return jsonify({"ok": False, "error": "cid required"}), 400
    have = archive_path(cid) is not None
    return jsonify({"ok": True, "have": have, "cid": cid})


@p2p_self_bp.get("/manifest/<cid>")
def p2p_manifest(cid: str):
    fail = _check_or_401("GET", f"/p2p/self/manifest/{cid}")
    if fail:
        return fail
    man = load_manifest(cid)
    if not man:
        return jsonify({"ok": False, "error": "not found"}), 404
    return (jsonify(man), 200)


@p2p_self_bp.get("/archive/<cid>")
def p2p_archive(cid: str):
    fail = _check_or_401("GET", f"/p2p/self/archive/{cid}")
    if fail:
        return fail
    p = archive_path(cid)
    if not p:
        return jsonify({"ok": False, "error": "not found"}), 404
    return send_file(p, as_attachment=True, download_name=f"{cid}.zip", mimetype="application/zip")


def register_self_archives_routes(app) -> None:
    app.register_blueprint(p2p_self_bp)


def register(app):
    app.register_blueprint(p2p_self_bp)
    return app