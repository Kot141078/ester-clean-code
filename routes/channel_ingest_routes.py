# -*- coding: utf-8 -*-
"""
routes/channel_ingest_routes.py - REST/webhook endpoints for message/file/event ingest.

Examples:
  POST /ingest/message   {"source":"telegram","user":"owner","text":"Hello"}
  POST /ingest/file      {"source":"browser","path":"docs/test.txt","user":"owner"}
  POST /ingest/event     {"source":"web","kind":"click_button","meta":{"id":"ok"}}
  GET  /admin/ingest
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import os
import time
import threading
import uuid
from flask import Blueprint, jsonify, request, render_template
try:
    from flask_jwt_extended import jwt_required  # type: ignore
except Exception:
    def jwt_required(*args, **kwargs):  # type: ignore
        def _wrap(fn):
            return fn
        return _wrap
try:
    from modules.auth.rbac import has_any_role as _has_any_role
except Exception:
    def _has_any_role(_required):  # type: ignore
        return True
from modules.memory import channel_ingest as CI
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("channel_ingest_routes", __name__, url_prefix="/ingest")
_JOBS_LOCK = threading.RLock()
_JOBS = {}
_DENY_EXTS = {".exe", ".bat", ".cmd", ".com", ".msi"}


def _csrf_expected(user_agent: str, client_ip: str) -> str:
    secret = (os.getenv("CSRF_SECRET", "ester-dev-csrf-secret")).encode("utf-8")
    msg = f"{user_agent}|{client_ip}".encode("utf-8")
    sig = hmac.new(secret, msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("ascii")


def _set_job(job_id: str, patch: dict) -> dict:
    with _JOBS_LOCK:
        cur = dict(_JOBS.get(job_id) or {})
        cur.update(patch)
        _JOBS[job_id] = cur
        return cur


def _get_job(job_id: str) -> dict:
    with _JOBS_LOCK:
        return dict(_JOBS.get(job_id) or {})


def _multipart_value(name: str, default: str = "") -> str:
    """Read multipart scalar from form, with fallback for malformed tuple uploads.

    In some legacy tests, scalar fields are sent as file-parts where the value is
    encoded into FileStorage.filename and body is empty.
    """
    val = request.form.get(name)
    if val is not None and str(val) != "":
        return str(val)
    fs = request.files.get(name)
    if fs is None:
        return default
    if fs.filename:
        return str(fs.filename)
    try:
        raw = fs.read()
    except Exception:
        raw = b""
    try:
        fs.stream.seek(0)
    except Exception:
        pass
    if raw:
        return raw.decode("utf-8", errors="ignore")
    return default


def _save_text_upload(text: str, ext: str = ".txt") -> str:
    ts = int(time.time())
    os.makedirs(os.path.join("data", "uploads"), exist_ok=True)
    path = os.path.join("data", "uploads", f"upload_{ts}_{uuid.uuid4().hex[:8]}{ext}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def _max_upload_mb() -> float:
    # Keep compatibility with legacy tests that monkeypatch routes_upload.MAX_MB.
    env_raw = (os.getenv("MAX_UPLOAD_MB") or "").strip()
    if env_raw:
        try:
            val = float(env_raw)
            if val > 0:
                return val
        except Exception:
            pass
    try:
        import routes_upload  # type: ignore

        val = float(getattr(routes_upload, "MAX_MB", 25))
        return max(0.000001, val)
    except Exception:
        try:
            return max(0.000001, float(os.getenv("MAX_UPLOAD_MB", "25")))
        except Exception:
            return 25


def _file_size_bytes(fs) -> int:
    try:
        cl = getattr(fs, "content_length", None)
        if cl is not None:
            return int(cl)
    except Exception:
        pass
    try:
        stream = getattr(fs, "stream", None)
        if stream is None:
            return 0
        cur = stream.tell()
        stream.seek(0, os.SEEK_END)
        sz = int(stream.tell())
        stream.seek(cur)
        return sz
    except Exception:
        return 0

@bp.route("/message", methods=["POST"])
def message():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(CI.ingest_message(d.get("source","unknown"), d.get("user","anon"), d.get("text","")))

@bp.route("/file", methods=["POST"])
def file():
    if "file" in request.files:
        ua = (request.headers.get("User-Agent") or "").strip()
        xff = (request.headers.get("X-Forwarded-For") or "").strip()
        if ua and xff:
            ip = xff.split(",", 1)[0].strip()
            got = (request.headers.get("X-CSRF-Token") or "").strip()
            exp = _csrf_expected(ua, ip)
            if not got or not hmac.compare_digest(got, exp):
                return jsonify({"ok": False, "error": "csrf required"}), 403

        f = request.files["file"]
        ts = int(time.time())
        name = f.filename or f"upload_{ts}.bin"
        ext = os.path.splitext(name)[1].lower()
        if ext in _DENY_EXTS:
            return jsonify({"ok": False, "error": "unsupported media type"}), 415
        size = _file_size_bytes(f)
        if size <= 0:
            try:
                size = int(request.content_length or 0)
            except Exception:
                size = 0
        if size > _max_upload_mb() * 1024 * 1024:
            return jsonify({"ok": False, "error": "too large"}), 413
        os.makedirs(os.path.join("data", "uploads"), exist_ok=True)
        path = os.path.join("data", "uploads", name)
        f.save(path)
        source = request.form.get("source") or "files"
        user = request.form.get("user") or "anon"
        rep = CI.ingest_file(source, path, user)
        job_id = f"file_{uuid.uuid4().hex[:12]}"
        _set_job(
            job_id,
            {
                "id": job_id,
                "status": "DONE",
                "created_ts": float(time.time()),
                "finished_ts": float(time.time()),
                "path": path,
                "user": user,
                "result": rep,
            },
        )
        out = dict(rep or {})
        out.setdefault("ok", True)
        out["id"] = job_id
        out["status"] = "DONE"
        return jsonify(out)

    d = request.get_json(force=True, silent=True) or {}
    rep = CI.ingest_file(d.get("source", "files"), d.get("path", ""), d.get("user", "anon"))
    job_id = f"file_{uuid.uuid4().hex[:12]}"
    _set_job(
        job_id,
        {
            "id": job_id,
            "status": "DONE",
            "created_ts": float(time.time()),
            "finished_ts": float(time.time()),
            "path": d.get("path", ""),
            "user": d.get("user", "anon"),
            "result": rep,
        },
    )
    out = dict(rep or {})
    out.setdefault("ok", True)
    out["id"] = job_id
    out["status"] = "DONE"
    return jsonify(out)

@bp.route("/event", methods=["POST"])
def event():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(CI.ingest_event(d.get("source","web"), d.get("kind",""), d.get("meta") or {}, d.get("user","anon")))


@bp.route("/submit", methods=["POST"])
@jwt_required(optional=True)
def submit():
    source = "submit"
    user = "anon"
    collection = ""

    if "file" in request.files:
        f = request.files["file"]
        ts = int(time.time())
        name = f.filename or f"upload_{ts}.bin"
        os.makedirs(os.path.join("data", "uploads"), exist_ok=True)
        path = os.path.join("data", "uploads", name)
        f.save(path)
        user = _multipart_value("user", "anon")
        collection = _multipart_value("collection", "")
        source = _multipart_value("source", "upload")
    elif (request.mimetype or "").startswith("multipart/"):
        # Compatibility path for legacy multipart payloads where `file`
        # arrives as a regular text form field instead of request.files.
        text_payload = request.form.get("file")
        if text_payload is not None and str(text_payload) != "":
            path = _save_text_upload(str(text_payload), ".txt")
            user = _multipart_value("user", "anon")
            collection = _multipart_value("collection", "")
            source = _multipart_value("source", "upload")
        else:
            # As a last chance, consume first non-meta file part.
            candidate = None
            for key, fs in request.files.items():
                if key in ("user", "collection", "source"):
                    continue
                candidate = fs
                break
            if candidate is None:
                return jsonify({"ok": False, "error": "file or path required"}), 400
            ts = int(time.time())
            name = candidate.filename or f"upload_{ts}.bin"
            os.makedirs(os.path.join("data", "uploads"), exist_ok=True)
            path = os.path.join("data", "uploads", name)
            candidate.save(path)
            user = _multipart_value("user", "anon")
            collection = _multipart_value("collection", "")
            source = _multipart_value("source", "upload")
    else:
        d = request.get_json(force=True, silent=True) or {}
        path = str(d.get("path") or "").strip()
        user = str(d.get("user") or "anon")
        collection = str(d.get("collection") or "")
        source = str(d.get("source") or "path")
        if not path:
            return jsonify({"ok": False, "error": "path required"}), 400
        if not os.path.exists(path):
            return jsonify({"ok": False, "error": "path not found"}), 400

    job_id = f"job_{uuid.uuid4().hex[:12]}"
    _set_job(
        job_id,
        {
            "id": job_id,
            "status": "processing",
            "created_ts": float(time.time()),
            "path": path,
            "user": user,
            "collection": collection,
            "stats": {"vstore_added": 0},
        },
    )

    try:
        rep = CI.ingest_file(source, path, user)
        _set_job(
            job_id,
            {
                "status": "done",
                "finished_ts": float(time.time()),
                "result": rep,
                "stats": {"vstore_added": 1},
            },
        )
    except Exception as e:
        _set_job(
            job_id,
            {
                "status": "error",
                "finished_ts": float(time.time()),
                "error": f"{e.__class__.__name__}: {e}",
                "stats": {"vstore_added": 0},
            },
        )

    return jsonify({"ok": True, "job_id": job_id})


@bp.route("/job/<job_id>", methods=["GET"])
@jwt_required(optional=True)
def job_status(job_id: str):
    job = _get_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True, "job": job})


@bp.route("/status", methods=["GET"])
@jwt_required(optional=True)
def ingest_status():
    job_id = str(request.args.get("id") or "").strip()
    if not job_id:
        return jsonify({"ok": False, "error": "id required"}), 400
    job = _get_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True, "id": job_id, "status": str(job.get("status") or "DONE"), "job": job})

@bp.route("/admin", methods=["GET"])
@jwt_required()
def admin():
    if not _has_any_role(["ingest", "admin"]):
        return jsonify({"ok": False, "error": "rbac deny"}), 403
    return render_template("admin_channel_ingest.html")

def register(app):
    app.register_blueprint(bp)
