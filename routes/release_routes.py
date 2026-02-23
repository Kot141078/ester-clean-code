# -*- coding: utf-8 -*-
"""
routes/release_routes.py - REST: snepshot sborki i .torrent dlya distributsii.

Ruchki:
  POST /release/snapshot  {"roots":["src","web"],"name":"ester"} -> {"ok":true,...}
  POST /release/torrent   {"manifest":"path/to/manifest.json","announce":["udp://..."]}

Mosty:
- Yavnyy: (Veb ↔ Reliz) gotovim manifest/arkhiv i .torrent cherez edinyy REST.
- Skrytyy #1: (Integratsiya ↔ Trust) manifest prigoden dlya podpisi i proverki tselostnosti.
- Skrytyy #2: (Ustoychivost ↔ Bekap) .torrent oblegchaet P2P-rasprostranenie i rassharivanie uzlov.

Zemnoy abzats:
Odin zapros - i u tebya na rukakh proveryaemaya «sborka» i torrent dlya razdachi po seti. Prozrachno i bystro.

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_rel = Blueprint("release_routes", __name__)

# Myagkiy import yadra relizov
try:
    from modules.release.packager import snapshot as _snap, make_torrent as _tor  # type: ignore
except Exception:  # pragma: no cover
    _snap = _tor = None  # type: ignore


def register(app):  # pragma: no cover
    app.register_blueprint(bp_rel)


def init_app(app):  # pragma: no cover
    register(app)


@bp_rel.route("/release/snapshot", methods=["POST"])
def api_snap():
    """Sobrat snepshot: manifest + arkhiv (realizatsiya delegirovana _snap)."""
    if _snap is None:
        return jsonify({"ok": False, "error": "release_unavailable"}), 500
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    roots = d.get("roots", [])
    name = str(d.get("name", "ester")).strip() or "ester"

    if not isinstance(roots, list):
        return jsonify({"ok": False, "error": "roots must be a list"}), 400
    try:
        roots_list: List[str] = [str(x) for x in roots]
        rep = _snap(roots_list, name)  # type: ignore[misc]
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_rel.route("/release/torrent", methods=["POST"])
def api_tor():
    """Sgenerirovat .torrent na osnove manifesta (delegirovano _tor)."""
    if _tor is None:
        return jsonify({"ok": False, "error": "release_unavailable"}), 500
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    manifest = str(d.get("manifest", "")).strip()
    announce = d.get("announce", [])

    if not manifest:
        return jsonify({"ok": False, "error": "manifest is required"}), 400
    if not isinstance(announce, list):
        return jsonify({"ok": False, "error": "announce must be a list"}), 400

    try:
        ann_list: List[str] = [str(x) for x in announce]
        rep = _tor(manifest, ann_list)  # type: ignore[misc]
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


__all__ = ["bp_rel", "register", "init_app"]
# c=a+b