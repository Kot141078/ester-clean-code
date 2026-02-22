# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

    _ED25519_OK = True
except Exception:  # pragma: no cover
    serialization = None  # type: ignore
    Ed25519PrivateKey = None  # type: ignore
    Ed25519PublicKey = None  # type: ignore
    _ED25519_OK = False


def _persist_dir() -> Path:
    root = str(os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _default_priv_path() -> Path:
    raw = str(os.getenv("ESTER_EVIDENCE_SIGNING_PRIVKEY_PATH") or "").strip()
    if raw:
        p = Path(raw)
        return p.resolve() if p.is_absolute() else (_persist_dir() / p).resolve()
    return (_persist_dir() / "keys" / "evidence_ed25519_private.pem").resolve()


def _default_pub_path() -> Path:
    raw = str(os.getenv("ESTER_EVIDENCE_SIGNING_PUBKEY_PATH") or "").strip()
    if raw:
        p = Path(raw)
        return p.resolve() if p.is_absolute() else (_persist_dir() / p).resolve()
    return (_persist_dir() / "keys" / "evidence_ed25519_public.pem").resolve()


def _canonical_payload(packet: Dict[str, Any]) -> bytes:
    src = dict(packet or {})
    src.pop("sig", None)
    return json.dumps(src, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def payload_hash(packet: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_payload(packet)).hexdigest()


def is_available() -> bool:
    return bool(_ED25519_OK)


def ensure_keypair(*, priv_path: str = "", pub_path: str = "", overwrite: bool = False) -> Dict[str, Any]:
    if not _ED25519_OK:
        return {"ok": False, "error_code": "ED25519_UNAVAILABLE", "error": "ed25519_unavailable"}
    priv = Path(priv_path).resolve() if str(priv_path).strip() else _default_priv_path()
    pub = Path(pub_path).resolve() if str(pub_path).strip() else _default_pub_path()
    priv.parent.mkdir(parents=True, exist_ok=True)
    pub.parent.mkdir(parents=True, exist_ok=True)

    if priv.exists() and pub.exists() and (not overwrite):
        pub_bytes = pub.read_bytes()
        return {
            "ok": True,
            "private_key_path": str(priv),
            "public_key_path": str(pub),
            "public_key_fingerprint": hashlib.sha256(pub_bytes).hexdigest(),
            "created": False,
        }

    sk = Ed25519PrivateKey.generate()
    pk = sk.public_key()
    priv_bytes = sk.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = pk.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv.write_bytes(priv_bytes)
    pub.write_bytes(pub_bytes)
    return {
        "ok": True,
        "private_key_path": str(priv),
        "public_key_path": str(pub),
        "public_key_fingerprint": hashlib.sha256(pub_bytes).hexdigest(),
        "created": True,
    }


def _load_private_key(path: Path) -> Any:
    blob = path.read_bytes()
    return serialization.load_pem_private_key(blob, password=None)


def _load_public_key(path: Path) -> Any:
    blob = path.read_bytes()
    return serialization.load_pem_public_key(blob)


def sign_packet(packet: Dict[str, Any], *, key_id: str = "default", priv_path: str = "", pub_path: str = "") -> Dict[str, Any]:
    if not _ED25519_OK:
        return {"ok": False, "error_code": "ED25519_UNAVAILABLE", "error": "ed25519_unavailable"}
    ensure = ensure_keypair(priv_path=priv_path, pub_path=pub_path, overwrite=False)
    if not bool(ensure.get("ok")):
        return ensure
    priv = Path(str(ensure.get("private_key_path") or "")).resolve()
    pub = Path(str(ensure.get("public_key_path") or "")).resolve()
    sk = _load_private_key(priv)
    pk = _load_public_key(pub)
    if not isinstance(sk, Ed25519PrivateKey):
        return {"ok": False, "error_code": "EVIDENCE_PRIVKEY_INVALID", "error": "evidence_privkey_invalid"}
    if not isinstance(pk, Ed25519PublicKey):
        return {"ok": False, "error_code": "EVIDENCE_PUBKEY_INVALID", "error": "evidence_pubkey_invalid"}

    out = dict(packet or {})
    p_hash = payload_hash(out)
    sig = sk.sign(_canonical_payload(out))
    raw_pub = pk.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    out["sig"] = {
        "alg": "ed25519",
        "key_id": str(key_id or "default"),
        "pub_b64": base64.b64encode(raw_pub).decode("ascii"),
        "sig_b64": base64.b64encode(sig).decode("ascii"),
        "payload_hash": p_hash,
    }
    return {
        "ok": True,
        "packet": out,
        "payload_hash": p_hash,
        "public_key_fingerprint": hashlib.sha256(pub.read_bytes()).hexdigest(),
        "public_key_path": str(pub),
        "private_key_path": str(priv),
    }


def verify_packet(packet: Dict[str, Any], *, pub_path: str = "") -> Dict[str, Any]:
    if not _ED25519_OK:
        return {"ok": False, "error_code": "ED25519_UNAVAILABLE", "error": "ed25519_unavailable"}
    src = dict(packet or {})
    sig = dict(src.get("sig") or {})
    if not sig:
        return {"ok": False, "error_code": "EVIDENCE_SIG_REQUIRED", "error": "evidence_sig_required"}
    if str(sig.get("alg") or "").strip().lower() != "ed25519":
        return {"ok": False, "error_code": "EVIDENCE_SIG_ALG_INVALID", "error": "evidence_sig_alg_invalid"}

    try:
        sig_raw = base64.b64decode(str(sig.get("sig_b64") or ""), validate=True)
    except Exception:
        return {"ok": False, "error_code": "EVIDENCE_SIG_INVALID", "error": "evidence_sig_invalid"}
    if len(sig_raw) != 64:
        return {"ok": False, "error_code": "EVIDENCE_SIG_INVALID", "error": "evidence_sig_invalid"}

    expected_hash = payload_hash(src)
    claimed_hash = str(sig.get("payload_hash") or "").strip().lower()
    if claimed_hash != expected_hash:
        return {
            "ok": False,
            "error_code": "EVIDENCE_PAYLOAD_HASH_MISMATCH",
            "error": "evidence_payload_hash_mismatch",
            "payload_hash": expected_hash,
        }

    pk = None
    p = Path(pub_path).resolve() if str(pub_path).strip() else _default_pub_path()
    if p.exists():
        try:
            obj = _load_public_key(p)
            if isinstance(obj, Ed25519PublicKey):
                pk = obj
        except Exception:
            return {"ok": False, "error_code": "EVIDENCE_PUBKEY_INVALID", "error": "evidence_pubkey_invalid"}
    if pk is None:
        pub_b64 = str(sig.get("pub_b64") or "").strip()
        if not pub_b64:
            return {"ok": False, "error_code": "EVIDENCE_PUBKEY_INVALID", "error": "evidence_pubkey_invalid"}
        try:
            raw_pub = base64.b64decode(pub_b64, validate=True)
            pk = Ed25519PublicKey.from_public_bytes(raw_pub)
        except Exception:
            return {"ok": False, "error_code": "EVIDENCE_PUBKEY_INVALID", "error": "evidence_pubkey_invalid"}

    try:
        pk.verify(sig_raw, _canonical_payload(src))
    except Exception:
        return {"ok": False, "error_code": "EVIDENCE_SIG_INVALID", "error": "evidence_sig_invalid", "payload_hash": expected_hash}
    return {
        "ok": True,
        "error_code": "",
        "payload_hash": expected_hash,
        "key_id": str(sig.get("key_id") or "default"),
        "alg": "ed25519",
    }


__all__ = [
    "is_available",
    "payload_hash",
    "ensure_keypair",
    "sign_packet",
    "verify_packet",
]

