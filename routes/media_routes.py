# -*- coding: utf-8 -*-
"""routes/media_routes.py - REST dlya work s video/audio: probe/fetch/subs/outline/ingest/watch/tick/status/list/get/text/sync + registratsiya deystviy.

Mosty:
- Yavnyy: (Beb v†" Media) polnyy konveyer ot URL/fayla do pamyati, vklyuchaya metadannye/subtitry/konspekt.
- Skrytyy #1: (Memory v†" KG) kladet v pamyat Re svyazyvaet suschnosti.
- Skrytyy #2: (Volya v†" Geystviya) registriruem deystviya media.* v reestre mysley.
- Skrytyy #3: (Ostorozhnost v†" Kvoty) uvazhaet ingest-bakety.
- Skrytyy #4: (Profile v†" Audit) vse etapy shtampuyutsya v profile dlya polnoy pamyati.
- Novyy: (R aspredelennaya pamyat Ester v†" Sinkhronizatsiya) /sync dlya P2P-simulyatsii ingested media.

Zemnoy abzats:
Tri knopki: “proschupat”, “zabrat”, “posmotret” - Re chernovik konspekta uzhe v pamyati. S humor: Ester watch video bystree, chem ty morgaesh.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, send_file
import os
from typing import Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("media_routes", __name__)

# --- Importy moduley (obedinennye iz obeikh) ---
try:
    from modules.media.yt_dlp_wrapper import fetch as _fetch
    from modules.media.ingest_video import probe as _probe, extract_subs as _subs, outline_from as _outline, ingest as _ingest
    from modules.media.watch import tick as _watch_tick
    from modules.media.video_ingest import list_items as _list, get as _get, status as _status  # Iz pervoy
except Exception:
    _fetch = _probe = _subs = _outline = _ingest = _watch_tick = _list = _get = _status = None

def _check_availability():
    if any(fn is None for fn in [_fetch, _probe, _subs, _outline, _ingest, _watch_tick, _list, _get, _status]):
        return jsonify({"ok": False, "error": "media_unavailable"}), 500
    return None

def _rbac_write_ok() -> bool:
    """Checking RVACH for lie operations."""
    if os.getenv("RBAC_REQUIRED", "true").lower() == "false":
        return True
    try:
        from modules.auth.rbac import has_any_role
        return has_any_role(["admin", "operator"])
    except Exception:
        return True

def _log_passport(action: str, details: Dict[str, any]):
    """Logs in the profile for auditing in Esther (best-effort)."""
    try:
        from modules.mem.passport import append as _pp
        _pp(f"media_api_{action}", details, "media://routes")
    except Exception:
        pass

# --- Functions for registering in Vola (thinking) ---
def _act_fetch(d: Dict[str, any]) -> Dict[str, any]:
    url = str(d.get("url", ""))
    prefer = str(d.get("prefer", "video"))
    rep = _fetch(url, prefer)
    _log_passport("fetch", {"url": url[:100], "ok": rep["ok"]})
    return rep

def _act_subs(d: Dict[str, any]) -> Dict[str, any]:
    source = str(d.get("source", ""))
    prefer = str(d.get("prefer", "subs"))
    rep = _subs(source, prefer)
    _log_passport("subs", {"source": source[:100], "ok": rep["ok"]})
    return rep

def _act_outline(d: Dict[str, any]) -> Dict[str, any]:
    source = str(d.get("source", ""))
    k = int(d.get("k", 12))
    rep = _outline(source, k)
    _log_passport("outline", {"source": source[:100], "ok": rep["ok"]})
    return rep

def _act_ingest(d: Dict[str, any]) -> Dict[str, any]:
    if not _rbac_write_ok():
        return {"ok": False, "error": "forbidden"}
    source = str(d.get("source", ""))
    want_subs = bool(d.get("want_subtitles", True))
    want_stt = bool(d.get("want_stt", False))
    tags = d.get("tags", [])
    rep = _ingest(source, want_subs, want_stt, tags)
    _log_passport("ingest", {"source": source[:100], "ok": rep["ok"]})
    # Idea for Esther: P2P sync after ingestion
    if rep["ok"] and os.getenv("MEDIA_P2P_SYNC", "true").lower() == "true":
        _p2p_sync_sim(rep.get("id"))
    return rep

def _act_status(d: Dict[str, any]) -> Dict[str, any]:
    vid = str(d.get("id", ""))
    rep = _status(vid)
    _log_passport("status", {"id": vid, "ok": rep["ok"]})
    return rep

def _act_list(d: Dict[str, any]) -> Dict[str, any]:
    limit = int(d.get("limit", 50))
    rep = _list(limit)
    _log_passport("list", {"limit": limit, "items": len(rep.get("items", []))})
    return rep

def _p2p_sync_sim(media_id: str) -> None:
    """P2P simulation for a distributed airspace Ester (stub; expanded to real)."""
    try:
        from modules.p2p.bloom import add
        add([media_id])  # Add ID to bloom for deduplication during sync
        _log_passport("p2p_sync_sim", {"id": media_id})
    except Exception:
        pass

def register(app):
    """Registriruet blueprint i actions v Vole."""
    app.register_blueprint(bp)
    try:
        from modules.thinking.action_registry import register as areg
        areg("media.probe", {"source": "str"}, {"ok": "bool", "meta": "dict?"}, timeout_sec=30, fn=lambda d: _probe(str(d.get("source", ""))))
        areg("media.fetch", {"url": "str", "prefer": "str?"}, {"ok": "bool", "path": "str?"}, timeout_sec=60, fn=_act_fetch)
        areg("media.subs", {"source": "str", "prefer": "str?"}, {"ok": "bool", "path": "str?"}, timeout_sec=60, fn=_act_subs)
        areg("media.outline", {"source": "str", "k": "int?"}, {"ok": "bool", "bullets": "list"}, timeout_sec=60, fn=_act_outline)
        areg("media.ingest", {"source": "str", "want_subs": "bool?", "want_stt": "bool?", "tags": "list?"}, {"ok": "bool"}, timeout_sec=180, fn=_act_ingest)
        areg("media.status", {"id": "str"}, {"ok": "bool", "status": "dict?"}, timeout_sec=30, fn=_act_status)
        areg("media.list", {"limit": "int?"}, {"ok": "bool", "items": "list"}, timeout_sec=30, fn=_act_list)
    except Exception:
        pass

# --- Routes (combined and extended) ---
@bp.route("/media/probe", methods=["POST"])
def api_probe():
    unavailable = _check_availability()
    if unavailable: return unavailable
    d = request.get_json(silent=True) or {}
    source = str(d.get("source") or d.get("url") or d.get("path", ""))
    rep = _probe(source)
    _log_passport("probe", {"source": source[:100], "ok": rep["ok"]})
    return jsonify(rep)

@bp.route("/media/fetch", methods=["POST"])
def api_fetch():
    if not _rbac_write_ok(): return jsonify({"ok": False, "error": "forbidden"}), 403
    unavailable = _check_availability()
    if unavailable: return unavailable
    d = request.get_json(silent=True) or {}
    return jsonify(_act_fetch(d))

@bp.route("/media/subs", methods=["POST"])
def api_subs():
    if not _rbac_write_ok(): return jsonify({"ok": False, "error": "forbidden"}), 403
    unavailable = _check_availability()
    if unavailable: return unavailable
    d = request.get_json(silent=True) or {}
    return jsonify(_act_subs(d))

@bp.route("/media/outline", methods=["POST"])
def api_outline():
    if not _rbac_write_ok(): return jsonify({"ok": False, "error": "forbidden"}), 403
    unavailable = _check_availability()
    if unavailable: return unavailable
    d = request.get_json(silent=True) or {}
    return jsonify(_act_outline(d))

@bp.route("/media/ingest", methods=["POST"])
def api_ingest():
    unavailable = _check_availability()
    if unavailable: return unavailable
    d = request.get_json(silent=True) or {}
    return jsonify(_act_ingest(d))

@bp.route("/media/watch/tick", methods=["POST"])
def api_watch_tick():
    if not _rbac_write_ok(): return jsonify({"ok": False, "error": "forbidden"}), 403
    unavailable = _check_availability()
    if unavailable: return unavailable
    rep = _watch_tick()
    _log_passport("watch_tick", {"ok": rep["ok"]})
    return jsonify(rep)

@bp.route("/media/status", methods=["GET"])
def api_status():
    unavailable = _check_availability()
    if unavailable: return unavailable
    vid = str(request.args.get("id", ""))
    rep = _status(vid)
    _log_passport("status", {"id": vid, "ok": rep["ok"]})
    return jsonify(rep)

@bp.route("/media/list", methods=["GET"])
def api_list():
    unavailable = _check_availability()
    if unavailable: return unavailable
    limit = int(request.args.get("limit", "50"))
    rep = _list(limit)
    _log_passport("list", {"limit": limit, "items": len(rep.get("items", []))})
    return jsonify(rep)

@bp.route("/media/video/get", methods=["GET"])
def api_get():
    unavailable = _check_availability()
    if unavailable: return unavailable
    mid = str(request.args.get("id", ""))
    rep = _get(mid)
    _log_passport("get", {"id": mid, "ok": rep["ok"]})
    if not rep.get("ok"): return jsonify(rep), 404
    return jsonify(rep)

@bp.route("/media/video/text", methods=["GET"])
def api_text():
    unavailable = _check_availability()
    if unavailable: return unavailable
    mid = str(request.args.get("id", ""))
    kind = str(request.args.get("type", "notes"))
    rep = _get(mid)
    if not rep.get("ok"): return jsonify(rep), 404
    paths = rep["item"].get("paths") or {}
    file_map = {"subs": "subs.vtt", "transcript": "transcript.txt", "notes": "notes.md"}
    p = paths.get(kind, "")
    if not p or not os.path.isfile(p):
        guess = os.path.join(paths.get("dir", ""), file_map.get(kind, "notes.md"))
        if os.path.isfile(guess): p = guess
    if not p or not os.path.isfile(p):
        return jsonify({"ok": False, "error": "no_text"}), 404
    _log_passport("text", {"id": mid, "type": kind})
    return send_file(p, mimetype="text/plain; charset=utf-8")

@bp.route("/media/sync", methods=["POST"])
def api_sync():
    """New: Simulates P2P sync for ingested media."""
    if not _rbac_write_ok(): return jsonify({"ok": False, "error": "forbidden"}), 403
    d = request.get_json(silent=True) or {}
    media_id = str(d.get("id", ""))
    _p2p_sync_sim(media_id)
    rep = {"ok": True, "synced": True}
    _log_passport("sync", {"id": media_id})
    return jsonify(rep)

@bp.route("/media/help", methods=["GET"])
def api_help():
    rep = {
        "ok": True,
        "available": _check_availability() is None,
        "supports": {
            "ffprobe": "via FFPROBE_BIN or PATH",
            "ffmpeg": "via FFMPEG_BIN or PATH",
            "yt-dlp": "via module or YTDLP_BIN",
            "stt": "via MEDIA_STT_CMD with {wav}",
            "p2p_sync": "simulation; extend to real"
        }
    }
    _log_passport("help", {})
    return jsonify(rep)
