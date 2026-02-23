# -*- coding: utf-8 -*-
from __future__ import annotations

"""
routes/routes_replication.py

Unified replication HTTP routes used by tests and runtime app wiring.
This module exposes a module-level Blueprint so autoscan registration works,
and also keeps register_replication_routes(app, replicator, ...) for legacy callers.
"""

import base64
import hashlib
import hmac
import io
import os
import time
import zipfile
from typing import Any, Dict, List, Optional

from flask import Blueprint, Response, jsonify, request

try:
    from flask_jwt_extended import jwt_required  # type: ignore
except Exception:  # pragma: no cover
    def jwt_required(*_args, **_kwargs):  # type: ignore
        def _wrap(fn):
            return fn
        return _wrap

try:
    from security.signing import get_hmac_key as _security_get_hmac_key  # type: ignore
except Exception:  # pragma: no cover
    _security_get_hmac_key = None  # type: ignore


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _env_token() -> str:
    return str(os.getenv("REPLICATION_TOKEN") or os.getenv("REPL_TOKEN") or "").strip()


def _env_include_dirs_raw() -> str:
    return str(os.getenv("REPLICATION_INCLUDE_DIRS") or os.getenv("REPL_INCLUDE_DIRS") or "").strip()


def _hmac_key_bytes() -> bytes:
    repl_key = str(os.getenv("REPL_HMAC_KEY") or "").strip()
    if repl_key:
        key = repl_key
    elif callable(_security_get_hmac_key):
        try:
            raw = _security_get_hmac_key()
            if isinstance(raw, bytes):
                return raw
            return str(raw).encode("utf-8", errors="ignore")
        except Exception:
            key = ""
    else:
        key = ""

    if not key:
        key = (
            os.getenv("REPLICATION_HMAC_KEY")
            or os.getenv("P2P_HMAC_KEY")
            or os.getenv("HMAC_KEY")
            or os.getenv("ESTER_HMAC_KEY")
            or os.getenv("HMAC_SECRET")
            or os.getenv("SIGNING_KEY")
            or "ester-hmac-key"
        )
    key_s = str(key).strip()

    if key_s.startswith("b64:"):
        try:
            return base64.b64decode(key_s[4:].strip())
        except Exception:
            return key_s[4:].strip().encode("utf-8", errors="ignore")

    if len(key_s) >= 32 and all(c.isalnum() or c in "+/=_-" for c in key_s):
        try:
            return base64.urlsafe_b64decode(key_s + "===")
        except Exception:
            pass

    return key_s.encode("utf-8", errors="ignore")


def _parse_dirs(value: str) -> List[str]:
    out: List[str] = []
    for part in (value or "").split(","):
        p = part.strip()
        if not p:
            continue
        p_abs = os.path.abspath(p)
        if p_abs not in out:
            out.append(p_abs)

    if out:
        return out

    persist_dir = str(os.getenv("PERSIST_DIR") or "").strip()
    if persist_dir:
        return [os.path.abspath(persist_dir)]

    return [os.path.abspath("data")]


def _require_token(req) -> Optional[Response]:
    """
    Guard semantics:
    - If REPLICATION_TOKEN/REPL_TOKEN is configured: require exact match (401 on mismatch).
    - If token is not configured: still require explicit X-REPL-TOKEN header presence,
      otherwise return 503 (fail-closed behavior for unconfigured replication gate).
    """
    want = _env_token()
    got = req.headers.get("X-REPL-TOKEN")

    if want:
        if got != want:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        return None

    if got is None:
        return jsonify({"ok": False, "error": "replication token not configured"}), 503
    return None


# ---------------------------------------------------------------------------
# Signature helpers
# ---------------------------------------------------------------------------

def hmac_sign(blob: bytes) -> str:
    mac = hmac.new(_hmac_key_bytes(), blob, hashlib.sha256).hexdigest().lower()
    return "hmac-" + mac


def hmac_verify(blob: bytes, sig: str) -> bool:
    raw = str(sig or "").strip().lower()
    if not raw:
        return False
    if raw.startswith("hmac-"):
        raw = raw[len("hmac-") :]
    if raw.startswith("hmac-sha256:"):
        raw = raw.split(":", 1)[1]
    if raw.startswith("sha256="):
        raw = raw.split("=", 1)[1]

    if any(c not in "0123456789abcdef" for c in raw):
        return False

    expected = hmac.new(_hmac_key_bytes(), blob, hashlib.sha256).hexdigest().lower()
    return hmac.compare_digest(expected, raw)


# ---------------------------------------------------------------------------
# Zip helpers
# ---------------------------------------------------------------------------

def _safe_tag_from_dir(path: str) -> str:
    base = os.path.basename(os.path.normpath(path)) or "dir"
    base = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in base)[:32] or "dir"
    return base


