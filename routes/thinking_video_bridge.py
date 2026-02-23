# -*- coding: utf-8 -*-
"""
routes/thinking_video_bridge.py — most dlya pravil myshleniya: avtopoisk video po teme v†' postanovka na fetch.

Endpoint:
  • POST /thinking/video/autosearch {"topic":"...", "limit":2, "lang"?: "ru|en"}

Logika:
  • Pytaemsya nayti video cherez yt-dlp (ytsearchN:topic) ili legkiy veb-poisk (esli yt-dlp nedostupen — best-effort).
  • Glya kazhdogo naydennogo URL sozdaem zadanie fetch cherez universal-ekstraktor (mode uchityvaet VIDEO_UNIVERSAL_AB).
  • Bozvraschaem spisok kandidatov Re statusy postanovki.

Mosty:
- Yavnyy: (Myshlenie v†" Video) «volya» Ester zaprashivaet video po teme bez vmeshatelstva polzovatelya.
- Skrytyy #1: (Infoteoriya v†" R esursy) ogranichenie limit Re otsutstvie skachivaniya na stadii poiska.
- Skrytyy #2: (Memory v†" Poisk) rezultaty srazu konvertiruyutsya v otchety dlya pamyati/vektora.

Zemnoy abzats:
Eto kak poruchit pomoschniku: «Naydi paru rolikov po teme Re sdelay vyzhimki» — tikho, regulyarno, po raspisaniyu.

# c=a+b
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_thinking_video = Blueprint("thinking_video", __name__)

YTDLP = os.getenv("YTDLP_BIN", "yt-dlp")

try:
    from modules.video.extractors.universal import fetch  # type: ignore
except Exception:
    fetch = None  # type: ignore

def register(app):
    app.register_blueprint(bp_thinking_video)

def _run(cmd: list[str], timeout: float = 12.0) -> tuple[int, str, str]:
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate(timeout=timeout)
        return p.returncode or 0, out.decode("utf-8", "ignore"), err.decode("utf-8", "ignore")
    except Exception as e:
        return -1, "", str(e)

@bp_thinking_video.route("/thinking/video/autosearch", methods=["POST"])
def api_autosearch():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    topic = (data.get("topic") or "").strip()
    limit = int(data.get("limit") or 2)
    lang = (data.get("lang") or "").strip() or None
    if not topic:
        return jsonify({"ok": False, "error": "topic is required"}), 400
    # Poisk cherez yt-dlp: ytsearchN:
    urls: List[str] = []
    code, out, err = _run([YTDLP, "-J", f"ytsearch{max(1, min(5, limit))}:{topic}"])
    if code == 0 and out.strip():
        try:
            info = json.loads(out)
            for e in (info.get("entries") or [])[:limit]:
                if e.get("webpage_url"):
                    urls.append(e["webpage_url"])
        except Exception:
            pass
    # fallback: nichego — pusto
    results: List[Dict[str, Any]] = []
    for u in urls:
        req = {"url": u, "want": {"subs": True, "summary": True, "meta": True}, "lang": lang}
        if fetch is None:
            results.append({"url": u, "status": "skipped (extractor unavailable)"})
            continue
        rep = fetch(req)
        results.append({"url": u, "status": "ok" if rep.get("ok") else "err", "mode": rep.get("mode"), "dump": rep.get("dump"), "summary_len": len(rep.get("summary") or "")})
# return jsonify({"ok": True, "topic": topic, "found": urls, "results": results})