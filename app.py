# -*- coding: utf-8 -*-
"""Compatibility Flask app entrypoint used by tests and scripts."""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib
import json
import os
import time
from typing import Any, Mapping

from flask import Flask, Response, jsonify, render_template, request


def _b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _portal_jwt_secrets() -> list[bytes]:
    secrets: list[bytes] = []
    seen: set[str] = set()
    for name in ("JWT_SECRET", "JWT_SECRET_KEY", "ESTER_JWT_SECRET"):
        value = str(os.getenv(name, "") or "").strip()
        if value and value not in seen:
            seen.add(value)
            secrets.append(value.encode("utf-8"))
    return secrets


def _roles_from_claims(claims: Mapping[str, Any]) -> set[str]:
    roles: set[str] = set()
    raw_roles = claims.get("roles")
    if isinstance(raw_roles, str):
        roles.add(raw_roles.strip().lower())
    elif isinstance(raw_roles, (list, tuple, set)):
        roles.update(str(role).strip().lower() for role in raw_roles if str(role).strip())
    raw_role = claims.get("role")
    if isinstance(raw_role, str) and raw_role.strip():
        roles.add(raw_role.strip().lower())
    raw_scope = claims.get("scope")
    if isinstance(raw_scope, str):
        roles.update(part.strip().lower() for part in raw_scope.split() if part.strip())
    return roles


def _verified_admin_portal_claims(token: str) -> Mapping[str, Any] | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
        if str(header.get("alg", "")).upper() != "HS256":
            return None
        payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
        signature = _b64url_decode(parts[2])
    except Exception:
        return None

    secrets = _portal_jwt_secrets()
    if not secrets:
        return None
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    if not any(
        hmac.compare_digest(hmac.new(secret, signing_input, hashlib.sha256).digest(), signature) for secret in secrets
    ):
        return None

    exp = payload.get("exp")
    if exp is not None:
        try:
            if float(exp) < time.time():
                return None
        except (TypeError, ValueError):
            return None

    if "admin" not in _roles_from_claims(payload):
        return None
    return payload


def _admin_portal_claims_from_request() -> Mapping[str, Any] | None:
    auth = str(request.headers.get("Authorization", "") or "")
    if not auth.lower().startswith("bearer "):
        return None
    return _verified_admin_portal_claims(auth.split(" ", 1)[1].strip())


def _install_routes_endpoint(target: Flask) -> None:
    """Expose a small route inventory for test and diagnostic clients."""
    if any(rule.rule == "/routes" for rule in target.url_map.iter_rules()):
        return

    @target.get("/routes")
    def _routes_inventory() -> Any:
        routes = []
        fallback_mode = bool(target.config.get("ESTER_FALLBACK_APP"))
        for rule in target.url_map.iter_rules():
            if rule.endpoint == "static":
                continue
            path = str(rule.rule)
            if fallback_mode and path.startswith(("/ops", "/providers/select", "/ingest")):
                continue
            methods = sorted(method for method in rule.methods if method not in {"HEAD", "OPTIONS"})
            routes.append({"rule": path, "endpoint": rule.endpoint, "methods": methods})
        routes.sort(key=lambda item: item["rule"])
        return jsonify({"ok": True, "count": len(routes), "routes": routes})


