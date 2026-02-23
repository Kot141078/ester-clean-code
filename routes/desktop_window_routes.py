# -*- coding: utf-8 -*-
"""
routes/desktop_window_routes.py - REST-pult okon/goryachikh klavish.

Ruchki:
  GET  /desktop/window/list
  POST /desktop/window/focus {"id":12345}  | {"title":"Bloknot"}
  POST /desktop/window/capture {"id":12345}  -> {ok, png_b64}
  POST /desktop/window/hotkey {"seq":"CTRL+S"} -> {ok}

MOSTY:
- Yavnyy: (Okno ↔ Deystvie) vybor tseli, fokus, zum.
- Skrytyy #1: (Zrenie ↔ Infoteoriya) zakhvat okna umenshaet shum dlya shablonov/OCR.
- Skrytyy #2: (Kibernetika ↔ Volya) goryachaya klavisha kak bystraya komanda.

ZEMNOY ABZATs:
Bez pravok agenta: rabotaem cherez Win32/X11 utility. Vse lokalno.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from typing import Any, Dict, Optional

from modules.ops.window_ops import list_windows, focus_by_id, focus_by_title, capture_by_id, send_hotkey
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("desktop_window_routes", __name__, url_prefix="/desktop/window")

@bp.route("/list", methods=["GET"])
def win_list():
    return jsonify({"ok": True, "items": list_windows()})

@bp.route("/focus", methods=["POST"])
def win_focus():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    wid = data.get("id")
    title = (data.get("title") or "").strip()
    if wid is None and not title:
        return jsonify({"ok": False, "error": "id_or_title_required"}), 400
    ok = (focus_by_id(int(wid)) if wid is not None else (focus_by_title(title) is not None))
    return jsonify({"ok": bool(ok)}), (200 if ok else 400)

@bp.route("/capture", methods=["POST"])
def win_capture():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    wid = data.get("id")
    if wid is None:
        return jsonify({"ok": False, "error": "id_required"}), 400
    png = capture_by_id(int(wid))
    if not png:
        return jsonify({"ok": False, "error": "capture_failed"}), 500
    return jsonify({"ok": True, "png_b64": png})

@bp.route("/hotkey", methods=["POST"])
def win_hotkey():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    seq = (data.get("seq") or "").strip()
    if not seq:
        return jsonify({"ok": False, "error": "seq_required"}), 400
    ok = send_hotkey(seq)
    return jsonify({"ok": bool(ok)}), (200 if ok else 400)

def register(app):
    app.register_blueprint(bp)