# -*- coding: utf-8 -*-
from __future__ import annotations

"""
routes/rag_doc_routes.py — vspomogatelnye ruchki dlya prosmotra syrykh dokumentov RAG.

MOSTY:
- Yavnyy: (Veb ↔ Memory) GET /rag/hybrid/doc vozvraschaet srez teksta po id iz docs.jsonl ili po pryamomu puti.
- Skrytyy №1: (Indeks ↔ FS) pri promakhe po indeksu pytaemsya doindeksirovat docs.jsonl i esche raz nayti id.
- Skrytyy №2: (FS ↔ Baypas) esli id pokhozh na put i fayl suschestvuet — chitaem fayl napryamuyu, keshiruya ego v protsesse.

ZEMNOY ABZATs (inzheneriya/anatomiya):
Eto «endoskop» v syruyu dokumentnuyu pamyat. Kak tekhnik: mozhno rukami proverit, chto RAG realno chitaet te fayly,
kotorye lezhat na diske, bez uchastiya modeley i «magii» poverkh.
Format indeksa: JSONL, po stroke na dokument vida {"id": "...", "text": "...", "meta": {...}}.
# c = a + b
"""

import os
import json
import threading
import re
from typing import Dict, Tuple, Optional, Any, List
from urllib.parse import unquote

from flask import Blueprint, request, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("rag_doc", __name__)

# -------- kesh i indeksy --------
_DOCS_LOCK = threading.Lock()
_DOCS: Dict[str, Tuple[str, Dict[str, Any]]] = {}   # original_id -> (text, meta)
_NORM_INDEX: Dict[str, str] = {}                    # norm_key -> original_id
_LOADED: bool = False

# Upravlyayuschie simvoly (vklyuchaya \r \n \t \x00)
_WS_RE = re.compile(r"[\u0000-\u001F\u007F]+")


# -------- utility normalizatsii/indeksa --------
def _norm_key(s: str) -> str:
    s = s.strip()
    s = s.replace("/", os.sep).replace("\\", os.sep)
    try:
        s = os.path.normpath(s)
    except Exception:
        pass
    try:
        s = os.path.normcase(s)
    except Exception:
        pass
    return s