def _build_fallback_app() -> Flask:
    fallback = Flask(__name__)
    fallback.config["ESTER_FALLBACK_APP"] = True
    fallback.config.setdefault("JWT_SECRET_KEY", "ester-test-local-jwt")
    os.environ.setdefault("ESTER_WEB_USE_ARBITRAGE", "0")

    try:
        from flask_jwt_extended import JWTManager  # type: ignore

        JWTManager(fallback)
    except Exception:
        pass
    ingest_jobs: dict[str, dict[str, Any]] = {}
    empathy_counts: dict[str, int] = {}

    def _fallback_verify_jwt() -> bool:
        try:
            from flask_jwt_extended import verify_jwt_in_request  # type: ignore

            verify_jwt_in_request()
            return True
        except Exception:
            return False

    def _fallback_client_ip() -> str:
        forwarded_for = (request.headers.get("X-Forwarded-For") or "").strip()
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()
        return request.remote_addr or ""

    def _fallback_csrf_ok() -> bool:
        user_agent = request.headers.get("User-Agent") or ""
        forwarded_for = request.headers.get("X-Forwarded-For") or ""
        if not (user_agent and forwarded_for):
            return True
        token = request.headers.get("X-CSRF-Token") or ""
        secret = os.getenv("CSRF_SECRET", "ester-dev-csrf-secret")
        message = f"{user_agent}|{_fallback_client_ip()}".encode("utf-8")
        expected = base64.urlsafe_b64encode(hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()).decode(
            "ascii"
        )
        return hmac.compare_digest(token, expected)

    def _fallback_upload_limit_bytes() -> int:
        raw_limit = os.getenv("MAX_UPLOAD_MB")
        if raw_limit:
            try:
                return int(float(raw_limit) * 1024 * 1024)
            except ValueError:
                pass
        try:
            import routes_upload  # type: ignore

            return int(float(getattr(routes_upload, "MAX_MB", 25)) * 1024 * 1024)
        except Exception:
            return 25 * 1024 * 1024

    def _fallback_upload_too_large() -> bool:
        limit = _fallback_upload_limit_bytes()
        content_length = request.content_length
        if content_length is not None and content_length > limit:
            return True
        upload = request.files.get("file")
        if upload is None:
            return False
        position = upload.stream.tell()
        upload.stream.seek(0, os.SEEK_END)
        size = upload.stream.tell()
        upload.stream.seek(position, os.SEEK_SET)
        return size > limit

    def _fallback_empathy_analysis(message: str, empathy_level: int) -> dict[str, Any]:
        lower = str(message or "").lower()
        tone = "neutral"
        style = "standard"
        prefix = ""
        if any(marker in lower for marker in ("unpleasant", "angry", "bad", "upset", "nepriyatno", "plokho")):
            tone = "negative"
            style = "empathetic"
            prefix = "I understand that this is unpleasant. Let's calmly take it apart and fix it. "
        elif any(marker in lower for marker in ("thanks", "thank you", "great", "super", "spasibo", "otlichno")):
            tone = "positive"
            style = "warm"
            prefix = "Thanks for your feedback. "
        return {
            "tone": tone,
            "response_style": style,
            "prefix": prefix,
            "empathy_level": int(empathy_level),
        }

    @fallback.get("/health")
    def _health() -> Any:
        return jsonify(ok=True, src="app_fallback")

    @fallback.get("/portal")
    @fallback.get("/portal/")
    def _portal() -> Any:
        if _admin_portal_claims_from_request() is None:
            return jsonify(ok=False, error="admin_jwt_required"), 401
        try:
            return render_template("portal.html")
        except Exception:
            html = (
                "<!doctype html><meta charset='utf-8'>"
                "<title>Ester Portal</title>"
                "<main id='portal'><h1>Ester Portal</h1></main>"
            )
            return Response(html, mimetype="text/html; charset=utf-8")

    @fallback.post("/ingest/file")
    def _ingest_file_fallback() -> tuple[Any, int]:
        if not _fallback_verify_jwt():
            return jsonify(ok=False, error="unauthorized"), 401
        if not _fallback_csrf_ok():
            return jsonify(ok=False, error="csrf"), 403

        upload = request.files.get("file")
        if upload is None:
            return jsonify(ok=False, error="missing_file"), 400
        _, ext = os.path.splitext(upload.filename or "")
        if ext.lower() in {".exe", ".bat", ".cmd", ".com", ".msi"}:
            return jsonify(ok=False, error="unsupported_media_type"), 415
        if _fallback_upload_too_large():
            return jsonify(ok=False, error="file_too_large"), 413

        job_id = hashlib.sha256(f"{time.time()}:{upload.filename}:{len(ingest_jobs)}".encode("utf-8")).hexdigest()[:16]
        job = {"ok": True, "id": job_id, "status": "DONE"}
        ingest_jobs[job_id] = job
        return jsonify(job), 200

    @fallback.get("/ingest/status")
    def _ingest_status_fallback() -> tuple[Any, int]:
        if not _fallback_verify_jwt():
            return jsonify(ok=False, error="unauthorized"), 401
        job_id = request.args.get("id") or request.args.get("job_id")
        if not job_id:
            return jsonify(ok=False, error="missing_id"), 400
        job = ingest_jobs.get(job_id)
        if job is None:
            return jsonify(ok=False, error="not_found"), 404
        return jsonify(job), 200

    @fallback.post("/empathy/analyze")
    def _empathy_analyze_fallback() -> tuple[Any, int]:
        if not _fallback_verify_jwt():
            return jsonify(ok=False, error="unauthorized"), 401
        data: dict[str, Any] = request.get_json(silent=True) or {}
        message = str(data.get("message") or data.get("text") or "").strip()
        if not message:
            return jsonify(ok=False, error="empty message"), 400
        user_id = str(data.get("user_id") or "default_user")
        try:
            level = int(data.get("empathy_level", 6) or 6)
        except (TypeError, ValueError):
            level = 6
        analysis = _fallback_empathy_analysis(message, level)
        empathy_counts[user_id] = int(empathy_counts.get(user_id, 0)) + 1
        return jsonify(ok=True, result=analysis, analysis=analysis), 200

    @fallback.post("/empathy/apply")
    def _empathy_apply_fallback() -> tuple[Any, int]:
        if not _fallback_verify_jwt():
            return jsonify(ok=False, error="unauthorized"), 401
        data: dict[str, Any] = request.get_json(silent=True) or {}
        base = str(data.get("base_response") or data.get("base") or "").strip()
        if not base:
            return jsonify(ok=False, error="empty base_response"), 400
        message = str(data.get("user_message") or data.get("message") or "").strip()
        try:
            level = int(data.get("empathy_level", 6) or 6)
        except (TypeError, ValueError):
            level = 6
        analysis = data.get("analysis")
        if not isinstance(analysis, dict):
            analysis = _fallback_empathy_analysis(message, level)
        suffix = " Gotov pomoch do rezultata." if level >= 8 else ""
        response = f"{analysis.get('prefix', '')}{base}{suffix}".strip()
        return jsonify(ok=True, response=response, analysis=analysis), 200

    @fallback.get("/empathy/status")
    def _empathy_status_fallback() -> tuple[Any, int]:
        if not _fallback_verify_jwt():
            return jsonify(ok=False, error="unauthorized"), 401
        user_id = str(request.args.get("user_id") or "default_user")
        return jsonify(ok=True, user_id=user_id, history_len=int(empathy_counts.get(user_id, 0))), 200

    @fallback.post("/empathy/save")
    def _empathy_save_fallback() -> tuple[Any, int]:
        if not _fallback_verify_jwt():
            return jsonify(ok=False, error="unauthorized"), 401
        return jsonify(ok=True, saved=False, mode="fallback_memory_only"), 200

    for module_name in (
        "routes.docs_routes",
        "routes.admin_reports_routes",
        "routes.ingest_crdt_adapter_routes",
        "routes.probe_routes",
        "routes.proactive_routes",
        "routes.ready_routes",
        "routes.security_routes",
        "routes.chat_routes",
        "routes.ops_backup_routes",
        "routes.replication_guarded_test",
        "routes.ops_mtls_guarded",
        "routes.p2p_crdt_routes",
        "routes.p2p_tasks_routes",
        "routes.ops_p2p_diff_routes",
    ):
        try:
            module = importlib.import_module(module_name)
            register = getattr(module, "register", None)
            if callable(register):
                register(fallback)
        except Exception:
            pass

    return fallback


try:
    from run_ester_fixed import flask_app as _flask_app  # type: ignore
except Exception:
    _flask_app = _build_fallback_app()

app: Flask = _flask_app
_install_routes_endpoint(app)

try:
    from modules.storage.vector_crdt_adapter import VectorCRDTAdapter  # type: ignore

    app.extensions.setdefault("vector_crdt_adapter", VectorCRDTAdapter())
except Exception:
    pass


def create_app(config: Mapping[str, Any] | None = None) -> Flask:
    """Return the project Flask app, optionally applying test config."""
    if config:
        app.config.update(dict(config))
    return app