def _zip_dirs(include_dirs: List[str]) -> bytes:
    max_total_mb = max(1, int(str(os.getenv("REPLICATION_SNAPSHOT_MAX_MB") or "32")))
    max_file_mb = max(1, int(str(os.getenv("REPLICATION_SNAPSHOT_MAX_FILE_MB") or "8")))
    max_files = max(1, int(str(os.getenv("REPLICATION_SNAPSHOT_MAX_FILES") or "2000")))
    max_total_bytes = max_total_mb * 1024 * 1024
    max_file_bytes = max_file_mb * 1024 * 1024

    skip_dir_names = {
        ".git",
        "__pycache__",
        "node_modules",
        "venv",
        ".venv",
        "models",
        "model",
        "snapshots",
        "backups",
    }

    packed_bytes = 0
    packed_files = 0
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for d in include_dirs:
            d_abs = os.path.abspath(d)
            if not os.path.isdir(d_abs):
                continue
            tag = _safe_tag_from_dir(d_abs)
            for root, dirnames, files in os.walk(d_abs):
                dirnames[:] = [dname for dname in dirnames if dname.casefold() not in skip_dir_names]
                for name in files:
                    if packed_files >= max_files or packed_bytes >= max_total_bytes:
                        break
                    full = os.path.join(root, name)
                    try:
                        size = int(os.path.getsize(full))
                    except Exception:
                        continue
                    if size > max_file_bytes:
                        continue
                    if packed_bytes + size > max_total_bytes:
                        continue
                    rel = os.path.relpath(full, start=d_abs).replace("\\", "/")
                    if rel.startswith(".."):
                        continue
                    arcname = f"payload/{tag}/{rel}"
                    zf.write(full, arcname=arcname)
                    packed_bytes += size
                    packed_files += 1
                if packed_files >= max_files or packed_bytes >= max_total_bytes:
                    break
    buf.seek(0)
    return buf.read()


def _apply_zip(blob: bytes, include_dirs: List[str]) -> Dict[str, Any]:
    max_mb = int(str(os.getenv("REPLICATION_MAX_ZIP_MB") or "250"))
    if len(blob) > max_mb * 1024 * 1024:
        return {
            "ok": False,
            "error": "zip_too_large",
            "max_mb": max_mb,
            "size": len(blob),
        }

    tag_map: Dict[str, str] = {}
    for d in include_dirs:
        d_abs = os.path.abspath(d)
        tag_map[_safe_tag_from_dir(d_abs)] = d_abs

    changed = 0
    skipped = 0
    rejected = 0
    errors = 0

    with zipfile.ZipFile(io.BytesIO(blob), "r") as zf:
        for zi in zf.infolist():
            try:
                name = zi.filename.replace("\\", "/")
                if not name.startswith("payload/"):
                    rejected += 1
                    continue

                rest = name[len("payload/") :]
                parts = [p for p in rest.split("/") if p]
                if len(parts) < 2:
                    rejected += 1
                    continue

                tag = parts[0]
                rel = "/".join(parts[1:])
                if not rel or rel.startswith("..") or "/../" in rel or rel.startswith("/"):
                    rejected += 1
                    continue

                base_dir = tag_map.get(tag)
                if not base_dir:
                    rejected += 1
                    continue

                target = os.path.abspath(os.path.join(base_dir, rel))
                base_norm = os.path.abspath(base_dir)
                if not (target == base_norm or target.startswith(base_norm + os.sep)):
                    rejected += 1
                    continue

                os.makedirs(os.path.dirname(target), exist_ok=True)

                try:
                    incoming_mtime = time.mktime(zi.date_time + (0, 0, -1))
                except Exception:
                    incoming_mtime = time.time()

                if os.path.exists(target):
                    try:
                        if os.path.getmtime(target) >= incoming_mtime:
                            skipped += 1
                            continue
                    except Exception:
                        pass

                with zf.open(zi, "r") as src, open(target, "wb") as dst:
                    dst.write(src.read())

                try:
                    os.utime(target, (incoming_mtime, incoming_mtime))
                except Exception:
                    pass

                changed += 1
            except Exception:
                errors += 1

    return {
        "ok": True,
        "changed": changed,
        "skipped": skipped,
        "rejected": rejected,
        "errors": errors,
        "files": changed,
    }


# ---------------------------------------------------------------------------
# Replicator adapter
# ---------------------------------------------------------------------------

class _LocalReplicator:
    def __init__(self, peers: Optional[List[str]] = None):
        self.peers = list(peers or [])
        self.running = False
        self.last_pull: Optional[float] = None
        self.last_report: Dict[str, Any] = {"pulled": 0, "reports": {}}

    def status(self) -> Dict[str, Any]:
        return {
            "peers": list(self.peers),
            "running": bool(self.running),
            "last_pull": self.last_pull,
            "last_report": self.last_report,
        }

    def pull_once(self) -> Dict[str, Any]:
        rep = {"pulled": 0, "reports": {}}
        self.last_pull = time.time()
        self.last_report = rep
        return rep