def _clean_id_param(raw: Optional[str]) -> str:
    """
    strip → unquote → vykinut upravlyayuschie → snyat kavychki → normpath/normcase
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return s
    try:
        s = unquote(s)
    except Exception:
        pass
    s = _WS_RE.sub("", s)
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"', "`"):
        s = s[1:-1]
    try:
        s = s.replace("/", os.sep).replace("\\", os.sep)
        s = os.path.normpath(s)
    except Exception:
        pass
    try:
        s = os.path.normcase(s)
    except Exception:
        pass
    return s


def _index_put(oid: str, text: str, meta: Dict[str, Any]) -> None:
    key = _norm_key(oid)
    _DOCS[oid] = (text, meta or {})
    _NORM_INDEX[key] = oid


def _candidate_docs_paths() -> List[str]:
    res: List[str] = []

    env_p = os.environ.get("ESTER_MEM_DOCS_PATH")
    if env_p:
        res.append(env_p)

    dr = os.environ.get("ESTER_DATA_ROOT")
    if dr:
        res.append(os.path.join(dr, "mem", "docs.jsonl"))

    cwd = os.getcwd()
    res.append(os.path.join(cwd, "data", "mem", "docs.jsonl"))
    res.append(os.path.join(cwd, "mem", "docs.jsonl"))

    out: List[str] = []
    seen = set()
    for p in res:
        if not p:
            continue
        ap = os.path.abspath(p)
        nk = _norm_key(ap)
        if nk in seen:
            continue
        seen.add(nk)
        out.append(ap)
    return out


def _load_jsonl_into_cache(path: str) -> int:
    if not os.path.exists(path):
        return 0
    loaded = 0
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            rid = row.get("id")
            if not rid:
                continue
            rid_clean = _clean_id_param(str(rid))
            if not rid_clean:
                continue
            text = row.get("text", "") or ""
            meta = row.get("meta", {}) or {}
            _index_put(rid_clean, text, meta)
            loaded += 1
    return loaded


def _ensure_loaded(force: bool = False) -> None:
    global _LOADED
    if not force and _LOADED:
        return
    with _DOCS_LOCK:
        if not force and _LOADED:
            return
        _DOCS.clear()
        _NORM_INDEX.clear()
        for p in _candidate_docs_paths():
            _load_jsonl_into_cache(p)
        _LOADED = True


def _lookup_by_id_any_form(id_param: str) -> Optional[Tuple[str, Dict[str, Any], str]]:
    _ensure_loaded()
    key = _norm_key(id_param)

    # 1) po normalizovannomu klyuchu
    with _DOCS_LOCK:
        oid = _NORM_INDEX.get(key)
        if oid:
            text, meta = _DOCS[oid]
            return text, meta, oid

    # 2) doindeksirovat i poprobovat esche raz
    with _DOCS_LOCK:
        before = len(_DOCS)
        for p in _candidate_docs_paths():
            _load_jsonl_into_cache(p)
        if len(_DOCS) != before:
            oid = _NORM_INDEX.get(key)
            if oid:
                text, meta = _DOCS[oid]
                return text, meta, oid

    # 3) pryamoe chtenie fayla po puti (baypas indeksa)
    for p in (id_param, os.path.abspath(id_param)):
        try:
            if os.path.exists(p) and os.path.isfile(p):
                with open(p, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
                meta = {"fname": os.path.basename(p)}
                try:
                    meta["size"] = os.path.getsize(p)
                except Exception:
                    pass
                with _DOCS_LOCK:
                    _index_put(p, text, meta)  # keshiruem
                return text, meta, p
        except Exception:
            pass

    return None


def _b(s: Optional[str]) -> bool:
    return (s or "").strip().lower() in ("1", "true", "t", "yes", "y", "on")


def _i(name: str, default: int) -> int:
    v = request.args.get(name)
    if not v:
        return default
    try:
        return int(v)
    except Exception:
        return default


# ------------------ Publichnye marshruty ------------------

@bp.get("/rag/hybrid/doc")
def get_doc_slice():
    """
    GET /rag/hybrid/doc
      ?id=...                # obyazatelnyy: id iz docs.jsonl ILI pryamoy put k faylu
      &start=0               # rezhim SREZA
      &max_chars=2000
      &q=...                 # rezhim «OKNO» vokrug frazy
      &window_before=200
      &window_after=400
      &include_meta=1
    """
    raw_id = request.args.get("id")
    id_param = _clean_id_param(raw_id)
    if not id_param:
        return jsonify({"ok": False, "error": "missing id"}), 400

    got = _lookup_by_id_any_form(id_param)
    if not got:
        tail = raw_id[-8:] if raw_id else ""
        return jsonify({
            "ok": False,
            "error": "id not found",
            "id": raw_id,
            "id_clean": id_param,
            "id_len_raw": len(raw_id or ""),
            "id_len_clean": len(id_param or ""),
            "id_tail_raw": tail,
        }), 404

    text, meta, oid = got
    include_meta = _b(request.args.get("include_meta"))
    q = request.args.get("q") or ""

    # rezhim "okno" vokrug stroki q
    if q:
        src = text
        idx = src.lower().find(q.lower())
        if idx < 0:
            # PATCh: ne shlem 404, chtoby PowerShell/iwr ne padali.
            # Vozvraschaem 200 + ok:false i diagnosticheskie polya.
            return jsonify({
                "ok": False,
                "error": "q not found",
                "http_status": 404,
                "id": oid,
                "len_text": len(src),
                "q": q,
            }), 200

        wb = _i("window_before", 200)
        wa = _i("window_after", 400)
        start = max(0, idx - wb)
        end = min(len(src), idx + len(q) + wa)
        chunk = src[start:end]
        resp: Dict[str, Any] = {
            "ok": True,
            "mode": "window",
            "id": oid,
            "len_text": len(src),
            "start": start,
            "end": end,
            "window_before": wb,
            "window_after": wa,
            "has_more": end < len(src),
            "q": q,
            "text": chunk,
        }
        if include_meta:
            resp["meta"] = meta
        return jsonify(resp)

    # rezhim "srez"
    start = max(0, _i("start", 0))
    max_chars = _i("max_chars", 2000)
    if max_chars <= 0:
        end = len(text)
    else:
        end = min(len(text), start + max_chars)
    chunk = text[start:end]

    resp = {
        "ok": True,
        "mode": "slice",
        "id": oid,
        "len_text": len(text),
        "start": start,
        "max_chars": max_chars if max_chars > 0 else (len(text) - start),
        "has_more": end < len(text),
        "text": chunk,
    }
    if include_meta:
        resp["meta"] = meta
    return jsonify(resp)


# ------------------ Diagnostika ------------------

@bp.get("/_diag/rag_doc/state")
def diag_state():
    _ensure_loaded()
    with _DOCS_LOCK:
        sample = list(_DOCS.keys())[:10]
        return jsonify({
            "ok": True,
            "candidates": _candidate_docs_paths(),
            "indexed_count": len(_DOCS),
            "sample_ids": sample,
        })


@bp.get("/_diag/rag_doc/lookup")
def diag_lookup():
    raw_id = request.args.get("id", "")
    clean_id = _clean_id_param(raw_id)
    got = _lookup_by_id_any_form(clean_id)
    found = bool(got)
    resp: Dict[str, Any] = {
        "ok": True,
        "raw_id": raw_id,
        "clean_id": clean_id,
        "raw_len": len(raw_id),
        "clean_len": len(clean_id),
        "candidates": _candidate_docs_paths(),
        "found": found,
    }
    if found:
        text, meta, oid = got
        resp.update({
            "oid": oid,
            "meta": meta,
            "text_len": len(text),
        })
    return jsonify(resp)


@bp.post("/_diag/rag_doc/reload")
def diag_reload():
    _ensure_loaded(force=True)
    with _DOCS_LOCK:
        return jsonify({
            "ok": True,
            "indexed_count": len(_DOCS),
        })


# Sovmestimost s avtoloaderom iz app.py
def register(app):
    app.register_blueprint(bp)
    return app


__all__ = ["bp", "register"]