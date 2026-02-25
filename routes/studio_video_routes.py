# -*- coding: utf-8 -*-
"""routes/studio_video_routes.py - REST: komponovka i spiski video/shablonov.

Mosty:
- Yavnyy: (Veb ↔ Kompozer) knopka “sobrat rolik”, plyus inventory gotovykh mp4 i shablonov.
- Skrytyy #1: (Studiya ↔ Sotsdeploy) itogovye mp4 v STUDIO_OUT avtomaticheski vidny /social/kit.
- Skrytyy #2: (Memory ↔ Profile) modul pishet “profile” sborki.

Zemnoy abzats:
Eto kak “eksport iz montazhki”: odnoy ruchkoy sdelali rolik, drugoy - uvideli vse result.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os, glob
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("studio_video_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.studio.video_compose import compose as _compose, list_templates as _tpls  # type: ignore
except Exception:
    _compose=_tpls=None  # type: ignore

@bp.route("/studio/video/compose", methods=["POST"])
def api_compose():
    if _compose is None: return jsonify({"ok": False, "error":"video_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_compose(
        str(d.get("title","Untitled")),
        str(d.get("aspect","9x16")),
        (d.get("template") if d.get("template") not in ("",None) else None),
        (None if d.get("subs") in (None,"",False) else (None if d.get("subs")=="auto" else str(d.get("subs")))),
        (None if d.get("audio") in (None,"",False) else str(d.get("audio"))),
        (None if d.get("video") in (None,"",False) else str(d.get("video"))),
        (None if d.get("background") in (None,"",False) else str(d.get("background"))),
        int(d.get("duration_sec",0)) if d.get("duration_sec") else None
    ))

@bp.route("/studio/video/list", methods=["GET"])
def api_list():
    root=os.getenv("STUDIO_OUT","data/studio/out")
    xs=sorted(glob.glob(root+"/*.mp4"))
    return jsonify({"ok": True, "items": xs})

@bp.route("/studio/video/templates", methods=["GET"])
def api_tpls():
    if _tpls is None: return jsonify({"ok": False, "error":"video_unavailable"}), 500
    return jsonify({"ok": True, "items": _tpls()})
# c=a+b