_REPLICATOR: Any = _LocalReplicator(
    peers=[p.strip() for p in str(os.getenv("REPLICATION_PEERS") or "").split(",") if p.strip()]
)


def _repl_status_payload() -> Dict[str, Any]:
    try:
        data = dict(_REPLICATOR.status()) if _REPLICATOR is not None else {}
    except Exception:
        data = {}
    data.setdefault("peers", [])
    data.setdefault("running", False)
    data.setdefault("last_pull", None)
    data.setdefault("last_report", {})
    return data


def _repl_pull_once_payload() -> Dict[str, Any]:
    try:
        report = dict(_REPLICATOR.pull_once()) if _REPLICATOR is not None else {}
    except Exception as exc:
        report = {"ok": False, "error": str(exc), "pulled": 0, "reports": {}}

    if "pulled" not in report:
        reports = report.get("reports")
        if isinstance(reports, dict):
            report["pulled"] = len(reports)
        elif isinstance(reports, list):
            report["pulled"] = len(reports)
        else:
            report["pulled"] = 0
    report.setdefault("reports", {})
    return report


# ---------------------------------------------------------------------------
# Blueprint endpoints
# ---------------------------------------------------------------------------

bp = Blueprint("replication_routes_core", __name__)


@bp.get("/replication/status")
@jwt_required()
def repl_status():
    return jsonify(_repl_status_payload())


@bp.post("/replication/pull_now")
@jwt_required()
def repl_pull_now():
    return jsonify({"ok": True, "report": _repl_pull_once_payload()})


@bp.get("/replication/snapshot")
def repl_snapshot():
    guard = _require_token(request)
    if guard is not None:
        return guard

    include = _parse_dirs(_env_include_dirs_raw())
    blob = _zip_dirs(include)
    sig = hmac_sign(blob)

    resp = Response(blob, mimetype="application/zip")
    resp.headers["X-Signature"] = sig
    resp.headers["X-Signature-Alg"] = "hmac-sha256"
    resp.headers["X-Include"] = ",".join(include)
    return resp


@bp.post("/replication/apply")
def repl_apply():
    guard = _require_token(request)
    if guard is not None:
        return guard

    sig = str(request.headers.get("X-Signature") or "").strip()
    blob = request.get_data() or b""

    if not sig or not hmac_verify(blob, sig):
        return jsonify({"ok": False, "error": "bad signature"}), 400

    include = _parse_dirs(_env_include_dirs_raw())
    rep = _apply_zip(blob, include)

    stats = {
        "files": int(rep.get("files") or rep.get("changed") or 0),
        "changed": int(rep.get("changed") or 0),
        "skipped": int(rep.get("skipped") or 0),
        "rejected": int(rep.get("rejected") or 0),
        "errors": int(rep.get("errors") or 0),
    }

    status = 200 if rep.get("ok") else 413
    return jsonify({"ok": bool(rep.get("ok")), "stats": stats, "report": rep}), status


# ---------------------------------------------------------------------------
# Public registration API
# ---------------------------------------------------------------------------

def register_replication_routes(app, replicator=None, url_prefix: str = "/replication"):
    """
    Legacy entrypoint used by tests.
    `url_prefix` is kept for compatibility; current blueprint routes are canonical /replication/*.
    """
    global _REPLICATOR

    if replicator is not None:
        _REPLICATOR = replicator

    # Best-effort normalization of legacy replicator objects.
    if _REPLICATOR is not None and not hasattr(_REPLICATOR, "status"):
        _REPLICATOR = _LocalReplicator()

    # Register canonical blueprint once.
    if bp.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(bp)

    # Compatibility mode: optional extra prefixed aliases.
    pref = str(url_prefix or "").strip()
    if pref and pref != "/replication":
        alias_name = "replication_routes_alias"
        if alias_name not in getattr(app, "blueprints", {}):
            alias = Blueprint(alias_name, __name__, url_prefix=pref)

            @alias.get("/status")
            @jwt_required()
            def _status_alias():
                return repl_status()

            @alias.post("/pull_now")
            @jwt_required()
            def _pull_alias():
                return repl_pull_now()

            @alias.get("/snapshot")
            def _snapshot_alias():
                return repl_snapshot()

            @alias.post("/apply")
            def _apply_alias():
                return repl_apply()

            app.register_blueprint(alias)

    return bp


def register(app):
    return register_replication_routes(app)


__all__ = ["register_replication_routes", "register", "hmac_sign", "hmac_verify", "bp"]
