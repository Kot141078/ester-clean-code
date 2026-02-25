# -*- coding: utf-8 -*-
"""routes/portable_replica.py - UI/REST “Otdat/Zabrat” portable + P2P endpoints.

Local:
  • GET /admin/portable/replica
  • GET /admin/portable/replica/status
  • POST /admin/portable/replica/index
  • POST /admin/portable/replica/offer
  • POST /admin/portable/replica/pull
  • POST /admin/portable/replica/activate

P2P:
  • GET /lan/portable/manifest
  • GET /lan/portable/block/<sha>

Mosty:
- Yavnyy (Kibernetika ↔ UX): knopki “Otdat/Zabrat” i monitoring progress.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): token/lokalnaya set + khesh-kontrol i CAS.
- Skrytyy 2 (Praktika ↔ Sovmestimost): ne trogaem yadro; aktivatsiya sovmestima so slotovoy skhemoy.

Zemnoy abzats:
Odin ekran: indeksirovat svoy current, vystavit manifest, zabrat u soseda i pri zhelanii akkuratno vklyuchit novuyu versiyu.

# c=a+b"""
from __future__ import annotations

import json, os, re
from pathlib import Path
from flask import Blueprint, jsonify, render_template, request, abort, send_file

from modules.replica.portable_sync_settings import load_sync_settings, save_sync_settings  # type: ignore
from modules.replica.portable_sync import index_current, set_offer, get_offer, pull_from_peer, activate_version  # type: ignore
from modules.replica.portable_cas import cas_path, has_block  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_pr = Blueprint("portable_replica", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _is_local_ip(ip: str) -> bool:
    return bool(re.match(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[0-1])\.)", ip or ""))

@bp_pr.get("/admin/portable/replica")
def page():
    return render_template("portable_replica.html", ab=AB)

@bp_pr.get("/admin/portable/replica/status")
def api_status():
    s = load_sync_settings()
    off = get_offer()
    return jsonify({"ok": True, "ab": AB, "settings": s, "offer": off})

@bp_pr.post("/admin/portable/replica/index")
def api_index():
    s = load_sync_settings()
    if AB != "B":
        man = index_current(s["base_dir"], s["cas_dir"], s["block_mb"])
        return jsonify({"ok": True, "dry": True, "manifest": {"version": man.get("version"), "blocks": len(man.get("blocks",{})), "total_bytes": man.get("total_bytes")}})
    man = index_current(s["base_dir"], s["cas_dir"], s["block_mb"])
    return jsonify({"ok": True, "manifest": man})

@bp_pr.post("/admin/portable/replica/offer")
def api_offer():
    s = load_sync_settings()
    man = index_current(s["base_dir"], s["cas_dir"], s["block_mb"])  # garantiruem nalichie CAS
    rep = set_offer(man)
    return jsonify({"ok": True, "result": rep})

@bp_pr.post("/admin/portable/replica/pull")
def api_pull():
    s = load_sync_settings()
    body = request.get_json(silent=True) or {}
    peer = (body.get("peer") or "").strip()
    if not peer: return jsonify({"ok": False, "error": "no-peer"}), 400
    target = Path(os.path.expanduser(s["base_dir"])) / "replica" / "from_peer"
    target.parent.mkdir(parents=True, exist_ok=True)
    token = s.get("token","")
    rep = pull_from_peer(peer, s["cas_dir"], str(target), token=token)
    return jsonify({"ok": bool(rep.get("ok")), "result": rep})

@bp_pr.post("/admin/portable/replica/activate")
def api_activate():
    s = load_sync_settings()
    body = request.get_json(silent=True) or {}
    version = (body.get("version") or "").strip()
    health_cmd = str(body.get("health_cmd") or "")
    if not version: return jsonify({"ok": False, "error": "no-version"}), 400
    if AB != "B":
        return jsonify({"ok": True, "dry": True, "version": version})
    rep = activate_version(s["base_dir"], version, health_cmd=health_cmd)
    return jsonify({"ok": bool(rep.get("ok")), "result": rep})

# ---------- P2P endpoints ----------
@bp_pr.get("/lan/portable/manifest")
def p2p_manifest():
    s = load_sync_settings()
    # simple protection: by default, allows only from the local network; for a given token - requires it.
    if s.get("token"):
        if request.headers.get("X-Ester-Token","") != s["token"]:
            return abort(401)
    else:
        if not _is_local_ip(request.remote_addr or ""):
            return abort(403)
    off = get_offer()
    return jsonify(off)

@bp_pr.get("/lan/portable/block/<sha>")
def p2p_block(sha: str):
    s = load_sync_settings()
    if s.get("token"):
        if request.headers.get("X-Ester-Token","") != s["token"]:
            return abort(401)
    else:
        if not _is_local_ip(request.remote_addr or ""):
            return abort(403)
    if not re.fullmatch(r"[a-fA-F0-9]{64}", sha or ""):
        return abort(400)
    if not has_block(s["cas_dir"], sha):
        return abort(404)
    path = cas_path(s["cas_dir"], sha)
    return send_file(str(path), mimetype="application/octet-stream")
    
def register_portable_replica(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_pr)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("portable_replica_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/portable/replica")
        def _p(): return page()

        @pref.get("/admin/portable/replica/status")
        def _s(): return api_status()

        @pref.post("/admin/portable/replica/index")
        def _i(): return api_index()

        @pref.post("/admin/portable/replica/offer")
        def _o(): return api_offer()

        @pref.post("/admin/portable/replica/pull")
        def _pl(): return api_pull()

        @pref.post("/admin/portable/replica/activate")
        def _a(): return api_activate()

        @pref.get("/lan/portable/manifest")
        def _lm(): return p2p_manifest()

        @pref.get("/lan/portable/block/<sha>")
        def _lb(sha): return p2p_block(sha)

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_pr)
    return app