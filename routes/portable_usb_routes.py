# routes/portable_usb_routes.py
# -*- coding: utf-8 -*-
"""routes/portable_usb_routes.py - USB-ruchki dlya podgotovki nositelya (myagkaya zavisimost ot enterprise-modulya).

Mosty:
- Yavnyy (UI ↔ Portable/USB): UI “Sozdat fleshku” dergaet eti ruchki: spisok, podgotovka /ESTER, formatirovanie.
- Skrytyy #1 (Bezopasnost ↔ Ekspluatatsiya): esli modules.portable.usb otsutstvuet - vozvraschaem 501, not padaem.
- Skrytyy #2 (Profile ↔ Audit): pri nalichii passport logiruem operatsii polzovatelya.

Zemnoy abzats:
Daet REST-obertku vokrug nizkourovnevykh funktsiy work s USB. Import obernuty v try/except, poetomu sborki bez
enterprise-komponentov ne lomayutsya - UI poluchaet predskazuemye JSON-otvety.
# c=a+b"""
from __future__ import annotations

from typing import Dict, Any, List
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("portable_usb", __name__)

# ---- Optional imports (protected) ----
_list_roots = _prepare_root = _format_root = None  # podmenim pri udachnom importe

try:
    # Preferred enterprise module signature
    from modules.portable.usb import list_roots as _list_roots  # type: ignore
    from modules.portable.usb import prepare_root as _prepare_root  # type: ignore
    from modules.portable.usb import format_root as _format_root  # type: ignore
except Exception:
    # Poprobuem izvestnye alternativy imen
    try:
        from modules.portable.usb import ls as _list_roots  # type: ignore
    except Exception:
        pass
    try:
        from modules.portable.usb import prepare as _prepare_root  # type: ignore
    except Exception:
        pass
    try:
        from modules.portable.usb import fmt as _format_root  # type: ignore
    except Exception:
        pass

# ---- Profile (optsionalno) ----
def _passport_log(action: str, payload: Dict[str, Any]) -> None:
    try:
        from modules.mem.passport import append as passport  # type: ignore
        passport("portable_usb", {"action": action, **payload}, "ops://portable/usb")
    except Exception:
        pass

@bp.get("/self/usb/list")
def usb_list():
    if callable(_list_roots):
        try:
            roots = _list_roots()  # type: ignore[misc]
            _passport_log("list", {"n": len(roots) if isinstance(roots, list) else -1})
            return jsonify({"ok": True, "roots": roots})
        except Exception as e:
            return jsonify({"ok": False, "error": f"{e}"}), 500
    return jsonify({"ok": False, "error": "portable_unavailable"}), 501

@bp.post("/self/usb/prepare")
def usb_prepare():
    data = request.get_json(silent=True) or {}
    mount = data.get("mount") or ""
    if not mount:
        return jsonify({"ok": False, "error": "mount_required"}), 400
    if callable(_prepare_root):
        try:
            res = _prepare_root(mount)  # type: ignore[misc]
            _passport_log("prepare", {"mount": mount})
            return jsonify({"ok": True, "root": res if res is not None else mount})
        except Exception as e:
            return jsonify({"ok": False, "error": f"{e}"}), 500
    return jsonify({"ok": False, "error": "portable_unavailable"}), 501

@bp.post("/self/usb/format")
def usb_format():
    data = request.get_json(silent=True) or {}
    mount = data.get("mount") or ""
    fs = (data.get("fs") or "fat32").lower()
    if not mount:
        return jsonify({"ok": False, "error": "mount_required"}), 400
    if callable(_format_root):
        try:
            res = _format_root(mount, fs=fs)  # type: ignore[misc]
            _passport_log("format", {"mount": mount, "fs": fs})
            return jsonify({"ok": True, "root": res if res is not None else mount, "fs": fs})
        except Exception as e:
            return jsonify({"ok": False, "error": f"{e}"}), 500
    return jsonify({"ok": False, "error": "portable_unavailable"}), 501

def register_routes(app, seen_endpoints=None):
    app.register_blueprint(bp)


def register(app):
    app.register_blueprint(bp)
    return app