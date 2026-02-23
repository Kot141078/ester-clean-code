# -*- coding: utf-8 -*-
"""
routes/ester_net_ingest_url_routes_alias.py — ingest URL (fetch→text→markdown inbox).

YaVNYY MOST: c=a+b — chelovek daet URL (a), protsedura fetch/SSRF-guard/normalizatsiya/zapis (b) → ustoychivyy artefakt (c).
SKRYTYE MOSTY:
  - Cover&Thomas: ogranichenie kanala (taymaut/limit bayt/limit chars) protiv “zabitoy linii”.
  - Ashby: raznoobrazie istochnikov (WEB_PROVIDER) daet variety, no my rezhem risk (SSRF) i derzhim ramki.
ZEMNOY ABZATs:
  Eto kak “vpustit vozdukh” cherez filtr i klapan: my ne otkryvaem vorota nastezh, a doziruem potok,
  chistim ot musora i skladyvaem v “yaschik vkhodyaschikh”, chtoby pamyat ne zakhlebnulas.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from bridges.internet_access import InternetAccess  # type: ignore
except Exception as e:  # pragma: no cover
    InternetAccess = None  # type: ignore
    _IA_IMPORT_ERROR = str(e)
else:
    _IA_IMPORT_ERROR = ""

bp_ester_net_ingest_url = Blueprint("ester_net_ingest_url", __name__)


def _env_bool(name: str, default: bool = False) -> bool:
    v = (os.getenv(name, "") or "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "y", "on")


def _project_root() -> Path:
    # Prefer explicit, otherwise resolve from this file: <root>/routes/...
    env = (os.getenv("ESTER_PROJECT_ROOT", "") or "").strip()
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[1]


def _default_out_dir() -> Path:
    # app.py is mainly monitoring, so we put artifacts in a dedicated “web inbox”
    rel = (os.getenv("ESTER_NET_INBOX_DIR", "data/inbox/web") or "data/inbox/web").strip()
    return (_project_root() / rel).resolve()


@bp_ester_net_ingest_url.get("/ester/net/fetch_text")
def fetch_text():
    """
    GET /ester/net/fetch_text?url=https://...
    Returns: {ok, url, text, error}
    """
    if InternetAccess is None:
        return jsonify({"ok": False, "error": f"InternetAccess import failed: {_IA_IMPORT_ERROR}"}), 500

    if not _env_bool("ESTER_NET_FETCH_ALLOW", default=True):
        return jsonify({"ok": False, "error": "fetch_disabled_by_env"}), 403

    url = (request.args.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "empty_url"}), 400

    max_chars = int((request.args.get("max_chars") or "12000").strip() or "12000")

    ia = InternetAccess()
    txt = ia.read_text(url, max_chars=max_chars)

    if not txt:
        # Most common: WEB_ALLOW_FETCH=0 or SSRF guard triggered
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "empty_or_fetch_disabled",
                    "hint": "Set WEB_ALLOW_FETCH=1 (and keep CLOSED_BOX=0) to enable HTML fetch; SSRF guard blocks private hosts.",
                }
            ),
            409,
        )

    return jsonify({"ok": True, "url": url, "chars": len(txt), "text": txt})


@bp_ester_net_ingest_url.post("/ester/net/ingest_url")
def ingest_url():
    """
    POST /ester/net/ingest_url
    JSON: {url, query?, max_chars?, out_dir?, mode?('A'|'B')}
    Returns: {ok, path, chars, summary?, error?}
    """
    if InternetAccess is None:
        return jsonify({"ok": False, "error": f"InternetAccess import failed: {_IA_IMPORT_ERROR}"}), 500

    if not _env_bool("ESTER_NET_INGEST_ALLOW", default=True):
        return jsonify({"ok": False, "error": "ingest_disabled_by_env"}), 403

    data: Dict[str, Any] = request.get_json(silent=True) or {}
    url = str(data.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "empty_url"}), 400

    query = str(data.get("query") or "").strip()
    max_chars = int(data.get("max_chars") or 18000)
    mode = str(data.get("mode") or "A").strip().upper()
    if mode not in ("A", "B"):
        mode = "A"

    out_dir = str(data.get("out_dir") or "").strip()
    if out_dir:
        out_path = Path(out_dir).expanduser()
        if not out_path.is_absolute():
            out_path = (_project_root() / out_path).resolve()
    else:
        out_path = _default_out_dir()

    ia = InternetAccess()
    res = ia.ingest_url_to_markdown(url=url, out_dir=str(out_path), query=query, max_chars=max_chars, mode=mode)
    code = 200 if res.get("ok") else 409
    return jsonify(res), code