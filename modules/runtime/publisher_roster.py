# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from modules.runtime import bundle_signing

ROSTER_SCHEMA_V1 = "ester.publisher.roster.v1"
ROSTER_SIG_SCHEMA_V1 = "ester.publisher.roster_sig.v1"
ROSTER_SIG_MSG_V1 = "ester.publisher.roster_body_sha256.v1"


def _is_sha256_hex(value: str) -> bool:
    s = str(value or "").strip().lower()
    return len(s) == 64 and all(ch in "0123456789abcdef" for ch in s)


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def canonical_roster_body(roster: Dict[str, Any]) -> Dict[str, Any]:
    src = dict(roster or {})
    src.pop("sig", None)
    return src


def canonical_roster_body_bytes(roster: Dict[str, Any]) -> bytes:
    body = canonical_roster_body(roster)
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def compute_body_sha256(roster: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_roster_body_bytes(roster)).hexdigest()


def load_roster(path: str) -> Dict[str, Any]:
    raw_path = str(path or "").strip()
    if not raw_path:
        return {"ok": False, "error_code": "ROSTER_REQUIRED", "error": "roster_path_missing"}
    p = Path(raw_path).resolve()
    if not p.exists() or not p.is_file():
        return {"ok": False, "error_code": "ROSTER_REQUIRED", "error": "roster_file_missing", "path": str(p)}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"ok": False, "error_code": "ROSTER_SIG_INVALID", "error": "roster_json_invalid", "path": str(p)}
    if not isinstance(raw, dict):
        return {"ok": False, "error_code": "ROSTER_SIG_INVALID", "error": "roster_not_object", "path": str(p)}
    return {"ok": True, "roster": dict(raw), "path": str(p)}


def roster_root_dir(roster_path: str) -> Path:
    rp = Path(str(roster_path or "").strip()).resolve()
    parent = rp.parent
    if parent.name.lower() == "keys":
        return parent.parent.resolve()
    return parent.resolve()


def roster_body_message(body_sha256: str) -> bytes:
    s = str(body_sha256 or "").strip().lower()
    if not _is_sha256_hex(s):
        raise ValueError("roster_body_sha256_invalid")
    return f"{ROSTER_SIG_MSG_V1}:{s}".encode("ascii")


