# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any, Dict, List

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

    _ED25519_OK = True
except Exception:  # pragma: no cover
    serialization = None  # type: ignore
    Ed25519PrivateKey = None  # type: ignore
    Ed25519PublicKey = None  # type: ignore
    _ED25519_OK = False

_DOMAIN = "ester.l4w.bundle_tree_sha256.v1"


def _is_sha256_hex(value: str) -> bool:
    s = str(value or "").strip().lower()
    return len(s) == 64 and all(ch in "0123456789abcdef" for ch in s)


def _message_bytes(tree_hash_hex: str) -> bytes:
    s = str(tree_hash_hex or "").strip().lower()
    if not _is_sha256_hex(s):
        raise ValueError("tree_hash_invalid")
    return (f"{_DOMAIN}:{s}").encode("ascii")


def is_available() -> bool:
    return bool(_ED25519_OK)


def load_privkey(path: str) -> Any:
    if not _ED25519_OK:
        raise ValueError("ed25519_unavailable")
    p = Path(str(path or "").strip()).resolve()
    obj = serialization.load_pem_private_key(p.read_bytes(), password=None)
    if not isinstance(obj, Ed25519PrivateKey):
        raise ValueError("publisher_privkey_invalid")
    return obj


def load_pubkey(path: str) -> Any:
    if not _ED25519_OK:
        raise ValueError("ed25519_unavailable")
    p = Path(str(path or "").strip()).resolve()
    obj = serialization.load_pem_public_key(p.read_bytes())
    if not isinstance(obj, Ed25519PublicKey):
        raise ValueError("publisher_pubkey_invalid")
    return obj


def pub_fingerprint(pubkey: Any) -> str:
    if not _ED25519_OK or not isinstance(pubkey, Ed25519PublicKey):
        return ""
    raw = pubkey.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return hashlib.sha256(raw).hexdigest()


def pub_fingerprint_from_path(path: str) -> str:
    try:
        return pub_fingerprint(load_pubkey(path))
    except Exception:
        return ""


def sign_tree_hash(tree_hash_hex: str, priv_path: str, key_id: str = "publisher-default") -> Dict[str, Any]:
    if not _ED25519_OK:
        raise ValueError("ed25519_unavailable")
    msg = _message_bytes(tree_hash_hex)
    sk = load_privkey(priv_path)
    pk = sk.public_key()
    sig_raw = sk.sign(msg)
    return {
        "schema": "ester.l4w.publisher_sig.v1",
        "alg": "ed25519",
        "key_id": str(key_id or "publisher-default"),
        "msg": _DOMAIN,
        "signed": str(tree_hash_hex or "").strip().lower(),
        "pub_fingerprint": pub_fingerprint(pk),
        "sig_b64": base64.b64encode(sig_raw).decode("ascii"),
    }


def verify_tree_hash_sig(tree_hash_hex: str, publisher_sig: Dict[str, Any], pub_path: str) -> Dict[str, Any]:
    if not _ED25519_OK:
        return {"ok": False, "error_code": "ED25519_UNAVAILABLE", "error": "ed25519_unavailable"}
    if not _is_sha256_hex(str(tree_hash_hex or "")):
        return {"ok": False, "error_code": "PUBLISHER_TREE_HASH_INVALID", "error": "tree_hash_invalid"}
    sig = dict(publisher_sig or {})
    if str(sig.get("schema") or "") != "ester.l4w.publisher_sig.v1":
        return {"ok": False, "error_code": "PUBLISHER_SIG_SCHEMA_INVALID", "error": "publisher_sig_schema_invalid"}
    if str(sig.get("alg") or "").strip().lower() != "ed25519":
        return {"ok": False, "error_code": "PUBLISHER_SIG_SCHEMA_INVALID", "error": "publisher_sig_alg_invalid"}
    if str(sig.get("msg") or "") != _DOMAIN:
        return {"ok": False, "error_code": "PUBLISHER_SIG_SCHEMA_INVALID", "error": "publisher_sig_msg_invalid"}
    signed = str(sig.get("signed") or "").strip().lower()
    if signed != str(tree_hash_hex or "").strip().lower():
        return {"ok": False, "error_code": "PUBLISHER_SIG_SIGNED_MISMATCH", "error": "publisher_sig_signed_mismatch"}
    pub_raw = str(pub_path or "").strip()
    if not pub_raw:
        return {"ok": False, "error_code": "PUBLISHER_PUBKEY_MISSING", "error": "publisher_pubkey_missing"}
    pub_file = Path(pub_raw).resolve()
    if not pub_file.exists():
        return {"ok": False, "error_code": "PUBLISHER_PUBKEY_MISSING", "error": "publisher_pubkey_missing"}
    try:
        pk = load_pubkey(str(pub_file))
    except Exception:
        return {"ok": False, "error_code": "PUBLISHER_PUBKEY_INVALID", "error": "publisher_pubkey_invalid"}
    fp = pub_fingerprint(pk)
    claimed_fp = str(sig.get("pub_fingerprint") or "").strip().lower()
    if claimed_fp and claimed_fp != fp:
        return {
            "ok": False,
            "error_code": "PUBLISHER_PUBKEY_FINGERPRINT_MISMATCH",
            "error": "publisher_pubkey_fingerprint_mismatch",
            "pub_fingerprint": fp,
        }
    try:
        sig_raw = base64.b64decode(str(sig.get("sig_b64") or "").strip(), validate=True)
    except Exception:
        return {"ok": False, "error_code": "PUBLISHER_SIG_INVALID", "error": "publisher_sig_invalid", "pub_fingerprint": fp}
    if len(sig_raw) != 64:
        return {"ok": False, "error_code": "PUBLISHER_SIG_INVALID", "error": "publisher_sig_invalid", "pub_fingerprint": fp}
    try:
        pk.verify(sig_raw, _message_bytes(tree_hash_hex))
    except Exception:
        return {"ok": False, "error_code": "PUBLISHER_SIG_INVALID", "error": "publisher_sig_invalid", "pub_fingerprint": fp}
    return {
        "ok": True,
        "error_code": "",
        "error": "",
        "pub_fingerprint": fp,
        "key_id": str(sig.get("key_id") or "publisher-default"),
        "alg": "ed25519",
        "msg": _DOMAIN,
    }


def verify_tree_hash_sigs(tree_hash_hex: str, publisher_sigs: List[Dict[str, Any]], pub_paths: Dict[str, str]) -> Dict[str, Any]:
    rows = [dict(x) for x in list(publisher_sigs or []) if isinstance(x, dict)]
    path_map = dict(pub_paths or {})
    out_rows: List[Dict[str, Any]] = []
    seen: Dict[str, bool] = {}
    valid_distinct = 0
    for sig in rows:
        key_id = str(sig.get("key_id") or "publisher-default")
        pub_path = str(path_map.get(key_id) or "").strip()
        rep = verify_tree_hash_sig(tree_hash_hex, sig, pub_path)
        row = {"key_id": key_id, "ok": bool(rep.get("ok")), "error_code": str(rep.get("error_code") or ""), "error": str(rep.get("error") or "")}
        if bool(rep.get("ok")) and (not seen.get(key_id)):
            seen[key_id] = True
            valid_distinct += 1
        out_rows.append(row)
    return {"ok": True, "rows": out_rows, "valid_distinct": valid_distinct, "total": len(rows)}


__all__ = [
    "is_available",
    "load_privkey",
    "load_pubkey",
    "pub_fingerprint",
    "pub_fingerprint_from_path",
    "sign_tree_hash",
    "verify_tree_hash_sig",
    "verify_tree_hash_sigs",
]
