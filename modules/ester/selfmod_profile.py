# -*- coding: utf-8 -*-
"""Ester selfmod profile:
Svodnyy vzglyad na kontur samoizmeneniya i voli.

Endpoint:
    GET /ester/selfmod/profile

Ne menyaet povedenie selfmod, just pokazyvaet:
- tekuschiy rezhim (A/B),
- allow_ester,
- "syrye" otvety /ester/selfmod/status i /ester/will/plan."""

import os
import json
from urllib import request as urlrequest, error as urlerror
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_ester_selfmod_profile = Blueprint("ester_selfmod_profile", __name__)

DEFAULT_HOST = os.getenv("ESTER_HTTP_HOST", "127.0.0.1")
DEFAULT_PORT = os.getenv("ESTER_HTTP_PORT", "8080")


def _bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _get_mode() -> str:
    return (os.getenv("ESTER_SELFMOD_AB", "A") or "A").strip().upper()


def _fetch_json(path: str):
    base = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
    url = base + path
    try:
        with urlrequest.urlopen(url, timeout=2.0) as resp:
            code = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(body)
            except Exception:
                data = {"raw": body}
            return {"code": code, "status": data}
    except urlerror.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {"raw": body}
        return {"code": e.code, "status": data or {"error": str(e)}}
    except Exception as e:
        return {"code": 503, "status": {"ok": False, "error": str(e)}}


@bp_ester_selfmod_profile.route("/ester/selfmod/profile", methods=["GET"])
def ester_selfmod_profile():
    mode = _get_mode()
    allow_ester = _bool_env("ESTER_SELFMOD_ALLOW_ESTER", False)

    selfmod_status = _fetch_json("/ester/selfmod/status")
    will_plan = _fetch_json("/ester/will/plan")

    result = {
        "ok": True,
        "mode": mode,
        "allow_ester": allow_ester,
        "selfmod": selfmod_status,
        "will": will_plan,
    }
    return jsonify(result)