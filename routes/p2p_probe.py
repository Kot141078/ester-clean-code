
# -*- coding: utf-8 -*-
"""routes/p2p_probe.py - generatsiya HMAC-podpisi dlya P2P (primer dlya /api/v2/synergy/assign).

MOSTY:
- (Yavnyy) GET/POST /p2p/sign_example - vozvraschaet canonical, ts, sha256(body), signature, gotovye curl/PS-shablony.
- (Skrytyy #1) Use P2P_HMAC_KEY iz .env; format: METHOD|PATH|TS|<hex_sha256>.
- (Skrytyy #2) Rabotaet offlayn; telo mozhno peredat kak JSON (field "body") or strokoy.

ZEMNOY ABZATs:
Kak “kalibrator klyucha”: poluchil tochnuyu podpis i tut zhe vstavil v komandu - bez plyasok s bubnom.

# c=a+b"""
from __future__ import annotations
import os, hmac, hashlib, json, time
from flask import Blueprint, request, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("p2p_probe", __name__, url_prefix="/p2p")

def register(app):
    app.register_blueprint(bp)

def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _hmac_hex(key: str, msg: str) -> str:
    return hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()

def _make_examples(url: str, ts: str, sig: str, body_str: str):
    ps_body = body_str.replace('"','""')
    curl = f"curl -s -X POST \"{url}\" -H \"Content-Type: application/json\" -H \"X-Timestamp: {ts}\" -H \"X-Signature: {sig}\" --data '{body_str}'"
    ps = (
        "$ts = " + ts + "\n"
        "$sig = \"" + sig + "\"\n"
        "$body = '" + ps_body + "'\n"
        f"Invoke-RestMethod -Uri '{url}' -Method Post -Headers @{{'Content-Type'='application/json';'X-Timestamp'=$ts;'X-Signature'=$sig}} -Body $body"
    )
    return curl, ps

@bp.route("/sign_example", methods=["GET","POST"])
def sign_example():
    key = os.getenv("P2P_HMAC_KEY","devkey")
    method = (request.json or {}).get("method") if request.is_json else None
    path = (request.json or {}).get("path") if request.is_json else None
    body = (request.json or {}).get("body") if request.is_json else None

    method = (method or request.args.get("method") or "POST").upper()
    path = (path or request.args.get("path") or "/api/v2/synergy/assign")
    ts = request.args.get("ts") or str(int(time.time()))

    if body is None:
        # Defoltnoe telo primera
        body_obj = {"team_id":"Recon A","overrides":{"operator":"human.pilot"}}
        body_str = json.dumps(body_obj, ensure_ascii=False)
    else:
        body_str = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)

    sha = _sha256_hex(body_str.encode("utf-8"))
    canonical = f"{method}|{path}|{ts}|{sha}"
    sig = _hmac_hex(key, canonical)
    url = os.getenv("P2P_ASSIGN_URL","http://127.0.0.1:8080/api/v2/synergy/assign")
    curl, ps = _make_examples(url, ts, sig, body_str)

    return jsonify({
        "ok": True,
        "key_present": bool(os.getenv("P2P_HMAC_KEY")),
        "method": method, "path": path, "ts": ts,
        "sha256": sha, "canonical": canonical, "signature": sig,
        "examples": {"curl": curl, "powershell": ps}
    })
# c=a+b