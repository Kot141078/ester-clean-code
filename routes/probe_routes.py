# -*- coding: utf-8 -*-
"""routes/probe_routes.py - sinteticheskie proverki "zolotykh putey" v odnom HTTP-vyzove.
Ispolzuetsya dlya Argo Rollouts (web metrics provider) i dlya ruchnykh proverok.

Route:
  GET /ops/probe/golden -> { ok: bool, value: 1|0, checks: {...} }
  GET /ops/probe/llm -> { ok: bool, value: float (dolya uspekhov), details: [...] }

Uspekh - value > 0 (ili ==1) dlya web-provaydera Rollouts.

Drop-in: ne menyaet suschestvuyuschie importy i fayly. Dlya aktivatsii dobav registratsiyu
blueprint v place initsializatsii prilozheniya:
    from routes.probe_routes import bp_probe
    app.register_blueprint(bp_probe)

Mosty:
- Yavnyy: (DevOps ↔ Prilozhenie) eksportiruem metriki dostupnosti “zolotykh putey” cherez prostoy REST.
- Skrytyy #1: (Infoteoriya ↔ Shum) agregiruem binarnye iskhody v dolyu uspekhov, sglazhivaya noise.
- Skrytyy #2: (Kibernetika ↔ Obratnaya svyaz) HTTP-kody 200/503 napryamuyu zamykayut kontur avtodeploya.
- Skrytyy #3: (Memory/Logi ↔ Prozrachnost) details proverok mozhno pisat v obschiy “profile”.

Zemnoy abzats:
Dumay ob etom module kak o “stetoskope” dlya servisa: paru udarov - i slyshno, where weak place.
Proveryaem liveness/ready, OpenAPI, provayderov i korotkiy graf - bystryy diagnoz bez lishney krovi.

# c=a+b"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List

import requests
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_probe = Blueprint("probe", __name__)

TIMEOUT = float(os.getenv("PROBE_TIMEOUT_S", "3.0"))
BASE_URL = os.getenv("ESTER_BASE_URL_INTERNAL", "http://127.0.0.1:5000")
JWT = os.getenv("ESTER_PROBE_JWT", "")
HDRS = {"Authorization": f"Bearer {JWT}"} if JWT else {}


def _check(path: str, exp: List[int] = [200]) -> Dict[str, Any]:
    """GET request to BASE_URL+path (or absolute URL), waiting for code from exp."""
    url = f"{BASE_URL}{path}" if path.startswith("/") else path
    t0 = time.time()
    try:
        r = requests.get(url, headers=HDRS, timeout=TIMEOUT)
        ok = r.status_code in exp
        return {
            "path": path,
            "status": r.status_code,
            "ms": int((time.time() - t0) * 1000),
            "ok": ok,
        }
    except Exception as e:
        return {
            "path": path,
            "error": str(e),
            "ok": False,
            "ms": int((time.time() - t0) * 1000),
        }


@bp_probe.get("/ops/probe/golden")
def probe_golden():
    """Mini-set of “golden paths”: liveliness, spec, providers, short graph."""
    checks = [
        _check("/live"),
        _check("/ready", [200, 503]),
        _check("/openapi.json"),
        _check("/providers/status"),
        _check("/mem/kg/neighbors?limit=1&k=1", [200, 404]),
    ]
    ok = all(c.get("ok") for c in checks)
    return (
        jsonify({"ok": ok, "value": 1 if ok else 0, "checks": checks}),
        200 if ok else 503,
    )


@bp_probe.get("/ops/probe/llm")
def probe_llm():
    """Easy check of the LLM chain: status of providers + echo (if any)."""
    subs = []
    subs.append(_check("/providers/status"))
    subs.append(_check("/chat/echo?text=ping", [200, 404]))
    ok_count = sum(1 for s in subs if s.get("ok"))
    val = ok_count / max(len(subs), 1)
    return (
        jsonify({"ok": ok_count == len(subs), "value": val, "details": subs}),
        (200 if ok_count else 503),
    )


# Unified project hooks (by convention)
def register(app):  # pragma: no cover
    app.register_blueprint(bp_probe)


def init_app(app):  # pragma: no cover
    app.register_blueprint(bp_probe)


__all__ = ["bp_probe", "register", "init_app"]
# c=a+b