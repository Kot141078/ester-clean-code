# -*- coding: utf-8 -*-
"""routes/lan_diagnostics.py - publikatsiya diagnostiki po lokalke: indexes/skachivanie/zabor i sliyanie.

Route:
  • GET /lan/diagnostics/index
  • GET /lan/diagnostics/download?kind=history|ticket&name=
  • POST /lan/diagnostics/fetch {base_url, kind, name, op:merge|copy}

AB:
  • A - sukhoy plan bez setevykh zagruzok/zapisey.
  • B - realnaya zagruzka/kopirovanie/sliyanie NDJSON.

Mosty:
- Yavnyy (Obmen ↔ Audit): otchety i istorii Self-Care dostupny sosedyam.
- Skrytyy 1 (Bezopasnost ↔ Nadezhnost): ACL+throttle; limit size download.
- Skrytyy 2 (Praktika ↔ Sovmestimost): stdlib urllib; te zhe guard'y, chto u LAN paketov.

Zemnoy abzats:
This is “polka diagnostiki”: sosed uvidit tvoi istorii/tikety i smozhet zabrat ikh dlya analiza/sliyaniya.

# c=a+b"""
from __future__ import annotations
import json, os, urllib.parse, urllib.request
from pathlib import Path
from typing import Any
from flask import Blueprint, jsonify, request, send_file

from modules.lan.acl import is_allowed_ip, load_acl  # type: ignore
from modules.lan.throttle import allow as throttle_allow  # type: ignore
from modules.diag.catalog import build_diag_index  # type: ignore
from modules.diag.merge import merge_history_file  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_landiag = Blueprint("lan_diagnostics", __name__)

STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
DIAG_DIR  = STATE_DIR / "diagnostics"
HIST_DIR  = DIAG_DIR / "history"
TIC_DIR   = DIAG_DIR  / "tickets"
INCOMING  = DIAG_DIR  / "incoming"
AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _client_ip():
    return request.remote_addr or "0.0.0.0"

@bp_landiag.get("/lan/diagnostics/index")
def index():
    ip = _client_ip()
    if not is_allowed_ip(ip): return jsonify({"ok": False, "error": "forbidden"}), 403
    ok, meta = throttle_allow(ip, inc=1)
    if not ok: return jsonify({"ok": False, "error": "too-many-requests", "meta": meta}), 429
    return jsonify({"ok": True, "ab": AB, "acl": load_acl(), "diag": build_diag_index()})

@bp_landiag.get("/lan/diagnostics/download")
def download():
    ip = _client_ip()
    if not is_allowed_ip(ip): return jsonify({"ok": False, "error": "forbidden"}), 403
    ok, meta = throttle_allow(ip, inc=1)
    if not ok: return jsonify({"ok": False, "error": "too-many-requests", "meta": meta}), 429
    kind = (request.args.get("kind") or "").strip()
    name = (request.args.get("name") or "").strip()
    if kind not in ("history","ticket") or not name:
        return jsonify({"ok": False, "error": "bad-args"}), 400
    root = HIST_DIR if kind=="history" else TIC_DIR
    p = (root / name).resolve()
    if not str(p).startswith(str(root.resolve())) or not p.exists():
        return jsonify({"ok": False, "error": "not-found"}), 404
    return send_file(str(p), as_attachment=True, download_name=p.name)

@bp_landiag.post("/lan/diagnostics/fetch")
def fetch():
    body = request.get_json(silent=True) or {}
    base = (body.get("base_url") or "").rstrip("/")
    kind = (body.get("kind") or "").strip()
    name = (body.get("name") or "").strip()
    op   = (body.get("op") or "merge").strip()  # merge|copy
    if not base or kind not in ("history","ticket") or not name:
        return jsonify({"ok": False, "error": "base/kind/name required"}), 400
    if AB != "B":
        return jsonify({"ok": True, "dry": True, "base_url": base, "kind": kind, "name": name, "op": op})
    try:
        INCOMING.mkdir(parents=True, exist_ok=True)
        url = f"{base}/lan/diagnostics/download?kind={urllib.parse.quote(kind)}&name={urllib.parse.quote(name)}"
        max_mb = max(1, int(os.getenv("LAN_DIAG_MAX_FETCH_MB","128")))
        req = urllib.request.Request(url, headers={"User-Agent":"EsterDiagLAN/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
            if len(data) > max_mb * 1024 * 1024:
                return jsonify({"ok": False, "error":"too-large"}), 413
            tmp = INCOMING / name
            tmp.write_bytes(data)
        if kind == "ticket" or op == "copy":
            dst = (TIC_DIR if kind=="ticket" else HIST_DIR) / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            Path(tmp).replace(dst)
            return jsonify({"ok": True, "copied": str(dst)})
        # kind==history and op==merge
        res = merge_history_file(str(tmp), name)
        tmp.unlink(missing_ok=True)
        return jsonify({"ok": True, "merged": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

def register_lan_diagnostics(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_landiag)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("lan_diagnostics_pref", __name__, url_prefix=url_prefix)

        @pref.get("/lan/diagnostics/index")
        def _i(): return index()

        @pref.get("/lan/diagnostics/download")
        def _d(): return download()

        @pref.post("/lan/diagnostics/fetch")
        def _f(): return fetch()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_landiag)
    return app