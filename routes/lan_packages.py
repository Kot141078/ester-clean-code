# -*- coding: utf-8 -*-
"""routes/lan_packages.py - LAN-katalog packages: publikatsiya index, download ZIP, fetch/verify/import s pirov.

Route:
  • GET /lan/packages - HTML
  • GET /lan/packages/index - lokalnyy indexes ZIP (ACL+throttle)
  • GET /lan/packages/download - skachat ZIP iz lokalnogo out/?name=
  • POST /lan/packages/fetch - zabrat ZIP s pira i (opts.) importirovat
  • POST /lan/packages/peers - sokhranit/prochitat spisok pirov

AB:
  • A - bez setevykh zagruzok/importa (tolko prevyu indeksa udalennogo uzla, esli dostupen, i lokalnye operatsii chteniya).
  • B - complete operatsii.

Mosty:
- Yavnyy (Operatsii ↔ Audit): perenos paketov po lokalke s temi zhe plombami/proverkami, chto i USB.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): ACL+throttle, verify pered import, vse determinirovano.
- Skrytyy 2 (Praktika ↔ Sovmestimost): stdlib urllib; JSON-kontrakty kak u USB-packetov.

Zemnoy abzats:
Eto “lokalnaya polka”: sosedi vidyat tvoi pakety i mogut ikh zabrat; ty - ikh. All v ramkakh lokalki i s predokhranitelyami.

# c=a+b"""
from __future__ import annotations
import json, os, urllib.parse, urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional
from flask import Blueprint, jsonify, render_template, request, send_file, abort

from modules.usb.recovery import list_usb_targets  # type: ignore
from modules.pack.catalog import build_local_index  # type: ignore
from modules.lan.acl import is_allowed_ip, load_acl  # type: ignore
from modules.lan.throttle import allow as throttle_allow  # type: ignore
from modules.pack.packager import verify_package, import_package  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_lanpkg = Blueprint("lan_packages", __name__)

STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
OUT_DIR = STATE_DIR / "packages" / "out"
INCOMING = STATE_DIR / "packages" / "incoming"
PEERSF = STATE_DIR / "lan_pkg_peers.json"
AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _client_ip() -> str:
    # S-Forwarded-For is not taken into account intentionally (local output).
    return request.remote_addr or "0.0.0.0"

@bp_lanpkg.get("/lan/packages")
def page():
    return render_template("lan_packages.html", ab=AB)

@bp_lanpkg.get("/lan/packages/index")
def index():
    ip = _client_ip()
    if not is_allowed_ip(ip): return jsonify({"ok": False, "error": "forbidden"}), 403
    ok, meta = throttle_allow(ip, inc=1)
    if not ok: return jsonify({"ok": False, "error": "too-many-requests", "meta": meta}), 429
    usb = list_usb_targets() or []
    mounts = [i.get("mount") for i in usb if i.get("mount")]
    idx = build_local_index(mounts)
    return jsonify({"ok": True, "ab": AB, "acl": load_acl(), "index": idx})

@bp_lanpkg.get("/lan/packages/download")
def download():
    ip = _client_ip()
    if not is_allowed_ip(ip): return jsonify({"ok": False, "error": "forbidden"}), 403
    ok, meta = throttle_allow(ip, inc=1)
    if not ok: return jsonify({"ok": False, "error": "too-many-requests", "meta": meta}), 429
    name = (request.args.get("name") or "").strip()
    if not name: return jsonify({"ok": False, "error": "name required"}), 400
    # We only give files from the local OT_DIR
    p = (OUT_DIR / name).resolve()
    if not str(p).startswith(str(OUT_DIR.resolve())) or not p.exists():
        return jsonify({"ok": False, "error": "not-found"}), 404
    return send_file(str(p), as_attachment=True, download_name=p.name)

@bp_lanpkg.post("/lan/packages/fetch")
def fetch():
    body = request.get_json(silent=True) or {}
    base = (body.get("base_url") or "").rstrip("/")
    name = (body.get("name") or "").strip()
    do_import = bool(body.get("import", False))
    mode = (body.get("mode") or "merge").strip()
    if not base or not name:
        return jsonify({"ok": False, "error": "base_url/name required"}), 400
    # dry v A
    if AB != "B":
        return jsonify({"ok": True, "dry": True, "base_url": base, "name": name, "import": do_import, "mode": mode})
    # skachivaem
    try:
        INCOMING.mkdir(parents=True, exist_ok=True)
        url = f"{base}/lan/packages/download?name={urllib.parse.quote(name)}"
        max_mb = max(1, int(os.getenv("LAN_PKG_MAX_FETCH_MB","1024")))
        req = urllib.request.Request(url, headers={"User-Agent":"EsterLAN/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
            if len(data) > max_mb * 1024 * 1024:
                return jsonify({"ok": False, "error":"too-large"}), 413
            out = INCOMING / name
            out.write_bytes(data)
        v = verify_package(str(out))
        if not v.get("ok"):
            return jsonify({"ok": False, "error": "verify-failed", "verify": v}), 400
        imp = {"ok": True}
        if do_import:
            imp = import_package(str(out), mode=mode)
        return jsonify({"ok": True, "download": str(out), "verify": v, "import": imp})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp_lanpkg.post("/lan/packages/peers")
def peers():
    # mode: get/set
    body = request.get_json(silent=True) or {}
    mode = (body.get("op") or "get").strip()
    if mode == "set":
        items = body.get("items") or []
        try:
            PEERSF.parent.mkdir(parents=True, exist_ok=True)
            PEERSF.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    # get
    try:
        if not PEERSF.exists(): return jsonify({"ok": True, "items": []})
        d = json.loads(PEERSF.read_text(encoding="utf-8"))
        return jsonify({"ok": True, "items": d.get("items", [])})
    except Exception:
        return jsonify({"ok": True, "items": []})

def register_lan_packages(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_lanpkg)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("lan_packages_pref", __name__, url_prefix=url_prefix)

        @pref.get("/lan/packages")
        def _p(): return page()

        @pref.get("/lan/packages/index")
        def _i(): return index()

        @pref.get("/lan/packages/download")
        def _d(): return download()

        @pref.post("/lan/packages/fetch")
        def _f(): return fetch()

        @pref.post("/lan/packages/peers")
        def _pe(): return peers()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_lanpkg)
    return app