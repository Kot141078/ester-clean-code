# -*- coding: utf-8 -*-
"""
routes/ingest_backpressure.py - myagkiy backpressure dlya /ingest/* cherez before_request i token-bakety.

Povedenie:
  • Esli INGEST_BP_ENABLE=1 - pered lyubym /ingest/* delaem kontrol chastoty per-source (IP/X-Source-Key/host).
  • Token-baket: skorost = INGEST_BP_DEFAULT_RPS, burst = INGEST_BP_BURST. Pri nekhvatke - 429.
  • Oshibki 429/5xx mozhno uchityvat na urovne vyzyvayuschey storony (backoff); server - «myagkiy ogranichitel».
  • Metriki v /metrics/ingest_bp.

Mosty:
- Yavnyy: (Vvod ↔ Nadezhnost) zaschischaem ingest ot «zabivaniya» odnim istochnikom.
- Skrytyy #1: (Infoteoriya ↔ Planirovanie) skorost/ochered → ponyatnye signaly v RuleHub.
- Skrytyy #2: (Kibernetika ↔ Kontrol) vse cherez before_request - drop-in dlya suschestvuyuschikh routov.

Zemnoy abzats:
Eto «semafor na rampe»: slishkom mnogo gruzovikov s odnogo vyezda - pritormazhivaem, chtoby trassa ne vstala.

# c=a+b
"""
from __future__ import annotations

import os
import time
from typing import Dict, TypedDict

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_ingest_bp = Blueprint("ingest_bp", __name__)

_ENABLE = bool(int(os.getenv("INGEST_BP_ENABLE", "0")))
_RPS = float(os.getenv("INGEST_BP_DEFAULT_RPS", "0.5"))
_BURST = int(os.getenv("INGEST_BP_BURST", "3"))


class Bucket(TypedDict):
    tokens: float
    ts: float


_bucket: Dict[str, Bucket] = {}  # key -> {tokens, ts}
_cnt = {"allowed": 0, "blocked": 0}


def register(app):  # pragma: no cover
    app.register_blueprint(bp_ingest_bp)

    @app.before_request
    def _guard():
        if not _ENABLE:
            return
        p = request.path or ""
        if not p.startswith("/ingest/"):
            return
        key = request.headers.get("X-Source-Key") or request.remote_addr or "anon"
        now = time.time()
        b: Bucket = _bucket.get(key) or Bucket(tokens=float(_BURST), ts=now)  # type: ignore[arg-type]
        # refill
        delta = now - b["ts"]
        b["tokens"] = min(float(_BURST), b["tokens"] + delta * _RPS)
        b["ts"] = now
        if b["tokens"] < 1.0:
            _cnt["blocked"] += 1
            return jsonify({"ok": False, "error": "backpressure: rate limited"}), 429
        b["tokens"] -= 1.0
        _bucket[key] = b
        _cnt["allowed"] += 1


def init_app(app):  # pragma: no cover
    register(app)


@bp_ingest_bp.route("/ingest/backpressure/caps", methods=["GET"])
def caps():
    return jsonify({"ok": True, "enable": _ENABLE, "rps": _RPS, "burst": _BURST, "keys": len(_bucket)})


@bp_ingest_bp.route("/metrics/ingest_bp", methods=["GET"])
def metrics():
    text = (
        f"ingest_bp_enabled {1 if _ENABLE else 0}\n"
        f"ingest_bp_allowed_total {_cnt['allowed']}\n"
        f"ingest_bp_blocked_total {_cnt['blocked']}\n"
    )
    return text, 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"}


__all__ = ["bp_ingest_bp", "register", "init_app"]