def _sort_keys(roster_keys: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted([dict(x) for x in roster_keys if isinstance(x, dict)], key=lambda row: str(row.get("key_id") or ""))


def normalize_roster(roster: Dict[str, Any]) -> Dict[str, Any]:
    src = dict(roster or {})
    src["schema"] = str(src.get("schema") or ROSTER_SCHEMA_V1)
    src["created_ts"] = _to_int(src.get("created_ts"))
    src["updated_ts"] = _to_int(src.get("updated_ts"))
    src["roster_id"] = str(src.get("roster_id") or "")
    policy = dict(src.get("policy") or {})
    src["policy"] = {
        "schema": str(policy.get("schema") or "ester.publisher.policy.v1"),
        "threshold": _to_int(policy.get("threshold")),
        "of": _to_int(policy.get("of")),
        "allow_legacy_single_sig": bool(policy.get("allow_legacy_single_sig", True)),
    }
    normalized_keys: List[Dict[str, Any]] = []
    for row in _sort_keys(list(src.get("keys") or [])):
        normalized_keys.append(
            {
                "key_id": str(row.get("key_id") or ""),
                "pub_path": str(row.get("pub_path") or ""),
                "pub_fingerprint": str(row.get("pub_fingerprint") or "").strip().lower(),
                "status": str(row.get("status") or "active").strip().lower(),
                "not_before_ts": _to_int(row.get("not_before_ts")),
                "not_after_ts": _to_int(row.get("not_after_ts")),
                "revoked_ts": _to_int(row.get("revoked_ts")),
                "comment": str(row.get("comment") or ""),
            }
        )
    src["keys"] = normalized_keys
    if "sig" in src and isinstance(src.get("sig"), dict):
        src["sig"] = dict(src.get("sig") or {})
    return src


def sign_roster(
    roster: Dict[str, Any],
    *,
    roster_root_privkey_path: str,
    roster_root_pubkey_path: str,
    key_id: str = "roster-root",
) -> Dict[str, Any]:
    if not bundle_signing.is_available():
        return {"ok": False, "error_code": "ED25519_UNAVAILABLE", "error": "ed25519_unavailable"}
    src = normalize_roster(roster)
    body_sha = compute_body_sha256(src)
    priv_path = str(roster_root_privkey_path or "").strip()
    pub_path = str(roster_root_pubkey_path or "").strip()
    if not priv_path or not pub_path:
        return {"ok": False, "error_code": "ROSTER_ROOT_PUBKEY_REQUIRED", "error": "roster_root_key_missing"}
    try:
        sk = bundle_signing.load_privkey(priv_path)
    except Exception:
        return {"ok": False, "error_code": "ROSTER_SIG_INVALID", "error": "roster_root_privkey_invalid"}
    pub_fp = bundle_signing.pub_fingerprint_from_path(pub_path)
    if not pub_fp:
        return {"ok": False, "error_code": "ROSTER_SIG_INVALID", "error": "roster_root_pubkey_invalid"}
    try:
        sig_raw = sk.sign(roster_body_message(body_sha))
    except Exception:
        return {"ok": False, "error_code": "ROSTER_SIG_INVALID", "error": "roster_sign_failed"}
    src["sig"] = {
        "schema": ROSTER_SIG_SCHEMA_V1,
        "alg": "ed25519",
        "key_id": str(key_id or "roster-root"),
        "msg": ROSTER_SIG_MSG_V1,
        "body_sha256": body_sha,
        "pub_fingerprint": pub_fp,
        "sig_b64": base64.b64encode(sig_raw).decode("ascii"),
    }
    return {"ok": True, "roster": src, "body_sha256": body_sha, "pub_fingerprint": pub_fp}


def verify_roster_sig(roster: Dict[str, Any], roster_root_pubkey_path: str) -> Dict[str, Any]:
    if not bundle_signing.is_available():
        return {"ok": False, "error_code": "ED25519_UNAVAILABLE", "error": "ed25519_unavailable"}
    src = normalize_roster(roster)
    if str(src.get("schema") or "") != ROSTER_SCHEMA_V1:
        return {"ok": False, "error_code": "ROSTER_SIG_INVALID", "error": "roster_schema_invalid"}
    sig = dict(src.get("sig") or {})
    if not sig:
        return {"ok": False, "error_code": "ROSTER_SIG_INVALID", "error": "roster_sig_missing"}
    if str(sig.get("schema") or "") != ROSTER_SIG_SCHEMA_V1:
        return {"ok": False, "error_code": "ROSTER_SIG_INVALID", "error": "roster_sig_schema_invalid"}
    if str(sig.get("alg") or "").strip().lower() != "ed25519":
        return {"ok": False, "error_code": "ROSTER_SIG_INVALID", "error": "roster_sig_alg_invalid"}
    if str(sig.get("msg") or "") != ROSTER_SIG_MSG_V1:
        return {"ok": False, "error_code": "ROSTER_SIG_INVALID", "error": "roster_sig_msg_invalid"}

    pub_path = str(roster_root_pubkey_path or "").strip()
    if not pub_path:
        return {"ok": False, "error_code": "ROSTER_ROOT_PUBKEY_REQUIRED", "error": "roster_root_pubkey_missing"}

    body_sha = compute_body_sha256(src)
    claimed_sha = str(sig.get("body_sha256") or "").strip().lower()
    if claimed_sha != body_sha:
        return {"ok": False, "error_code": "ROSTER_SIG_INVALID", "error": "roster_body_sha256_mismatch", "body_sha256": body_sha}

    try:
        pk = bundle_signing.load_pubkey(pub_path)
    except Exception:
        return {"ok": False, "error_code": "ROSTER_SIG_INVALID", "error": "roster_root_pubkey_invalid", "body_sha256": body_sha}
    actual_fp = bundle_signing.pub_fingerprint(pk)
    claimed_fp = str(sig.get("pub_fingerprint") or "").strip().lower()
    if claimed_fp and claimed_fp != actual_fp:
        return {
            "ok": False,
            "error_code": "ROSTER_SIG_INVALID",
            "error": "roster_root_fingerprint_mismatch",
            "body_sha256": body_sha,
            "pub_fingerprint": actual_fp,
        }
    try:
        sig_raw = base64.b64decode(str(sig.get("sig_b64") or "").strip(), validate=True)
    except Exception:
        return {"ok": False, "error_code": "ROSTER_SIG_INVALID", "error": "roster_sig_invalid", "body_sha256": body_sha}
    if len(sig_raw) != 64:
        return {"ok": False, "error_code": "ROSTER_SIG_INVALID", "error": "roster_sig_invalid", "body_sha256": body_sha}
    try:
        pk.verify(sig_raw, roster_body_message(body_sha))
    except Exception:
        return {"ok": False, "error_code": "ROSTER_SIG_INVALID", "error": "roster_sig_invalid", "body_sha256": body_sha}
    return {
        "ok": True,
        "error_code": "",
        "error": "",
        "body_sha256": body_sha,
        "roster_id": str(src.get("roster_id") or ""),
        "pub_fingerprint": actual_fp,
    }


def find_key(roster: Dict[str, Any], key_id: str) -> Dict[str, Any]:
    target = str(key_id or "").strip()
    for row in list(dict(roster or {}).get("keys") or []):
        if not isinstance(row, dict):
            continue
        if str(row.get("key_id") or "").strip() == target:
            return dict(row)
    return {}


def is_key_active_at(roster_key: Dict[str, Any], ts: int) -> Dict[str, Any]:
    src = dict(roster_key or {})
    key_id = str(src.get("key_id") or "")
    now_ts = _to_int(ts)
    status = str(src.get("status") or "active").strip().lower()
    not_before_ts = _to_int(src.get("not_before_ts"))
    not_after_ts = _to_int(src.get("not_after_ts"))
    revoked_ts = _to_int(src.get("revoked_ts"))

    if revoked_ts > 0 and now_ts >= revoked_ts:
        return {"ok": False, "error_code": "ROSTER_KEY_REVOKED", "error": "roster_key_revoked", "key_id": key_id}
    if status == "revoked":
        return {"ok": False, "error_code": "ROSTER_KEY_REVOKED", "error": "roster_key_revoked", "key_id": key_id}
    if not_before_ts > 0 and now_ts < not_before_ts:
        return {"ok": False, "error_code": "ROSTER_KEY_NOT_ACTIVE", "error": "roster_key_not_active", "key_id": key_id}
    if not_after_ts > 0 and now_ts > not_after_ts:
        return {"ok": False, "error_code": "ROSTER_KEY_NOT_ACTIVE", "error": "roster_key_not_active", "key_id": key_id}
    if status != "active":
        return {"ok": False, "error_code": "ROSTER_KEY_NOT_ACTIVE", "error": "roster_key_not_active", "key_id": key_id}
    return {"ok": True, "error_code": "", "error": "", "key_id": key_id}


def resolve_pubkey_for_key_id(roster: Dict[str, Any], key_id: str, roster_path: str) -> Dict[str, Any]:
    key = find_key(roster, key_id)
    if not key:
        return {"ok": False, "error_code": "ROSTER_KEY_UNKNOWN", "error": "roster_key_unknown"}
    root = roster_root_dir(roster_path)
    rel = str(key.get("pub_path") or "").strip().replace("\\", "/")
    if not rel:
        return {"ok": False, "error_code": "ROSTER_KEY_UNKNOWN", "error": "roster_key_pub_path_missing", "key": key}
    if Path(rel).is_absolute():
        return {"ok": False, "error_code": "ROSTER_KEY_UNKNOWN", "error": "roster_key_pub_path_absolute", "key": key}
    target = (root / rel).resolve()
    if not _path_within(target, root):
        return {"ok": False, "error_code": "ROSTER_KEY_UNKNOWN", "error": "roster_key_pub_path_forbidden", "key": key}
    if not target.exists() or not target.is_file():
        return {"ok": False, "error_code": "PUBLISHER_PUBKEY_MISSING", "error": "publisher_pubkey_missing", "key": key}
    return {"ok": True, "path": str(target), "key": key, "root": str(root)}


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


__all__ = [
    "ROSTER_SCHEMA_V1",
    "ROSTER_SIG_SCHEMA_V1",
    "ROSTER_SIG_MSG_V1",
    "canonical_roster_body",
    "canonical_roster_body_bytes",
    "compute_body_sha256",
    "load_roster",
    "roster_root_dir",
    "normalize_roster",
    "sign_roster",
    "verify_roster_sig",
    "find_key",
    "is_key_active_at",
    "resolve_pubkey_for_key_id",
]
