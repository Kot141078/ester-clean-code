# -*- coding: utf-8 -*-
"""routes/ingest_backpressure_routes.py - podklyuchaemyy backpressure dlya vsekh POST /ingest/*
(bez change kontraktov i imeni blyuprinta).

Mosty:
- Yavnyy: (Kibernetika ↔ Nagruzka) - before_app_request sglazhivaet piki cherez allow(key).
- Skrytyy #1: (Nablyudaemost ↔ Ekspluatatsiya) - /ingest/queue/state i /ingest/queue/config dlya REST/Prometheus.
- Skrytyy #2: (Set ↔ Bezopasnost) - opredelenie istochnika: X-Source-Key → JSON.meta.source.key → URL.host → anon:IP.

Zemnoy abzats:
Eto “regulirovschik na vezde k skladu”: propuskaet fury po talonam, chtoby rampa ne zadokhnulas.
Kontrakty ingest-ruchek ne menyaem - filtr stoit pered nimi, myagko vozvraschaya 429 s Retry-After.

# c=a+b"""
from __future__ import annotations

import ipaddress
from typing import Any, Dict, Tuple, Optional

from flask import Blueprint, jsonify, request, current_app

# --- Constants and blueprint (we save the name for compatibility) ---
_BP_NAME = "ingest_bp"
bp_ingest_bp = Blueprint(_BP_NAME, __name__)

# AB flag (you can temporarily disable registration without editing the code)
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
_AB = (os.getenv("ESTER_INGEST_BP_AB") or "B").strip().upper()

# Tries to tighten up the real functions of Baskpressure; if not - soft plugs
try:
    from modules.ingest.backpressure import allow, counters, get_config, set_config  # type: ignore
except Exception:
    allow = counters = get_config = set_config = None  # type: ignore


def _source_key() -> str:
    """Retrieving the source key:
      1) Header S-Source-Key
      2) JSION.water.meta.source.key
      3) anon:<ip> (C-Forwarded-For|remote_addr)"""
    key = request.headers.get("X-Source-Key")
    if not key:
        try:
            data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
            meta = data.get("meta") or {}
            src = (meta.get("source") or {}).get("key")
            key = str(src) if src else None
        except Exception:
            key = None
    if not key:
        ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "0.0.0.0"
        try:
            ipaddress.ip_address(ip.split(",")[0].strip())
        except Exception:
            ip = "0.0.0.0"
        key = f"anon:{ip}"
    return key


# We will hang the filter on the blueprint (it will be registered once with it)
@bp_ingest_bp.before_app_request
def _bp_guard():
    # Only POST and only /ingest/*
    if request.method != "POST":
        return None
    path = request.path or ""
    if not path.startswith("/ingest/"):
        return None
    if allow is None:
        return None
    key = _source_key()
    ok_retry: Tuple[bool, Optional[int]] = allow(key)  # type: ignore
    ok, retry = bool(ok_retry[0]), ok_retry[1]
    if ok:
        return None
    # Myagkiy blok 429 + Retry-After
    resp = jsonify({"ok": False, "error": "rate_limited", "retry_after": retry, "source": key})
    resp.status_code = 429
    if retry is not None:
        resp.headers["Retry-After"] = str(retry)
    return resp


@bp_ingest_bp.route("/ingest/queue/state", methods=["GET"])
def api_state():
    if counters is None or get_config is None:
        return jsonify({"ok": False, "error": "backpressure unavailable"}), 500
    return jsonify({"ok": True, "counters": counters(), "config": get_config()})


@bp_ingest_bp.route("/ingest/queue/config", methods=["POST"])
def api_config():
    if set_config is None:
        return jsonify({"ok": False, "error": "backpressure unavailable"}), 500
    data = request.get_json(force=True, silent=True) or {}
    return jsonify({"ok": True, "config": set_config(data)})


def register(app):
    """Idempotentnaya registratsiya blyuprinta.
    Ispravlenie oshibki: esli blueprint s imenem 'ingest_bp' uzhe est (goryachiy reload/dvoynoy import) -
    ne pytaemsya registrirovat vtoroy raz, chtoby ne lovit ValueError(...already registered...)."""
    if _AB != "B":
        if hasattr(app, "logger"):
            app.logger.debug("[ingest_bp] AB flag != B, skip registering")
        return

    if _BP_NAME in app.blueprints:
        # already registered - quits quietly
        if hasattr(app, "logger"):
            app.logger.debug("[ingest_bp] blueprint already registered, skipping")
        return

    app.register_blueprint(bp_ingest_bp)