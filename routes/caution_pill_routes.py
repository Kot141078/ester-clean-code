# -*- coding: utf-8 -*-
"""routes/caution_pill_routes.py - REST: vydacha "pilyuli".

Mosty:
- Yavnyy: (Veb ↔ Ostorozhnost) edinaya tochka vypuska odnorazovykh tokenov.
- Skrytyy #1: (Ops ↔ Integratsiya) udobno v skriptakh i panelyakh (kak v smoke-shage).
- Skrytyy #2: (Audit ↔ Memory) vydachu mozhno logirovat vne etogo modulya.

Zemnoy abzats:
Odin POST - i u vas v rukakh odnorazovyy klyuch na opasnuyu operatsiyu.

# c=a+b"""
from __future__ import annotations
import base64
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("caution_pill_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.caution.pill import issue as _issue  # type: ignore
except Exception:
    _issue=None  # type: ignore

@bp.route("/caution/pill/issue", methods=["POST"])
def api_issue():
    if _issue is None: return jsonify({"ok": False, "error":"pill_unavailable"}), 500
    d=request.get_json(True, True) or {}
    pat=str(d.get("pattern","^/$") or "^/$")
    met=str(d.get("method","POST") or "POST")
    ttl=int(d.get("ttl",300))
    sub=_header_utf8("X-Subject")
    return jsonify(_issue(pat, met, ttl, subject=sub))


def _header_utf8(name: str) -> str:
    base = str(name or "").strip()
    if not base:
        return ""
    b64 = request.headers.get(base + "-B64", "")
    text = _b64url_decode_utf8(b64)
    if text:
        return text
    return str(request.headers.get(base, "") or "")


def _b64url_decode_utf8(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        pad = "=" * ((4 - (len(raw) % 4)) % 4)
        payload = base64.urlsafe_b64decode((raw + pad).encode("ascii"))
        return payload.decode("utf-8", errors="strict")
    except Exception:
        return ""
# c=a+b
