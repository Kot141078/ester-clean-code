# -*- coding: utf-8 -*-
"""routes/video_universal_routes.py - HTTP-ruchki universalnogo videokonveyera.

Endpoint:
  • GET /ingest/video/universal/probe?url=...|path=...
  • POST /ingest/video/universal/fetch {"url"|"path", "want":{...}, "lang"?:...}

Mosty:
- Yavnyy: (Bideo v†" Memory) pryamoy dostup k metadannym/sabam/chernoviku.
- Skrytyy #1: (Infoteoriya v†" Nadezhnost) probe bezopasen - ne kachaet bolshie bayty.
- Skrytyy #2: (Kibernetika v†" Volya) rabotaet kak po zaprosu, tak Re po triggeram myshleniya.

Zemnoy abzats:
Eto udobnye “ruchki kombayna”: proveril i snyal urozhay (profile, subtitry, vyzhimku).

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_vid_uni = Blueprint("video_universal", __name__)

try:
    from modules.video.metadata.ffprobe_ex import probe  # type: ignore
    from modules.video.extractors.universal import fetch  # type: ignore
except Exception:
    probe = fetch = None  # type: ignore

def register(app):
    app.register_blueprint(bp_vid_uni)

@bp_vid_uni.route("/ingest/video/universal/probe", methods=["GET"])
def api_probe():
    if probe is None:
        return jsonify({"ok": False, "error": "ffprobe_ex unavailable"}), 500
    url = (request.args.get("url") or "").strip()
    path = (request.args.get("path") or "").strip()
    if not url and not path:
        return jsonify({"ok": False, "error": "url or path required"}), 400
    return jsonify(probe({"url": url} if url else {"path": path}))

@bp_vid_uni.route("/ingest/video/universal/fetch", methods=["POST"])
def api_fetch():
    if fetch is None:
        return jsonify({"ok": False, "error": "universal extractor unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
# return jsonify(fetch(data))