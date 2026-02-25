# -*- coding: utf-8 -*-
"""routes/video_ingest_routes.py - REST-obertka vokrug video-konveyera (URL/fayl v†' metadannye/subtitry/ASR v†' konspekt v†' pamyat).

Mosty:
- Yavnyy: (Memory v†" Interfeysy) HTTP-ruchki dayut polzovatelyu Re Ester edinyy vkhod k pamyati cherez ingest yadro.
- Skrytyy #1: (Kibernetika v†" Planirovschik) REST dopuskaet vyzov iz vnutrennikh zadach/skriptov bez novykh kontraktov.
- Skrytyy #2: (Infoteoriya v†" Inzheneriya) Edinyy format JSON-otveta snizhaet entropiyu integratsiy Re uproschaet otladku.

Zemnoy abzats:
Eto “universalnyy razem” na paneli: mozhno podat syre (URL/put), poluchit profile (meta), syre raspilit (ASR) Re report (summary) - vse temi zhe klyuchami.

# c=a+b"""
from __future__ import annotations

import os
from typing import Any, Dict

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Bezopasno importiruem yadro
try:
    from modules.ingest.video_ingest import ingest_video  # type: ignore
except Exception as e:
    ingest_video = None  # type: ignore

bp_video = Blueprint("video_ingest", __name__)

def _json_error(msg: str, code: int = 400):
    return jsonify({"ok": False, "error": msg}), code

@bp_video.route("/ingest/video/url", methods=["POST"])
def ingest_by_url():
    if ingest_video is None:
        return _json_error("video_ingest core is not available", 500)
    try:
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        url = (data.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            return _json_error("url is required and must be http(s)")
        want_meta = bool(data.get("meta", True))
        want_transcript = bool(data.get("transcript", False) or data.get("summary", False))
        want_summary = bool(data.get("summary", False))
        prefer_audio = bool(data.get("prefer_audio", True))
        chunk_ms = int(data.get("chunk_ms", 300000))
        rep = ingest_video(
            src=url,
            want_meta=want_meta,
            want_transcript=want_transcript,
            want_summary=want_summary,
            prefer_audio=prefer_audio,
            want_subs=True,
            chunk_ms=chunk_ms,
        )
        return jsonify(rep)
    except Exception as e:
        return _json_error(f"exception: {e}", 500)

@bp_video.route("/ingest/video/file", methods=["POST"])
def ingest_by_file():
    if ingest_video is None:
        return _json_error("video_ingest core is not available", 500)
    try:
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        path = (data.get("path") or "").strip()
        if not path:
            return _json_error("path is required")
        if not os.path.isfile(path):
            return _json_error(f"file not found: {path}", 404)
        want_meta = bool(data.get("meta", True))
        want_transcript = bool(data.get("transcript", False) or data.get("summary", False))
        want_summary = bool(data.get("summary", False))
        prefer_audio = bool(data.get("prefer_audio", False))
        chunk_ms = int(data.get("chunk_ms", 300000))
        rep = ingest_video(
            src=path,
            want_meta=want_meta,
            want_transcript=want_transcript,
            want_summary=want_summary,
            prefer_audio=prefer_audio,
            want_subs=True,
            chunk_ms=chunk_ms,
        )
        return jsonify(rep)
    except Exception as e:
        return _json_error(f"exception: {e}", 500)

@bp_video.route("/ingest/video/probe", methods=["GET"])
def ingest_probe():
    """Vystryy ffprobe: ?url=... ili ?path=... (meta-only)"""
    if ingest_video is None:
        return _json_error("video_ingest core is not available", 500)
    try:
        url = (request.args.get("url") or "").strip()
        path = (request.args.get("path") or "").strip()
        if url:
            src = url
        elif path:
            if not os.path.isfile(path):
                return _json_error(f"file not found: {path}", 404)
            src = path
        else:
            return _json_error("url or path is required")

        rep = ingest_video(
            src=src,
            want_meta=True,
            want_transcript=False,
            want_summary=False,
            prefer_audio=True,
            want_subs=True,
            chunk_ms=300000,
        )
        # Let's leave only the sample/source for compactness
        return jsonify({"ok": rep.get("ok", True), "source": rep.get("source"), "probe": rep.get("probe")})
    except Exception as e:
        return _json_error(f"exception: {e}", 500)

def register(app):
    """Podkhvatyvaetsya routes/register_all.py (drop-in)."""
# app.register_blueprint(bp_video)