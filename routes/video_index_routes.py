# -*- coding: utf-8 -*-
"""
routes/video_index_routes.py - REST API dlya polnogo tsikla raboty s video:
ot indeksatsii do eksporta v RAG.

Endpointy:

Taymlayn-indeks i QA (vopros-otvet):
  • POST /video/index/build            {"dump":"data/video_ingest/rep_*.json"}
  • POST /video/index/from_source      {"url"|"path"[, "dump"]}
  • GET  /video/index/dumps
  • POST /video/qa/search              {"q":"...", "k":8, "scope":{"dump":"..."}}
  • GET  /video/index/chapters         ?dump=...&force=0
  • POST /video/index/summarize_window {"dump":..., "start":..., "end":..., "max_chars"?:700}

Eksport v vektornyy indeks (RAG):
  • POST /ingest/video/index/recent    {limit?:int, prefer_summary?:bool}
  • GET  /ingest/video/index/state

Metriki i UI:
  • GET  /metrics/video_index
  • GET  /ui/video/qa                  - UI dlya QA po video
  • GET  /admin/video/index            - UI-panel dlya upravleniya indeksatsiey

Mosty:
- Yavnyy: (Video ↔ Poisk ↔ Memory) udobnye ruchki dlya segmentatsii, QA, polucheniya glav
  i posleduyuschego perenosa konspektov v RAG-sloy.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) ustoychivye kontrakty API i fallback JSONL-ochered
  garantiruyut, chto dannye ne poteryayutsya.
- Skrytyy #2: (UX ↔ Obyasnimost) rezultaty poiska i glavy soderzhat taymkody i ssylki,
  chtoby proverit kontekst odnim klikom.
- Skrytyy #3: (Kibernetika ↔ Operatsii) legkovesnyy REST pozvolyaet zapuskat indeksatsiyu
  i eksport iz planirovschika ili pravil myshleniya.

Zemnoy abzats:
Eto polnyy konveyer «ot rolika do otveta». Snachala rabotaet «panel rezki i zakladok»: video
indeksiruetsya, narezaetsya na glavy, a lyuboy fragment mozhno bystro summarizirovat. Zatem «lift» perenosit
gotovye teksty i konspekty so sklada (dampy) na polku kataloga (vektornyy indeks), delaya ikh dostupnymi
dlya RAG-poiska.

# c=a+b
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from flask import Blueprint, Response, jsonify, request, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- Sektsiya taymlayn-indeksa, glav i QA po video ---

bp_vid_index = Blueprint("video_timeline_index", __name__, template_folder="../templates", static_folder="../static")

# Myagkie importy
try:
    from modules.video.index.timeline_index import build_index, list_dumps, qa_scope_filter  # type: ignore
except Exception:
    build_index = list_dumps = qa_scope_filter = None  # type: ignore

try:
    from modules.search.hybrid_retriever import hybrid_search  # type: ignore
except Exception:
    hybrid_search = None  # type: ignore

try:
    from modules.video.extractors.universal import fetch as uni_fetch  # type: ignore
except Exception:
    uni_fetch = None  # type: ignore

try:
    from modules.video.index.auto_chapters import build_chapters as _build_chapters  # type: ignore
except Exception:
    _build_chapters = None  # type: ignore

try:
    from modules.video.index.window_summary import summarize as _summarize_window  # type: ignore
except Exception:
    _summarize_window = None  # type: ignore

_STATE = os.path.join("data", "video_ingest", "index", "state.json")


@bp_vid_index.post("/video/index/build")
def api_build():
    if build_index is None:
        return jsonify({"ok": False, "error": "timeline_index unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    dump = (data.get("dump") or "").strip()
    if not dump or not os.path.isfile(dump):
        return jsonify({"ok": False, "error": "dump file required"}), 400
    try:
        rep = build_index(dump)  # type: ignore[misc]
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_vid_index.post("/video/index/from_source")
def api_from_source():
    if build_index is None:
        return jsonify({"ok": False, "error": "timeline_index unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    url = (data.get("url") or "").strip()
    path = (data.get("path") or "").strip()
    if not url and not path and not data.get("dump"):
        return jsonify({"ok": False, "error": "url or path required"}), 400

    dump = data.get("dump")
    if not dump:
        if uni_fetch is None:
            return jsonify({"ok": False, "error": "universal extractor unavailable"}), 500
        # Esli ukazan put - prosim subtitry/summary/meta
        want = {"subs": True, "summary": True, "meta": True}
        try:
            rep = uni_fetch({"url": url} if url else {"path": path, "want": want})  # type: ignore[misc]
        except Exception as e:
            return jsonify({"ok": False, "error": f"fetch failed: {e}"}), 500
        dump = rep.get("dump") if isinstance(rep, dict) else None
        if not dump:
            return jsonify({"ok": False, "error": "fetch failed", "detail": rep}), 500
    try:
        out = build_index(dump)  # type: ignore[misc]
        return jsonify(out if isinstance(out, dict) else {"ok": True, "result": out})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_vid_index.get("/video/index/dumps")
def api_dumps():
    if list_dumps is None:
        return jsonify({"ok": False, "error": "timeline_index unavailable"}), 500
    try:
        return jsonify({"ok": True, "dumps": list_dumps()})  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_vid_index.post("/video/qa/search")
def api_qa_search():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    q = (data.get("q") or "").strip()
    try:
        k = int(data.get("k") or 8)
    except Exception:
        k = 8
    scope = data.get("scope") or None
    if not q:
        return jsonify({"ok": False, "error": "q is required"}), 400
    if hybrid_search is None or qa_scope_filter is None:
        return jsonify({"ok": False, "error": "hybrid search unavailable"}), 500
    try:
        rep = hybrid_search(q=q, k=max(16, k))  # type: ignore[misc]
        items = (rep.get("items") or []) if isinstance(rep, dict) else []
        items = qa_scope_filter(items, scope)  # type: ignore[misc]
        items = items[:k]
        return jsonify({"ok": True, "mode": rep.get("mode") if isinstance(rep, dict) else None, "items": items})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_vid_index.get("/video/index/chapters")
def api_chapters():
    if _build_chapters is None:
        return jsonify({"ok": False, "error": "chapters unavailable"}), 500
    dump = (request.args.get("dump") or "").strip()
    if not dump or not os.path.isfile(dump):
        return jsonify({"ok": False, "error": "dump file required"}), 400
    try:
        force = bool(int(request.args.get("force", "0")))
    except Exception:
        force = False
    try:
        rep = _build_chapters(dump, force=force)  # type: ignore[misc]
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_vid_index.post("/video/index/summarize_window")
def api_summarize_window():
    if _summarize_window is None:
        return jsonify({"ok": False, "error": "window summary unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    dump = (data.get("dump") or "").strip()
    if not dump or not os.path.isfile(dump):
        return jsonify({"ok": False, "error": "dump file required"}), 400
    try:
        start = float(data.get("start"))
        end = float(data.get("end"))
    except Exception:
        return jsonify({"ok": False, "error": "start/end required as numbers"}), 400
    try:
        max_chars = int(data.get("max_chars") or 700)
    except Exception:
        max_chars = 700
    try:
        rep = _summarize_window(dump, start, end, max_chars=max_chars)  # type: ignore[misc]
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_vid_index.get("/metrics/video_index")
def metrics():
    # Vozvraschaem metriki s nulyami, esli fayl sostoyaniya otsutstvuet
    if not os.path.isfile(_STATE):
        body = (
            "video_index_segments_total 0\n"
            "video_index_dumps_indexed_total 0\n"
            "video_index_chapters_total 0\n"
            "video_index_last_ts 0\n"
        )
        return Response(body, mimetype="text/plain; version=0.0.4; charset=utf-8")
    try:
        with open(_STATE, "r", encoding="utf-8") as f:
            st = json.load(f)
    except Exception:
        st = {}
    lines = [
        f"video_index_segments_total {int(st.get('segments_total', 0))}",
        f"video_index_dumps_indexed_total {int(st.get('dumps_indexed_total', 0))}",
        f"video_index_chapters_total {int(st.get('video_index_chapters_total', 0))}",
        f"video_index_last_ts {int(st.get('ts', 0))}",
    ]
    return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4; charset=utf-8")


@bp_vid_index.get("/ui/video/qa")
def ui_video_qa():
    return render_template("video_qa.html")


@bp_vid_index.get("/admin/video/index")
def admin_video_index():
    return render_template("admin_video_index.html")


# --- Sektsiya eksporta v vektornyy indeks (RAG) ---

bp_video_ingest_index = Blueprint("video_ingest_index", __name__)

try:
    from modules.indexers.video_vector_indexer import export_recent_to_vectors, queue_size, fallback_path  # type: ignore
except Exception:
    export_recent_to_vectors = queue_size = fallback_path = None  # type: ignore


def _err(msg: str, code: int = 400):
    return jsonify({"ok": False, "error": msg}), code


@bp_video_ingest_index.post("/ingest/video/index/recent")
def api_index_recent():
    if export_recent_to_vectors is None:
        return _err("indexer not available", 500)
    try:
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        limit = int(data.get("limit") or 20)
        prefer_summary = bool(data.get("prefer_summary", True))
    except Exception:
        limit, prefer_summary = 20, True
    try:
        rep = export_recent_to_vectors(limit=limit, prefer_summary=prefer_summary)  # type: ignore[misc]
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return _err(f"exception: {e}", 500)


@bp_video_ingest_index.get("/ingest/video/index/state")
def api_index_state():
    if queue_size is None or fallback_path is None:
        return _err("indexer not available", 500)
    try:
        return jsonify({"ok": True, "queue_size": int(queue_size()), "fallback": fallback_path()})  # type: ignore[misc]
    except Exception as e:
        return _err(f"exception: {e}", 500)


# --- Registratsiya vsekh endpointov ---

def register(app):
    """Registriruet oba Blueprint'a v prilozhenii Flask."""
    app.register_blueprint(bp_vid_index)
    app.register_blueprint(bp_video_ingest_index)


def init_app(app):  # pragma: no cover
    register(app)


__all__ = ["bp_vid_index", "bp_video_ingest_index", "register", "init_app"]
# c=a+b