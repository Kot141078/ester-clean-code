# -*- coding: utf-8 -*-
"""
routes/releases_routes.py - admin-stranitsy i JSON dlya relizov/samosborki.

Endpointy:
  GET  /admin/releases             - HTML-stranitsa (templates/releases_admin.html)
  GET  /admin/releases/json        - spisok relizov, lokalnye/usb arkhivy, sostoyanie current
  POST /admin/releases/activate    - aktivirovat reliz po CID ili po puti k arkhivu
  POST /admin/releases/usb_sync    - sinkhronizatsiya s USB (pull ili dvustoronnyaya)

Bezopasnost:
  • /activate - trebuet kvorum ili odinochnyy approval (minimum: odin approval).

Mosty:
- Yavnyy: (DevOps ↔ UI) chelovek vklyuchaet nuzhnyy sborochnyy slepok cherez ponyatnuyu veb-panel.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) spisok arkhivov beretsya lokalno - menshe vneshnikh tochek otkaza.
- Skrytyy #2: (Kibernetika ↔ Kontrol) kvorum-«pilyulya» prepyatstvuet oshibochnomu deployu odnim klikom.

Zemnoy abzats (inzheneriya/anatomiya):
Eto «pereklyuchatel slepkov»: vybiraem arkhiv (po CID ili faylu) i «peresobiraem organizm» iz nego
v tselevoy katalog zapuska. Uzkie mesta - USB/arkhivy i verifikatsiya kvoruma; vse ostalnoe - prostye
muskuly vvoda/vyvoda i akkuratnye sukhozhiliya kontraktov JSON.

# c=a+b
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from flask import Blueprint, jsonify, render_template, request
from flask_jwt_extended import jwt_required  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- Myagkie importy zavisimostey (stabilnost offlayn) ---
try:  # pragma: no cover
    from modules.safety.quorum import require_quorum  # type: ignore
except Exception:  # pragma: no cover
    def require_quorum(kind: str, scope: Dict[str, Any], tokens, threshold: int = 1):  # type: ignore
        """Fallback: trebuem khotya by odin token-approval."""
        return (bool(tokens) and len(list(tokens)) >= threshold, "fallback")
try:  # pragma: no cover
    from modules.selfmanage.archive import _archives_dir as _local_archives_dir  # type: ignore
except Exception:  # pragma: no cover
    def _local_archives_dir():  # type: ignore
        d = os.path.join("data", "archives")
        os.makedirs(d, exist_ok=True)
        return d
try:  # pragma: no cover
    from modules.selfmanage.dump_assembler import assemble_from_archive  # type: ignore
except Exception:  # pragma: no cover
    def assemble_from_archive(arc, target_parent=None, require_token=False):  # type: ignore
        return {"ok": False, "error": "assemble_unavailable"}
try:  # pragma: no cover
    from modules.selfmanage.release_registry import ReleaseRegistry  # type: ignore
except Exception:  # pragma: no cover
    class ReleaseRegistry:  # type: ignore
        def list_releases(self, limit: int = 200):
            return []
        def record_activation(self, cid: str):
            return True
        def record_release(self, cid: str):
            return True
try:  # pragma: no cover
    from modules.selfmanage.relocator import _state_file as _relocate_state_file  # type: ignore
except Exception:  # pragma: no cover
    def _relocate_state_file():  # type: ignore
        return os.path.join("data", "selfmanage", "relocate_state.json")
try:  # pragma: no cover
    from modules.selfmanage.usb_sync import sync as usb_sync  # type: ignore
except Exception:  # pragma: no cover
    def usb_sync(usb_mount=None, push_to_usb=False):  # type: ignore
        return {"ok": False, "error": "usb_sync_unavailable"}

releases_bp = Blueprint("releases_admin", __name__, url_prefix="/admin/releases")


def _list_local_archives() -> Dict[str, str]:
    """Vozvraschaet slovar {cid: path} po lokalnoy papke arkhivov."""
    d = _local_archives_dir()
    out: Dict[str, str] = {}
    try:
        for name in os.listdir(d):
            if name.endswith(".zip"):
                cid = name[:-4]
                out[cid] = os.path.join(d, name)
    except Exception:
        pass
    return out


def _current_state() -> Dict[str, Any]:
    """Chitaet sostoyanie tekuschego «perenosa» reliza (esli bylo)."""
    p = _relocate_state_file()
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


@releases_bp.get("/")
@jwt_required()
def page():
    """HTML-stranitsa upravleniya relizami."""
    return render_template("releases_admin.html")


@releases_bp.get("/json")
@jwt_required()
def json_list():
    """JSON-svodka po relizam i lokalnym arkhivam + tekuschee sostoyanie."""
    rr = ReleaseRegistry()
    try:
        nodes = rr.list_releases(limit=500)
    except Exception:
        nodes = []
    local_archives = _list_local_archives()
    return jsonify({"ok": True, "releases": nodes, "local_archives": local_archives, "current": _current_state()})


@releases_bp.post("/activate")
@jwt_required()
def activate():
    """Aktivirovat reliz po CID ili puti k arkhivu (s proverkoy kvoruma)."""
    data = request.get_json(force=True, silent=True) or {}
    cid = (data.get("cid") or "").strip()
    path = (data.get("path") or "").strip()
    target_parent = str(data.get("target_parent") or (os.getenv("ESTER_RUN_ROOT") or os.getcwd()))

    approvals = data.get("approvals") or []
    ok, why = require_quorum(
        kind="assemble",
        scope={"action": "assemble"},
        tokens=approvals,
        threshold=int(data.get("threshold") or 1),
    )
    if not ok:
        return jsonify({"ok": False, "error": f"quorum failed: {why}"}), 403

    # opredelit put k arkhivu
    arc = None
    if path:
        arc = path
    elif cid:
        local = _list_local_archives()
        arc = local.get(cid)
        if not arc:
            return jsonify({"ok": False, "error": f"local archive for cid {cid} not found"}), 404
    else:
        return jsonify({"ok": False, "error": "cid or path required"}), 400

    # aktivatsiya
    try:
        res = assemble_from_archive(arc, target_parent=target_parent, require_token=False)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    if isinstance(res, dict) and res.get("ok"):
        try:
            rr = ReleaseRegistry()
            rr.record_activation(res.get("cid", ""))
            rr.record_release(res.get("cid", ""))
        except Exception:
            pass
    code = 200 if isinstance(res, dict) and res.get("ok") else 400
    return jsonify(res if isinstance(res, dict) else {"ok": False, "error": "bad response"}), code


@releases_bp.post("/usb_sync")
@jwt_required()
def do_usb_sync():
    """Zapusk sinkhronizatsii relizov s USB-nositelem (pull/dvustoronnyaya)."""
    data = request.get_json(force=True, silent=True) or {}
    mount = data.get("mount") or None
    push = bool(data.get("push_to_usb") or False)
    try:
        rep = usb_sync(usb_mount=mount, push_to_usb=push)
    except Exception as e:
        rep = {"ok": False, "error": str(e)}
    return jsonify(rep), (200 if isinstance(rep, dict) and rep.get("ok") else 400)


def register_releases_routes(app) -> None:  # pragma: no cover
    """Istoricheskaya registratsiya blyuprinta (sovmestimost s dampom)."""
    app.register_blueprint(releases_bp)


# Unifitsirovannye khuki proekta
def register(app) -> None:  # pragma: no cover
    app.register_blueprint(releases_bp)


def init_app(app) -> None:  # pragma: no cover
    app.register_blueprint(releases_bp)


__all__ = ["releases_bp", "register_releases_routes", "register", "init_app"]
# c=a+b


def register(app):
    app.register_blueprint(releases_bp)
    return app