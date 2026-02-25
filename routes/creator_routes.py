# -*- coding: utf-8 -*-
"""routes/creator_routes.py - REST: /creator/* (script/storyboard/compose)

Mosty:
- Yavnyy: (Veb ↔ Creator) knopki generatsii stsenariya/storiborda/sborki.
- Skrytyy #1: (Passport ↔ Trassirovka) vse art-shaga fiksiruyutsya.
- Skrytyy #2: (Uploader ↔ Metadannye) prigodno dlya posleduyuschey publikatsii.

Zemnoy abzats:
Neskolko POST - i u vas na diske gotovyy rolik. Minimum zavisimostey, maximum polzy.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("creator_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.creator.scriptgen import gen_script as _gen, storyboard as _sb  # type: ignore
    from modules.creator.compose import compose as _comp  # type: ignore
except Exception:
    _gen=_sb=_comp=None  # type: ignore

@bp.route("/creator/script", methods=["POST"])
def api_script():
    if _gen is None: return jsonify({"ok": False, "error":"creator_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_gen(str(d.get("topic","Tema")), str(d.get("style","shorts")), int(d.get("duration",60))))

@bp.route("/creator/storyboard", methods=["POST"])
def api_story():
    if _sb is None: return jsonify({"ok": False, "error":"creator_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_sb(str(d.get("script","")), int(d.get("shots",0) or 0)))

@bp.route("/creator/compose", methods=["POST"])
def api_compose():
    if _comp is None: return jsonify({"ok": False, "error":"creator_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_comp(list(d.get("images") or []), str(d.get("out","data/creator/out/out.mp4")), (str(d.get("audio","")) or None)))
# c=a+b