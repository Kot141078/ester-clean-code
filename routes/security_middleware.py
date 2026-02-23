# -*- coding: utf-8 -*-
"""
routes/security_middleware.py - per-request zaschita i nablyudaemost:
  • Proverka mTLS (cherez zagolovki ot reverse-proxy):
      MTLS_REQUIRED=1 → trebuem X-SSL-Client-Verify: SUCCESS
      Dopolnitelno MTLS_SUBJECT_REGEX (regex po Subject/Email),
      zagolovki: X-SSL-Client-Subject / X-SSL-Client-Email
  • Rate-limit per-IP/per-token (security/rate_limit.py)
  • Audit zaprosov (observability/audit)
  • Avtoinitsializatsiya OpenTelemetry (observability/otel) - no-op esli paket ne ustanovlen

Podklyuchenie:
  from routes.security_middleware import register_security_observability
  register_security_observability(app)

Mosty:
- Yavnyy: (Flask before/after_request ↔ Audit/RateLimit/OTel) - edinaya tochka zaschity i telemetrii.
- Skrytyy #1: (mTLS ↔ Profili dostupa) - proverka po zagolovkam proksi bez pryamoy kriptografii v prilozhenii.
- Skrytyy #2: (JWT ↔ Gostevoy dostup) - validatsiya tokena «optsionalna» (ne blokiruet anonimov), no obogaschaet audit.

Zemnoy abzats:
Eto «okhrannik u dveri tsekha»: puskaet po propuskam (mTLS/JWT), schitaet potok (rate limit)
i zapisyvaet v zhurnal, skolko zanyalo obsluzhivanie zaprosa. Realizatsiya bez setevykh vyzovov,
vse lokalno i bezopasno dlya zakrytoy korobki.
# c=a+b
"""
from __future__ import annotations

import os
import re
import time
import importlib
from typing import Any

from flask import g, jsonify, request

# V versii flask-jwt-extended ≥4.x net verify_jwt_in_request_optional;
# ispolzuetsya verify_jwt_in_request(optional=True).
from flask_jwt_extended import get_jwt_identity  # type: ignore
from flask_jwt_extended import verify_jwt_in_request  # type: ignore

# ---------------------------------------------------------------------------
# Nadezhnye importy observability.* s no-op-folbekami (ispravlenie ImportError)
# ---------------------------------------------------------------------------

# audit: ozhidaem modul observability.audit s funktsiey write(dict)
try:
    _audit_mod = importlib.import_module("observability.audit")
    if hasattr(_audit_mod, "write"):
        class _AuditProxy:
            @staticmethod
            def write(entry):  # type: ignore[no-redef]
                return _audit_mod.write(entry)  # type: ignore[attr-defined]
        audit_log = _AuditProxy()
    else:
        # myagkiy fallback, esli interfeys inoy
        class _AuditProxy:
            @staticmethod
            def write(entry):  # type: ignore[no-redef]
                try:
                    if hasattr(_audit_mod, "log"):
                        return _audit_mod.log(entry)  # type: ignore[attr-defined]
                except Exception:
                    pass
        audit_log = _AuditProxy()
except Exception:
    class _AuditNoop:
        @staticmethod
        def write(entry):  # type: ignore[no-redef]
            return None
    audit_log = _AuditNoop()

# otel: ozhidaem observability.otel s init_otel / instrument_flask_app / record_metric
try:
    otel = importlib.import_module("observability.otel")
except Exception:
    class _OtelNoop:
        @staticmethod
        def init_otel(service_name: str | None = None) -> bool: return False
        @staticmethod
        def instrument_flask_app(app: Any) -> bool: return False
        @staticmethod
        def record_metric(name: str, value: float, attributes: dict | None = None) -> None: return None
    otel = _OtelNoop()  # type: ignore

from security.rate_limit import get_rate_limiter
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _client_ip() -> str:
    xf = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    if xf:
        return xf
    return request.remote_addr or "0.0.0.0"


def _mtls_enforced() -> bool:
    return bool(int(os.getenv("MTLS_REQUIRED", "0") or 0))


def _mtls_subject_ok() -> bool:
    regex = os.getenv("MTLS_SUBJECT_REGEX") or ""
    if not regex:
        return True
    subj = request.headers.get("X-SSL-Client-Subject") or ""
    email = request.headers.get("X-SSL-Client-Email") or ""
    s = subj + " " + email
    try:
        return re.search(regex, s) is not None
    except Exception:
        return False


def register_security_observability(app):
    # Initsializiruem OpenTelemetry (no-op esli ne ustanovleno)
    try:
        otel.init_otel(service_name=os.getenv("OTEL_SERVICE_NAME", "ester-api"))
        otel.instrument_flask_app(app)
    except Exception:
        pass

    @app.before_request
    def _before():
        # mTLS (cherez proksi)
        if _mtls_enforced():
            verify = request.headers.get("X-SSL-Client-Verify", "")
            if verify != "SUCCESS" or not _mtls_subject_ok():
                audit_log.write({"event": "mtls_denied", "ip": _client_ip(), "path": request.path})
                return jsonify({"ok": False, "error": "mTLS required"}), 403

        # JWT (optsionalno)
        identity = None
        try:
            # Bylo: verify_jwt_in_request_optional() - otsutstvuet v 4.x.
            verify_jwt_in_request(optional=True)  # ne brosaet, esli tokena net
            identity = get_jwt_identity()
        except Exception:
            identity = None

        # Rate-limit
        ip = _client_ip()
        ok, retry_after, info = get_rate_limiter().check(
            ip=ip, token_id=str(identity) if identity else None
        )
        if not ok:
            audit_log.write({"event": "rate_limit", "ip": ip, "path": request.path, "info": info})
            resp = jsonify(
                {
                    "ok": False,
                    "error": "rate_limited",
                    "retry_after": round(retry_after, 3),
                }
            )
            resp.status_code = 429
            resp.headers["Retry-After"] = str(int(retry_after) + 1)
            return resp

        # dlya after_request
        g._start_ts = time.time()
        g._identity = identity
        g._client_ip = ip

    @app.after_request
    def _after(resp):
        try:
            dur = (time.time() - getattr(g, "_start_ts", time.time())) * 1000.0
            entry = {
                "event": "http_request",
                "ip": getattr(g, "_client_ip", "0.0.0.0"),
                "identity": getattr(g, "_identity", None),
                "method": request.method,
                "path": request.path,
                "status": resp.status_code,
                "duration_ms": round(dur, 2),
            }
            audit_log.write(entry)
            # OTEL metriki/spany (esli dostupny)
            otel.record_metric(
                "http.server.duration_ms",
                entry["duration_ms"],
                {"path": request.path, "status": resp.status_code},
            )
        except Exception:
            pass
        return resp


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
# zaglushka dlya security_middleware: poka net bp/router/register_*_routes
def register(app):
    return True

# === /AUTOSHIM ===