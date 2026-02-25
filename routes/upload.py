# -*- coding: utf-8 -*-
# routes/upload.py
"""routes/upload.py - zagruzka faylov (bezopasno offlayn) s postanovkoy v inzhest.

Endpoint:
  • POST /ingest/file - multipart/form-data: file=<file>; meta: source?, tags?
  • GET /ingest/formats - spisok podderzhivaemykh/zapreschennykh formatov
  • GET /ingest/help - kratkaya spravka po API

Sovmestimost:
  • Signatura registratora: register_upload_routes(app, url_prefix="/ingest")
  • Dlya avtozagruzchika predusmotren register(app).

# c=a+b"""
from __future__ import annotations
import os, json, time, base64, hashlib, hmac
from typing import Any, Dict, List
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("upload_routes", __name__, url_prefix="/ingest")


def _csrf_expected(user_agent: str, client_ip: str) -> str:
    secret = (os.getenv("CSRF_SECRET", "ester-dev-csrf-secret")).encode("utf-8")
    msg = f"{user_agent}|{client_ip}".encode("utf-8")
    sig = hmac.new(secret, msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("ascii")


@bp.get("/formats")
def formats():
    ab = (os.getenv("ESTER_INGEST_PIPELINE_AB", "A") or "A").upper()
    allowed = [".txt", ".md", ".pdf"]
    if ab == "B":
        allowed += [".docx", ".doc", ".html", ".htm"]
    return jsonify({"ok": True, "allowed": allowed, "denied": [".exe", ".bat", ".cmd"]})

@bp.get("/help")
def help_():
    return jsonify({"ok": True, "routes": ["POST /ingest/file", "GET /ingest/formats", "GET /ingest/help"]})

@bp.post("/file")
def upload_file():
    # CSRF guard for browser-style multipart uploads:
    # enforce only when request is proxied with explicit client IP header.
    ua = (request.headers.get("User-Agent") or "").strip()
    xff = (request.headers.get("X-Forwarded-For") or "").strip()
    if ua and xff:
        client_ip = xff.split(",", 1)[0].strip()
        got = (request.headers.get("X-CSRF-Token") or "").strip()
        exp = _csrf_expected(ua, client_ip)
        if not got or not hmac.compare_digest(got, exp):
            return jsonify({"ok": False, "error": "csrf required"}), 403

    if "file" not in request.files:
        return jsonify({"ok": False, "error": "file required"}), 400
    f = request.files["file"]
    os.makedirs("data/uploads", exist_ok=True)
    ts = int(time.time())
    name = f.filename or f"upload_{ts}"
    path = os.path.join("data", "uploads", name)
    f.save(path)
    # Placement in the “ingest queue” (drop-in)
    q_dir = os.getenv("INGEST_QUEUE_DIR", os.path.join("data", "ingest", "queue"))
    os.makedirs(q_dir, exist_ok=True)
    meta = {
        "source": request.form.get("source") or "ui",
        "tags": (request.form.get("tags") or "").split(","),
        "uploaded_ts": ts,
    }
    with open(os.path.join(q_dir, f"{ts}_{name}.json"), "w", encoding="utf-8") as q:
        json.dump({"path": path, "meta": meta}, q, ensure_ascii=False)
    return jsonify({"ok": True, "stored": {"path": path}, "queued": True})

def register_upload_routes(app, url_prefix: str = "/ingest") -> None:
    # if you need a different prefix, create a second bp with the same view
    if bp.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(bp)
    if url_prefix and url_prefix != "/ingest":
        bp2 = Blueprint("upload_routes_prefixed", __name__, url_prefix=url_prefix)  # type: ignore
        bp2.add_url_rule("/file", view_func=upload_file, methods=["POST"])  # type: ignore
        bp2.add_url_rule("/formats", view_func=formats, methods=["GET"])  # type: ignore
        bp2.add_url_rule("/help", view_func=help_, methods=["GET"])  # type: ignore
        if bp2.name not in getattr(app, "blueprints", {}):
            app.register_blueprint(bp2)

def register(app) -> None:
    register_upload_routes(app)


def register(app):
    app.register_blueprint(bp)
    return app
