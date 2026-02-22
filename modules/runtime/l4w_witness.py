# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

    _ED25519_OK = True
except Exception:  # pragma: no cover
    serialization = None  # type: ignore
    Ed25519PrivateKey = None  # type: ignore
    Ed25519PublicKey = None  # type: ignore
    _ED25519_OK = False

try:
    from modules.runtime import evidence_signing
except Exception:  # pragma: no cover
    evidence_signing = None  # type: ignore

try:
    from modules.runtime import publisher_transparency_log
except Exception:  # pragma: no cover
    publisher_transparency_log = None  # type: ignore

_CHAIN_LOCK = threading.RLock()
_BOOL_TRUE = {"1", "true", "yes", "on", "y"}
_AUDIT_LOCK = threading.RLock()
_SUPPORTED_PROFILES = ("BASE", "HRO", "FULL")
_LAST_AUDIT: Dict[str, Any] = {
    "ts": 0,
    "profile": "",
    "ok": False,
    "error": "not_run",
}


def _env_bool(name: str, default: bool) -> bool:
    raw_default = "1" if bool(default) else "0"
    raw = str(os.getenv(name, raw_default) or raw_default).strip().lower()
    return raw in _BOOL_TRUE


def _env_int(name: str, default: int, min_value: int = 1) -> int:
    try:
        value = int(os.getenv(name, str(default)) or default)
    except Exception:
        value = int(default)
    return max(int(min_value), int(value))


def default_profile() -> str:
    raw = str(os.getenv("ESTER_L4W_PROFILE_DEFAULT", "HRO") or "HRO").strip().upper()
    if raw in _SUPPORTED_PROFILES:
        return raw
    return "HRO"


def normalize_profile(profile: str) -> str:
    raw = str(profile or "").strip().upper()
    if not raw:
        return default_profile()
    if raw in _SUPPORTED_PROFILES:
        return raw
    return ""


def supported_profiles() -> List[str]:
    return list(_SUPPORTED_PROFILES)


def _persist_dir() -> Path:
    root = str(os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _l4w_root() -> Path:
    p = (_persist_dir() / "l4w").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _envelopes_root() -> Path:
    p = (_l4w_root() / "envelopes").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _quarantine_envelopes_root() -> Path:
    p = (_envelopes_root() / "quarantine_clear").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _disclosures_root() -> Path:
    p = (_l4w_root() / "disclosures").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _chain_dir() -> Path:
    p = (_l4w_root() / "chains" / "quarantine_clear").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _default_priv_path() -> Path:
    raw = str(os.getenv("ESTER_L4W_SIGNING_PRIVKEY_PATH") or "").strip()
    if not raw:
        raw = str(os.getenv("ESTER_EVIDENCE_SIGNING_PRIVKEY_PATH") or "").strip()
    if raw:
        p = Path(raw)
        return p.resolve() if p.is_absolute() else (_persist_dir() / p).resolve()
    return (_persist_dir() / "keys" / "evidence_ed25519_private.pem").resolve()


def _default_pub_path() -> Path:
    raw = str(os.getenv("ESTER_L4W_SIGNING_PUBKEY_PATH") or "").strip()
    if not raw:
        raw = str(os.getenv("ESTER_EVIDENCE_SIGNING_PUBKEY_PATH") or "").strip()
    if raw:
        p = Path(raw)
        return p.resolve() if p.is_absolute() else (_persist_dir() / p).resolve()
    return (_persist_dir() / "keys" / "evidence_ed25519_public.pem").resolve()


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
        try:
            raw_pub = serialization.load_pem_public_key(pub.read_bytes()).public_bytes(  # type: ignore[union-attr]
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        except Exception:
            raw_pub = pub.read_bytes()
        return {
            "ok": True,
            "private_key_path": str(priv),
            "public_key_path": str(pub),
            "public_key_fingerprint": hashlib.sha256(raw_pub).hexdigest(),
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
    raw_pub = pk.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    priv.write_bytes(priv_bytes)
    pub.write_bytes(pub_bytes)
    return {
        "ok": True,
        "private_key_path": str(priv),
        "public_key_path": str(pub),
        "public_key_fingerprint": hashlib.sha256(raw_pub).hexdigest(),
        "created": True,
    }


def _load_private_key(path: Path) -> Any:
    blob = path.read_bytes()
    return serialization.load_pem_private_key(blob, password=None)


def _load_public_key(path: Path) -> Any:
    blob = path.read_bytes()
    return serialization.load_pem_public_key(blob)


def _ensure_canonical_subset(value: Any, *, where: str = "$") -> None:
    if value is None:
        return
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, str):
        return
    if isinstance(value, float):
        raise ValueError(f"float_forbidden:{where}")
    if isinstance(value, list):
        for idx, item in enumerate(value):
            _ensure_canonical_subset(item, where=f"{where}[{idx}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"dict_key_not_str:{where}")
            _ensure_canonical_subset(item, where=f"{where}.{key}")
        return
    raise ValueError(f"type_forbidden:{where}:{type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    _ensure_canonical_subset(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _sha256_hex(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(131072)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _is_sha256_hex(value: str) -> bool:
    s = str(value or "").strip().lower()
    if len(s) != 64:
        return False
    for ch in s:
        if ch not in "0123456789abcdef":
            return False
    return True


def _normalize_rel_path(raw: str) -> str:
    s = str(raw or "").strip().replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    return s


def _slot() -> str:
    raw = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if raw == "B" else "A"


def _roster_root_pubkey_path() -> Path:
    raw = str(os.getenv("ESTER_ROSTER_ROOT_PUBKEY_PATH") or "").strip()
    if raw:
        p = Path(raw)
        return p.resolve() if p.is_absolute() else (_persist_dir() / p).resolve()
    return (_persist_dir() / "keys" / "roster_root_public.pem").resolve()


def _resolve_roster_anchor_from_log() -> Dict[str, Any]:
    if publisher_transparency_log is None:
        return {"ok": False, "error_code": "ROSTER_LOG_INVALID", "error": "publisher_transparency_log_unavailable"}
    persist = _persist_dir()
    keys_dir = (persist / "keys").resolve()
    log_path = (keys_dir / "publisher_roster_log.jsonl").resolve()
    head_path = (keys_dir / "publisher_roster_log_head.json").resolve()
    if (not _path_within(log_path, persist)) or (not _path_within(head_path, persist)):
        return {"ok": False, "error_code": "ROSTER_LOG_REQUIRED", "error": "roster_log_path_forbidden"}
    if (not log_path.exists()) or (not log_path.is_file()):
        return {"ok": False, "error_code": "ROSTER_LOG_REQUIRED", "error": "roster_log_missing"}

    root_pub = _roster_root_pubkey_path()
    if (not root_pub.exists()) or (not root_pub.is_file()):
        return {"ok": False, "error_code": "ROSTER_LOG_REQUIRED", "error": "roster_root_pubkey_missing"}
    if not _path_within(root_pub, persist):
        return {"ok": False, "error_code": "ROSTER_LOG_REQUIRED", "error": "roster_root_pubkey_path_forbidden"}

    verified = publisher_transparency_log.verify_log_chain(
        str(log_path),
        str(root_pub),
        require_strict_append=True,
        require_publications=False,
    )
    if not bool(verified.get("ok")):
        return {
            "ok": False,
            "error_code": "ROSTER_LOG_INVALID",
            "error": str(verified.get("error") or "roster_log_invalid"),
        }

    entries = [dict(x) for x in list(verified.get("entries") or []) if isinstance(x, dict)]
    if not entries:
        return {"ok": False, "error_code": "ROSTER_LOG_REQUIRED", "error": "roster_log_empty"}

    head_hash = ""
    try:
        head_obj = json.loads(head_path.read_text(encoding="utf-8")) if head_path.exists() and head_path.is_file() else {}
        if isinstance(head_obj, dict):
            head_hash = str(head_obj.get("last_entry_hash") or "").strip().lower()
    except Exception:
        head_hash = ""
    if not _is_sha256_hex(head_hash):
        head_hash = str(verified.get("last_entry_hash") or "").strip().lower()
    if not _is_sha256_hex(head_hash):
        return {"ok": False, "error_code": "ROSTER_LOG_INVALID", "error": "roster_log_head_invalid"}

    anchor_entry: Dict[str, Any] = {}
    for row in entries:
        if str(row.get("entry_hash") or "").strip().lower() == head_hash:
            anchor_entry = dict(row)
            break
    if not anchor_entry:
        return {"ok": False, "error_code": "ROSTER_LOG_ENTRY_NOT_FOUND", "error": "roster_log_head_not_found"}

    body_sha = str(anchor_entry.get("body_sha256") or "").strip().lower()
    if not _is_sha256_hex(body_sha):
        return {"ok": False, "error_code": "ROSTER_LOG_INVALID", "error": "roster_log_body_sha_invalid"}

    anchor = {
        "schema": "ester.publisher.roster_anchor_ref.v1",
        "entry_hash": str(head_hash),
        "body_sha256": str(body_sha),
        "roster_id": str(anchor_entry.get("roster_id") or ""),
    }
    return {"ok": True, "anchor": anchor, "entry": anchor_entry}


def _envelope_hash_input(envelope_dict: Dict[str, Any]) -> Dict[str, Any]:
    src = dict(envelope_dict or {})
    src.pop("sig", None)
    ch = dict(src.get("chain") or {})
    ch.pop("envelope_hash", None)
    src["chain"] = ch
    return src


def _envelope_sig_input(envelope_dict: Dict[str, Any]) -> Dict[str, Any]:
    src = dict(envelope_dict or {})
    src.pop("sig", None)
    return src


def compute_envelope_hash(envelope_dict: Dict[str, Any]) -> str:
    return _sha256_hex(canonical_bytes(_envelope_hash_input(envelope_dict)))


def _commit_hash(salt_b64: str, value: Any) -> str:
    salt_raw = base64.b64decode(str(salt_b64 or "").strip(), validate=True)
    return _sha256_hex(salt_raw + canonical_bytes(value))


def _mk_commit(value: Any) -> Dict[str, str]:
    salt = base64.b64encode(os.urandom(16)).decode("ascii")
    return {"salt_b64": salt, "hash": _commit_hash(salt, value)}


def _read_commit_hash(claim: Dict[str, Any], key: str, *, required: bool) -> Dict[str, Any]:
    node = dict(claim.get(key) or {})
    if (not node) and (not required):
        return {"ok": True, "hash": ""}
    if not node:
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": f"{key}_required"}
    alg = str(node.get("alg") or "").strip().lower()
    hval = str(node.get("hash") or "").strip().lower()
    if alg != "sha256" or (not _is_sha256_hex(hval)):
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": f"{key}_invalid"}
    return {"ok": True, "hash": hval}


def _validate_envelope_shape(envelope_dict: Dict[str, Any], *, require_sig: bool) -> Dict[str, Any]:
    src = dict(envelope_dict or {})
    if str(src.get("schema") or "") != "ester.l4w.envelope.v1":
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "l4w_schema_invalid"}
    if str(src.get("kind") or "") != "quarantine.clear":
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "l4w_kind_invalid"}

    subj = dict(src.get("subject") or {})
    if (not str(subj.get("agent_id") or "").strip()) or (not str(subj.get("quarantine_event_id") or "").strip()):
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "l4w_subject_invalid"}

    eref = dict(src.get("evidence_ref") or {})
    if (
        (not str(eref.get("path") or "").strip())
        or (not _is_sha256_hex(str(eref.get("sha256") or "")))
        or (not str(eref.get("evidence_schema") or "").strip())
    ):
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "l4w_evidence_ref_invalid"}

    claim = dict(src.get("claim") or {})
    if str(claim.get("decision") or "") != "CLEAR_QUARANTINE":
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "l4w_claim_decision_invalid"}
    rc = _read_commit_hash(claim, "reviewer_commit", required=True)
    if not bool(rc.get("ok")):
        return rc
    sc = _read_commit_hash(claim, "summary_commit", required=True)
    if not bool(sc.get("ok")):
        return sc
    nc = _read_commit_hash(claim, "notes_commit", required=False)
    if not bool(nc.get("ok")):
        return nc

    roster_anchor = dict(src.get("roster_anchor") or {})
    if roster_anchor:
        if str(roster_anchor.get("schema") or "") != "ester.publisher.roster_anchor_ref.v1":
            return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "l4w_roster_anchor_schema_invalid"}
        entry_hash = str(roster_anchor.get("entry_hash") or "").strip().lower()
        body_sha = str(roster_anchor.get("body_sha256") or "").strip().lower()
        if (not _is_sha256_hex(entry_hash)) or (not _is_sha256_hex(body_sha)):
            return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "l4w_roster_anchor_invalid"}
        if not isinstance(roster_anchor.get("roster_id"), str):
            return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "l4w_roster_anchor_invalid"}

    chain = dict(src.get("chain") or {})
    if not isinstance(chain.get("prev_hash"), str):
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "l4w_prev_hash_invalid"}
    c_hash = str(chain.get("envelope_hash") or "").strip().lower()
    if c_hash and (not _is_sha256_hex(c_hash)):
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "l4w_envelope_hash_invalid"}

    if require_sig:
        sig = dict(src.get("sig") or {})
        if not sig:
            return {"ok": False, "error_code": "L4W_SIG_INVALID", "error": "l4w_sig_required"}
        if str(sig.get("alg") or "").strip().lower() != "ed25519":
            return {"ok": False, "error_code": "L4W_SIG_INVALID", "error": "l4w_sig_alg_invalid"}
        try:
            sig_raw = base64.b64decode(str(sig.get("sig_b64") or "").strip(), validate=True)
        except Exception:
            return {"ok": False, "error_code": "L4W_SIG_INVALID", "error": "l4w_sig_invalid"}
        if len(sig_raw) != 64:
            return {"ok": False, "error_code": "L4W_SIG_INVALID", "error": "l4w_sig_invalid"}

    try:
        canonical_bytes(_envelope_hash_input(src))
        canonical_bytes(_envelope_sig_input(src))
    except Exception:
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "l4w_canonicalization_invalid"}
    return {"ok": True}


def build_envelope_for_clear(
    agent_id: str,
    quarantine_event_id: str,
    *,
    reviewer: str,
    summary: str,
    notes: str | None,
    evidence_path: str,
    evidence_sha256: str,
    evidence_schema: str,
    evidence_sig_ok: bool,
    evidence_payload_hash: str,
    prev_hash: str = "",
    on_time: bool = False,
    late: bool = False,
    envelope_id: str = "",
    ts: int = 0,
    roster_anchor: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    eid = str(quarantine_event_id or "").strip()
    now_ts = int(ts or time.time())
    ent_id = str(envelope_id or "").strip()
    if not ent_id:
        seed = f"{aid}|{eid}|{now_ts}|{os.urandom(8).hex()}".encode("utf-8")
        ent_id = "l4w_" + hashlib.sha256(seed).hexdigest()[:16]

    reviewer_val = str(reviewer or "")
    summary_val = str(summary or "")
    notes_val = None if notes is None else str(notes)
    reviewer_commit = _mk_commit(reviewer_val)
    summary_commit = _mk_commit(summary_val)
    notes_commit = _mk_commit(notes_val) if notes_val is not None else None

    anchor_obj: Dict[str, Any] = {}
    if isinstance(roster_anchor, dict) and roster_anchor:
        raw_anchor = dict(roster_anchor)
        anchor_obj = {
            "schema": "ester.publisher.roster_anchor_ref.v1",
            "entry_hash": str(raw_anchor.get("entry_hash") or "").strip().lower(),
            "body_sha256": str(raw_anchor.get("body_sha256") or "").strip().lower(),
            "roster_id": str(raw_anchor.get("roster_id") or ""),
        }
    else:
        slot = _slot()
        keys_dir = (_persist_dir() / "keys").resolve()
        has_roster_log = (keys_dir / "publisher_roster_log.jsonl").exists() or (keys_dir / "publisher_roster_log_head.json").exists()
        anchor_enable = _env_bool("ESTER_L4W_ROSTER_ANCHOR_ENABLE", True)
        anchor_required = _env_bool("ESTER_L4W_ROSTER_ANCHOR_REQUIRED", False) or (slot == "B" and has_roster_log)
        anchor_rep: Dict[str, Any] = {"ok": False, "error_code": "ROSTER_LOG_REQUIRED", "error": "roster_anchor_missing"}
        if anchor_enable or anchor_required:
            anchor_rep = _resolve_roster_anchor_from_log()
            if bool(anchor_rep.get("ok")):
                anchor_obj = dict(anchor_rep.get("anchor") or {})
        if anchor_required and (not anchor_obj):
            return {
                "ok": False,
                "error_code": str(anchor_rep.get("error_code") or "ROSTER_LOG_REQUIRED"),
                "error": str(anchor_rep.get("error") or "roster_anchor_required"),
            }
    if anchor_obj:
        if str(anchor_obj.get("schema") or "") != "ester.publisher.roster_anchor_ref.v1":
            return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "l4w_roster_anchor_schema_invalid"}
        if (not _is_sha256_hex(str(anchor_obj.get("entry_hash") or "").strip().lower())) or (
            not _is_sha256_hex(str(anchor_obj.get("body_sha256") or "").strip().lower())
        ):
            return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "l4w_roster_anchor_invalid"}

    claim: Dict[str, Any] = {
        "decision": "CLEAR_QUARANTINE",
        "on_time": bool(on_time),
        "late": bool(late),
        "reviewer_commit": {"alg": "sha256", "hash": str(reviewer_commit.get("hash") or "")},
        "summary_commit": {"alg": "sha256", "hash": str(summary_commit.get("hash") or "")},
    }
    if notes_commit is not None:
        claim["notes_commit"] = {"alg": "sha256", "hash": str(notes_commit.get("hash") or "")}

    envelope: Dict[str, Any] = {
        "schema": "ester.l4w.envelope.v1",
        "envelope_id": ent_id,
        "ts": int(now_ts),
        "kind": "quarantine.clear",
        "subject": {
            "agent_id": aid,
            "quarantine_event_id": eid,
        },
        "evidence_ref": {
            "path": _normalize_rel_path(str(evidence_path or "")),
            "sha256": str(evidence_sha256 or "").strip().lower(),
            "evidence_schema": str(evidence_schema or "ester.evidence.v1"),
            "evidence_sig_ok": bool(evidence_sig_ok),
            "evidence_payload_hash": str(evidence_payload_hash or ""),
        },
        "claim": claim,
        "chain": {
            "prev_hash": str(prev_hash or "").strip().lower(),
            "envelope_hash": "",
        },
    }
    if anchor_obj:
        envelope["roster_anchor"] = dict(anchor_obj)
    env_hash = compute_envelope_hash(envelope)
    envelope["chain"] = {
        "prev_hash": str(prev_hash or "").strip().lower(),
        "envelope_hash": env_hash,
    }

    reveals: List[Dict[str, Any]] = [
        {"path": "claim.reviewer", "salt_b64": str(reviewer_commit.get("salt_b64") or ""), "value": reviewer_val},
        {"path": "claim.summary", "salt_b64": str(summary_commit.get("salt_b64") or ""), "value": summary_val},
    ]
    if notes_commit is not None:
        reveals.append({"path": "claim.notes", "salt_b64": str(notes_commit.get("salt_b64") or ""), "value": notes_val})

    disclosure_template = {
        "schema": "ester.l4w.disclosure.v1",
        "ts": int(now_ts),
        "envelope_hash": env_hash,
        "reveals": reveals,
    }
    return {
        "ok": True,
        "envelope": envelope,
        "envelope_hash": env_hash,
        "prev_hash": str(prev_hash or "").strip().lower(),
        "disclosure_template": disclosure_template,
    }


def sign_envelope(envelope_dict: Dict[str, Any], *, key_id: str = "default", priv_path: str = "", pub_path: str = "") -> Dict[str, Any]:
    if not _ED25519_OK:
        return {"ok": False, "error_code": "ED25519_UNAVAILABLE", "error": "ed25519_unavailable"}
    src = dict(envelope_dict or {})
    shape = _validate_envelope_shape(src, require_sig=False)
    if not bool(shape.get("ok")):
        return shape

    env_hash = compute_envelope_hash(src)
    chain = dict(src.get("chain") or {})
    chain["envelope_hash"] = env_hash
    src["chain"] = chain
    src.pop("sig", None)

    ensure = ensure_keypair(priv_path=priv_path, pub_path=pub_path, overwrite=False)
    if not bool(ensure.get("ok")):
        return ensure
    priv = Path(str(ensure.get("private_key_path") or "")).resolve()
    pub = Path(str(ensure.get("public_key_path") or "")).resolve()
    try:
        sk = _load_private_key(priv)
        pk = _load_public_key(pub)
    except Exception:
        return {"ok": False, "error_code": "L4W_SIG_INVALID", "error": "l4w_key_load_failed"}
    if not isinstance(sk, Ed25519PrivateKey) or not isinstance(pk, Ed25519PublicKey):
        return {"ok": False, "error_code": "L4W_SIG_INVALID", "error": "l4w_key_invalid"}

    payload = _envelope_sig_input(src)
    sig_raw = sk.sign(canonical_bytes(payload))
    raw_pub = pk.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    pub_fp = hashlib.sha256(raw_pub).hexdigest()
    src["sig"] = {
        "alg": "ed25519",
        "key_id": str(key_id or "default"),
        "pub_fingerprint": pub_fp,
        "sig_b64": base64.b64encode(sig_raw).decode("ascii"),
    }
    return {
        "ok": True,
        "envelope": src,
        "envelope_hash": env_hash,
        "pub_fingerprint": pub_fp,
        "key_id": str(key_id or "default"),
    }


def verify_envelope(envelope_dict: Dict[str, Any], *, pub_path: str = "") -> Dict[str, Any]:
    if not _ED25519_OK:
        return {"ok": False, "error_code": "ED25519_UNAVAILABLE", "error": "ed25519_unavailable"}
    src = dict(envelope_dict or {})
    shape = _validate_envelope_shape(src, require_sig=True)
    if not bool(shape.get("ok")):
        return shape

    env_hash = compute_envelope_hash(src)
    claimed_hash = str((dict(src.get("chain") or {})).get("envelope_hash") or "").strip().lower()
    if claimed_hash != env_hash:
        return {
            "ok": False,
            "error_code": "L4W_HASH_MISMATCH",
            "error": "l4w_hash_mismatch",
            "envelope_hash": env_hash,
            "claimed_hash": claimed_hash,
        }

    sig = dict(src.get("sig") or {})
    try:
        sig_raw = base64.b64decode(str(sig.get("sig_b64") or ""), validate=True)
    except Exception:
        return {"ok": False, "error_code": "L4W_SIG_INVALID", "error": "l4w_sig_invalid", "envelope_hash": env_hash}

    p = Path(pub_path).resolve() if str(pub_path).strip() else _default_pub_path()
    if not p.exists():
        return {"ok": False, "error_code": "L4W_SIG_INVALID", "error": "l4w_pubkey_missing", "envelope_hash": env_hash}
    try:
        pk = _load_public_key(p)
    except Exception:
        return {"ok": False, "error_code": "L4W_SIG_INVALID", "error": "l4w_pubkey_invalid", "envelope_hash": env_hash}
    if not isinstance(pk, Ed25519PublicKey):
        return {"ok": False, "error_code": "L4W_SIG_INVALID", "error": "l4w_pubkey_invalid", "envelope_hash": env_hash}

    payload = _envelope_sig_input(src)
    try:
        pk.verify(sig_raw, canonical_bytes(payload))
    except Exception:
        return {"ok": False, "error_code": "L4W_SIG_INVALID", "error": "l4w_sig_invalid", "envelope_hash": env_hash}

    raw_pub = pk.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    pub_fp = hashlib.sha256(raw_pub).hexdigest()
    claimed_fp = str(sig.get("pub_fingerprint") or "").strip().lower()
    if claimed_fp and claimed_fp != pub_fp:
        return {
            "ok": False,
            "error_code": "L4W_SIG_INVALID",
            "error": "l4w_pub_fingerprint_mismatch",
            "envelope_hash": env_hash,
            "pub_fingerprint": pub_fp,
        }

    return {
        "ok": True,
        "error_code": "",
        "envelope_hash": env_hash,
        "pub_fingerprint": pub_fp,
        "key_id": str(sig.get("key_id") or "default"),
        "alg": "ed25519",
    }


def resolve_envelope_path(envelope_path: str) -> Dict[str, Any]:
    raw = str(envelope_path or "").strip()
    if not raw:
        return {"ok": False, "error_code": "L4W_REQUIRED", "error": "l4w_required"}
    root = _envelopes_root()
    p = Path(raw)
    resolved = p.resolve() if p.is_absolute() else (root / p).resolve()
    if not _path_within(resolved, root):
        return {
            "ok": False,
            "error_code": "L4W_PATH_FORBIDDEN",
            "error": "l4w_path_forbidden",
            "l4w_root": str(root),
            "envelope_path": str(resolved),
        }
    return {
        "ok": True,
        "l4w_root": str(root),
        "envelope_path": str(resolved),
        "envelope_rel_path": str(resolved.relative_to(root)).replace("\\", "/"),
    }


def envelope_storage_path(agent_id: str, envelope_id: str) -> Path:
    aid = str(agent_id or "").strip().replace("\\", "_").replace("/", "_").replace(":", "_")
    ent = str(envelope_id or "").strip().replace("\\", "_").replace("/", "_").replace(":", "_")
    return (_quarantine_envelopes_root() / aid / f"{ent}.json").resolve()


def disclosure_storage_path(envelope_hash: str) -> Path:
    return (_disclosures_root() / f"{str(envelope_hash or '').strip().lower()}.json").resolve()


def write_envelope(agent_id: str, envelope_dict: Dict[str, Any]) -> Dict[str, Any]:
    src = dict(envelope_dict or {})
    eid = str(src.get("envelope_id") or "").strip()
    if not eid:
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "envelope_id_required"}
    p = envelope_storage_path(agent_id, eid)
    p.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(src, ensure_ascii=True, indent=2).encode("utf-8")
    tmp = p.with_suffix(".tmp")
    try:
        tmp.write_bytes(blob)
        tmp.replace(p)
    except Exception:
        p.write_bytes(blob)
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
    sha = sha256_file(p)
    return {
        "ok": True,
        "envelope_path": str(p),
        "envelope_rel_path": str(p.relative_to(_envelopes_root())).replace("\\", "/"),
        "envelope_sha256": sha,
    }


def write_disclosure(disclosure_dict: Dict[str, Any]) -> Dict[str, Any]:
    src = dict(disclosure_dict or {})
    ehash = str(src.get("envelope_hash") or "").strip().lower()
    if not _is_sha256_hex(ehash):
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "envelope_hash_invalid"}
    p = disclosure_storage_path(ehash)
    p.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(src, ensure_ascii=True, indent=2).encode("utf-8")
    tmp = p.with_suffix(".tmp")
    try:
        tmp.write_bytes(blob)
        tmp.replace(p)
    except Exception:
        p.write_bytes(blob)
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
    return {"ok": True, "disclosure_path": str(p)}


def _safe_agent_file(agent_id: str) -> str:
    raw = str(agent_id or "").strip()
    if not raw:
        raw = "unknown"
    out = "".join(ch if (ch.isalnum() or ch in "-_.") else "_" for ch in raw)
    if not out:
        out = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return out


def chain_path(agent_id: str) -> Path:
    return (_chain_dir() / f"{_safe_agent_file(agent_id)}.jsonl").resolve()


def _read_chain_records(agent_id: str) -> List[Dict[str, Any]]:
    p = chain_path(agent_id)
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                row = json.loads(s)
            except Exception:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def chain_head(agent_id: str) -> Dict[str, Any]:
    rows = _read_chain_records(agent_id)
    if not rows:
        return {"ok": True, "has_head": False, "envelope_hash": "", "prev_hash": "", "ts": 0}
    last = dict(rows[-1] or {})
    return {
        "ok": True,
        "has_head": True,
        "envelope_hash": str(last.get("envelope_hash") or "").strip().lower(),
        "prev_hash": str(last.get("prev_hash") or "").strip().lower(),
        "ts": int(last.get("ts") or 0),
        "record": last,
    }


def verify_chain_prev_hash(agent_id: str, prev_hash: str) -> Dict[str, Any]:
    head = chain_head(agent_id)
    if not bool(head.get("ok")):
        return {"ok": False, "error_code": "L4W_CHAIN_BROKEN", "error": "l4w_chain_head_error"}
    has_head = bool(head.get("has_head"))
    prev = str(prev_hash or "").strip().lower()
    if not has_head:
        if prev != "":
            return {
                "ok": False,
                "error_code": "L4W_CHAIN_BROKEN",
                "error": "l4w_chain_genesis_prev_hash_required_empty",
                "expected_prev_hash": "",
                "provided_prev_hash": prev,
            }
        return {"ok": True, "expected_prev_hash": "", "provided_prev_hash": prev}

    expected = str(head.get("envelope_hash") or "").strip().lower()
    if prev != expected:
        return {
            "ok": False,
            "error_code": "L4W_CHAIN_BROKEN",
            "error": "l4w_chain_prev_hash_mismatch",
            "expected_prev_hash": expected,
            "provided_prev_hash": prev,
        }
    return {"ok": True, "expected_prev_hash": expected, "provided_prev_hash": prev}


def append_chain_record(
    agent_id: str,
    *,
    quarantine_event_id: str,
    envelope_id: str,
    envelope_hash: str,
    prev_hash: str,
    envelope_path: str,
    envelope_sha256: str,
    ts: int = 0,
) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not aid:
        return {"ok": False, "error_code": "L4W_CHAIN_BROKEN", "error": "agent_id_required"}
    ehash = str(envelope_hash or "").strip().lower()
    p_hash = str(prev_hash or "").strip().lower()
    if not _is_sha256_hex(ehash):
        return {"ok": False, "error_code": "L4W_CHAIN_BROKEN", "error": "envelope_hash_invalid"}
    if p_hash and (not _is_sha256_hex(p_hash)):
        return {"ok": False, "error_code": "L4W_CHAIN_BROKEN", "error": "prev_hash_invalid"}

    now_ts = int(ts or time.time())
    row = {
        "ts": int(now_ts),
        "agent_id": aid,
        "quarantine_event_id": str(quarantine_event_id or ""),
        "envelope_id": str(envelope_id or ""),
        "envelope_hash": ehash,
        "prev_hash": p_hash,
        "envelope_path": str(envelope_path or ""),
        "envelope_sha256": str(envelope_sha256 or "").strip().lower(),
    }
    p = chain_path(aid)
    p.parent.mkdir(parents=True, exist_ok=True)

    with _CHAIN_LOCK:
        chk = verify_chain_prev_hash(aid, p_hash)
        if not bool(chk.get("ok")):
            return chk
        line = json.dumps(row, ensure_ascii=True, separators=(",", ":"))
        with p.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
    return {"ok": True, "record": row, "chain_path": str(p)}


def _verify_disclosure_sig(disclosure_dict: Dict[str, Any], *, pub_path: str = "") -> Dict[str, Any]:
    sig = dict(disclosure_dict.get("sig") or {})
    if not sig:
        return {"ok": True, "sig_present": False}
    if not _ED25519_OK:
        return {"ok": False, "error_code": "ED25519_UNAVAILABLE", "error": "ed25519_unavailable"}
    if str(sig.get("alg") or "").strip().lower() != "ed25519":
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "disclosure_sig_alg_invalid"}
    try:
        sig_raw = base64.b64decode(str(sig.get("sig_b64") or "").strip(), validate=True)
    except Exception:
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "disclosure_sig_invalid"}
    if len(sig_raw) != 64:
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "disclosure_sig_invalid"}

    p = Path(pub_path).resolve() if str(pub_path).strip() else _default_pub_path()
    if not p.exists():
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "disclosure_pubkey_missing"}
    try:
        pk = _load_public_key(p)
    except Exception:
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "disclosure_pubkey_invalid"}
    if not isinstance(pk, Ed25519PublicKey):
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "disclosure_pubkey_invalid"}

    payload = dict(disclosure_dict or {})
    payload.pop("sig", None)
    try:
        pk.verify(sig_raw, canonical_bytes(payload))
    except Exception:
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "disclosure_sig_invalid"}
    return {"ok": True, "sig_present": True}


def build_disclosure(
    envelope_hash: str,
    reveals: List[Dict[str, Any]],
    *,
    ts: int = 0,
    sign: bool = False,
    key_id: str = "default",
    priv_path: str = "",
    pub_path: str = "",
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "schema": "ester.l4w.disclosure.v1",
        "ts": int(ts or time.time()),
        "envelope_hash": str(envelope_hash or "").strip().lower(),
        "reveals": [],
    }
    for row in list(reveals or []):
        if not isinstance(row, dict):
            continue
        out["reveals"].append(
            {
                "path": str(row.get("path") or ""),
                "salt_b64": str(row.get("salt_b64") or ""),
                "value": row.get("value"),
            }
        )
    if not sign:
        return out
    if not _ED25519_OK:
        out["sig_error_code"] = "ED25519_UNAVAILABLE"
        return out

    ensure = ensure_keypair(priv_path=priv_path, pub_path=pub_path, overwrite=False)
    if not bool(ensure.get("ok")):
        out["sig_error_code"] = str(ensure.get("error_code") or "ED25519_UNAVAILABLE")
        return out
    priv = Path(str(ensure.get("private_key_path") or "")).resolve()
    pub = Path(str(ensure.get("public_key_path") or "")).resolve()
    try:
        sk = _load_private_key(priv)
        pk = _load_public_key(pub)
    except Exception:
        out["sig_error_code"] = "L4W_SCHEMA_INVALID"
        return out
    if not isinstance(sk, Ed25519PrivateKey) or not isinstance(pk, Ed25519PublicKey):
        out["sig_error_code"] = "L4W_SCHEMA_INVALID"
        return out

    payload = dict(out)
    payload.pop("sig", None)
    sig_raw = sk.sign(canonical_bytes(payload))
    raw_pub = pk.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    out["sig"] = {
        "alg": "ed25519",
        "key_id": str(key_id or "default"),
        "sig_b64": base64.b64encode(sig_raw).decode("ascii"),
        "pub_fingerprint": hashlib.sha256(raw_pub).hexdigest(),
    }
    return out


def verify_disclosure(envelope_dict: Dict[str, Any], disclosure_dict: Dict[str, Any]) -> Dict[str, Any]:
    env = verify_envelope(envelope_dict)
    if not bool(env.get("ok")):
        return {
            "ok": False,
            "error_code": str(env.get("error_code") or "L4W_SIG_INVALID"),
            "error": str(env.get("error") or "envelope_invalid"),
            "which_paths_ok": {},
        }
    envelope_hash = str(env.get("envelope_hash") or "")
    disclosure = dict(disclosure_dict or {})
    if str(disclosure.get("schema") or "") != "ester.l4w.disclosure.v1":
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "disclosure_schema_invalid", "which_paths_ok": {}}
    if str(disclosure.get("envelope_hash") or "").strip().lower() != envelope_hash:
        return {
            "ok": False,
            "error_code": "L4W_SCHEMA_INVALID",
            "error": "disclosure_envelope_hash_mismatch",
            "which_paths_ok": {},
        }
    reveals = list(disclosure.get("reveals") or [])
    if not reveals:
        return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "disclosure_reveals_required", "which_paths_ok": {}}

    claim = dict((dict(envelope_dict.get("claim") or {})) or {})
    expected_map = {
        "claim.reviewer": str((dict(claim.get("reviewer_commit") or {})).get("hash") or "").strip().lower(),
        "claim.summary": str((dict(claim.get("summary_commit") or {})).get("hash") or "").strip().lower(),
        "claim.notes": str((dict(claim.get("notes_commit") or {})).get("hash") or "").strip().lower(),
    }
    which_paths_ok: Dict[str, bool] = {}
    ok = True
    for row in reveals:
        if not isinstance(row, dict):
            ok = False
            continue
        path = str(row.get("path") or "").strip()
        salt_b64 = str(row.get("salt_b64") or "").strip()
        expected = str(expected_map.get(path) or "").strip().lower()
        if not expected:
            which_paths_ok[path] = False
            ok = False
            continue
        try:
            actual = _commit_hash(salt_b64, row.get("value"))
        except Exception:
            which_paths_ok[path] = False
            ok = False
            continue
        hit = bool(actual == expected)
        which_paths_ok[path] = hit
        if not hit:
            ok = False

    sig_verify = _verify_disclosure_sig(disclosure)
    if not bool(sig_verify.get("ok")):
        return {
            "ok": False,
            "error_code": str(sig_verify.get("error_code") or "L4W_SCHEMA_INVALID"),
            "error": str(sig_verify.get("error") or "disclosure_sig_invalid"),
            "which_paths_ok": which_paths_ok,
        }

    return {
        "ok": bool(ok),
        "error_code": "" if ok else "L4W_SCHEMA_INVALID",
        "which_paths_ok": which_paths_ok,
        "envelope_hash": envelope_hash,
        "sig_present": bool(sig_verify.get("sig_present")),
    }


def _persist_dir_for_audit(persist_dir_override: str = "") -> Path:
    raw = str(persist_dir_override or "").strip()
    if raw:
        return Path(raw).resolve()
    return _persist_dir().resolve()


def _audit_pub_path(persist_dir: Path) -> Path:
    raw = str(os.getenv("ESTER_L4W_SIGNING_PUBKEY_PATH") or "").strip()
    if not raw:
        raw = str(os.getenv("ESTER_EVIDENCE_SIGNING_PUBKEY_PATH") or "").strip()
    if raw:
        p = Path(raw)
        return p.resolve() if p.is_absolute() else (persist_dir / p).resolve()
    return (persist_dir / "keys" / "evidence_ed25519_public.pem").resolve()


def _audit_resolve_in_root(root: Path, raw: str, *, code_prefix: str) -> Dict[str, Any]:
    value = str(raw or "").strip()
    if not value:
        return {"ok": False, "code": f"{code_prefix}_PATH_REQUIRED", "detail": "path_required"}
    p = Path(value)
    resolved = p.resolve() if p.is_absolute() else (root / p).resolve()
    if not _path_within(resolved, root):
        return {"ok": False, "code": f"{code_prefix}_PATH_FORBIDDEN", "detail": str(resolved)}
    rel = str(resolved.relative_to(root)).replace("\\", "/")
    return {"ok": True, "path": str(resolved), "rel_path": rel}


def _audit_add_error(report: Dict[str, Any], code: str, where: str, detail: str) -> None:
    report.setdefault("errors", []).append(
        {
            "code": str(code or "L4W_AUDIT_ERROR"),
            "where": str(where or ""),
            "detail": str(detail or ""),
        }
    )


def _audit_add_warning(report: Dict[str, Any], code: str, where: str, detail: str) -> None:
    report.setdefault("warnings", []).append(
        {
            "code": str(code or "L4W_AUDIT_WARN"),
            "where": str(where or ""),
            "detail": str(detail or ""),
        }
    )


def _audit_public_fingerprint(pub_path: Path) -> Dict[str, Any]:
    if not _ED25519_OK:
        return {"ok": False, "code": "ED25519_UNAVAILABLE", "detail": "ed25519_unavailable"}
    if not pub_path.exists():
        return {"ok": False, "code": "L4W_SIG_INVALID", "detail": "l4w_pubkey_missing"}
    try:
        pk = _load_public_key(pub_path)
    except Exception:
        return {"ok": False, "code": "L4W_SIG_INVALID", "detail": "l4w_pubkey_invalid"}
    if not isinstance(pk, Ed25519PublicKey):
        return {"ok": False, "code": "L4W_SIG_INVALID", "detail": "l4w_pubkey_invalid"}
    raw_pub = pk.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {"ok": True, "fingerprint": hashlib.sha256(raw_pub).hexdigest()}


def _audit_extract_meta_ref(metadata: Dict[str, Any], keys: Tuple[str, ...]) -> str:
    src = dict(metadata or {})
    for key in keys:
        raw = str(src.get(key) or "").strip().lower()
        if raw:
            return raw
    return ""


def _audit_locate_volition_journal(persist_dir: Path) -> Dict[str, Any]:
    override = str(os.getenv("ESTER_VOLITION_JOURNAL_PATH") or "").strip()
    if override:
        p = Path(override)
        resolved = p.resolve() if p.is_absolute() else (persist_dir / p).resolve()
    else:
        resolved = (persist_dir / "volition" / "decisions.jsonl").resolve()
    if not _path_within(resolved, persist_dir):
        return {"ok": False, "code": "VOLITION_JOURNAL_FORBIDDEN", "detail": str(resolved)}
    return {"ok": True, "path": str(resolved)}


def _update_last_audit(profile: str, ok: bool, error: str) -> None:
    with _AUDIT_LOCK:
        _LAST_AUDIT["ts"] = int(time.time())
        _LAST_AUDIT["profile"] = str(profile or "")
        _LAST_AUDIT["ok"] = bool(ok)
        _LAST_AUDIT["error"] = str(error or "")


def get_last_audit() -> Dict[str, Any]:
    with _AUDIT_LOCK:
        return {
            "ts": int(_LAST_AUDIT.get("ts") or 0),
            "profile": str(_LAST_AUDIT.get("profile") or ""),
            "ok": bool(_LAST_AUDIT.get("ok")),
            "error": str(_LAST_AUDIT.get("error") or ""),
        }


def verify_agent_chain(
    agent_id: str,
    *,
    profile: str = "",
    max_records: int = 0,
    check_disclosure: bool = False,
    persist_dir_override: str = "",
) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    prof = normalize_profile(profile)
    if not prof:
        prof = str(profile or "").strip().upper()
    limit = int(max_records) if int(max_records or 0) > 0 else _env_int("ESTER_L4W_AUDIT_MAX_RECORDS", 50, 1)
    require_evidence = _env_bool("ESTER_L4W_AUDIT_REQUIRE_EVIDENCE_FILE", True)
    require_disclosure = bool(check_disclosure) or _env_bool("ESTER_L4W_AUDIT_REQUIRE_DISCLOSURE", False)

    report: Dict[str, Any] = {
        "ok": False,
        "profile": prof,
        "agent_id": aid,
        "checked_records": 0,
        "errors": [],
        "warnings": [],
        "last": {"envelope_hash": "", "prev_hash": "", "ts": 0, "quarantine_event_id": ""},
        "evidence": {"files_checked": 0, "sig_checked": False},
        "disclosure": {"checked": False, "paths_ok": {}},
    }

    def _fail(code: str, where: str, detail: str) -> None:
        _audit_add_error(report, code, where, detail)

    def _warn(code: str, where: str, detail: str) -> None:
        _audit_add_warning(report, code, where, detail)

    if not aid:
        _fail("AGENT_ID_REQUIRED", "input.agent_id", "agent_id_required")
    if prof not in _SUPPORTED_PROFILES:
        _fail("L4W_PROFILE_INVALID", "input.profile", f"unsupported_profile:{prof or profile}")
    if report["errors"]:
        _update_last_audit(prof, False, str(report["errors"][0].get("code") or "L4W_AUDIT_ERROR"))
        return report

    persist = _persist_dir_for_audit(persist_dir_override)
    l4w_root = (persist / "l4w").resolve()
    envelopes_root = (l4w_root / "envelopes").resolve()
    disclosures_root = (l4w_root / "disclosures").resolve()
    evidence_root = (persist / "capability_drift" / "evidence").resolve()
    chain_path_local = (l4w_root / "chains" / "quarantine_clear" / f"{_safe_agent_file(aid)}.jsonl").resolve()
    events_path = (persist / "capability_drift" / "quarantine_events.jsonl").resolve()
    state_path = (persist / "capability_drift" / "quarantine_state.json").resolve()
    pub_path = _audit_pub_path(persist)

    for chk_path, where in (
        (chain_path_local, "chain"),
        (envelopes_root, "envelopes_root"),
        (disclosures_root, "disclosures_root"),
        (evidence_root, "evidence_root"),
    ):
        if not _path_within(chk_path, persist):
            _fail("L4W_PATH_FORBIDDEN", where, str(chk_path))
    if report["errors"]:
        _update_last_audit(prof, False, str(report["errors"][0].get("code") or "L4W_AUDIT_ERROR"))
        return report

    rows: List[Dict[str, Any]] = []
    if chain_path_local.exists():
        try:
            with chain_path_local.open("r", encoding="utf-8", errors="replace") as f:
                for line_no, line in enumerate(f, start=1):
                    s = line.strip()
                    if not s:
                        continue
                    try:
                        obj = json.loads(s)
                    except Exception:
                        _fail("L4W_CHAIN_RECORD_INVALID", f"chain:{line_no}", "json_invalid")
                        continue
                    if isinstance(obj, dict):
                        rows.append(dict(obj))
                    else:
                        _fail("L4W_CHAIN_RECORD_INVALID", f"chain:{line_no}", "row_not_object")
        except Exception as exc:
            _fail("L4W_CHAIN_RECORD_INVALID", "chain", f"read_error:{exc.__class__.__name__}")

    if not rows:
        _warn("L4W_NO_RECORDS", "chain", "no_records")
        report["ok"] = True
        last_err = str(report["warnings"][0].get("code") or "")
        _update_last_audit(prof, True, last_err)
        return report

    cfg_pub_fp = ""
    if not _ED25519_OK:
        _fail("ED25519_UNAVAILABLE", "crypto", "ed25519_unavailable")
    if not _path_within(pub_path, persist):
        _fail("L4W_PATH_FORBIDDEN", "pubkey", str(pub_path))
    if not report["errors"]:
        pub_fp_rep = _audit_public_fingerprint(pub_path)
        cfg_pub_fp = str(pub_fp_rep.get("fingerprint") or "").strip().lower()
        if not bool(pub_fp_rep.get("ok")):
            _fail(str(pub_fp_rep.get("code") or "L4W_SIG_INVALID"), "pubkey", str(pub_fp_rep.get("detail") or ""))
    if report["errors"]:
        _update_last_audit(prof, False, str(report["errors"][0].get("code") or "L4W_AUDIT_ERROR"))
        return report

    seen_hash: Dict[str, int] = {}
    seen_env_id: Dict[str, int] = {}
    prev_ts = -1
    for idx, row in enumerate(rows):
        ts_val = int(row.get("ts") or 0)
        if prev_ts >= 0 and ts_val < prev_ts:
            if prof == "FULL":
                _fail("L4W_TS_NON_MONOTONIC", f"chain[{idx}].ts", f"{ts_val}<{prev_ts}")
            elif prof == "HRO":
                _warn("L4W_TS_NON_MONOTONIC", f"chain[{idx}].ts", f"{ts_val}<{prev_ts}")
        prev_ts = ts_val

        hval = str(row.get("envelope_hash") or "").strip().lower()
        if hval:
            prev_idx = seen_hash.get(hval)
            if prev_idx is not None:
                if prof == "FULL":
                    _fail("L4W_DUPLICATE_ENVELOPE_HASH", f"chain[{idx}]", f"duplicate_of:{prev_idx}")
                elif prof == "HRO":
                    _warn("L4W_DUPLICATE_ENVELOPE_HASH", f"chain[{idx}]", f"duplicate_of:{prev_idx}")
            else:
                seen_hash[hval] = idx

        envelope_id = str(row.get("envelope_id") or "").strip()
        if envelope_id:
            prev_idx = seen_env_id.get(envelope_id)
            if prev_idx is not None:
                if prof == "FULL":
                    _fail("L4W_DUPLICATE_ENVELOPE_ID", f"chain[{idx}]", f"duplicate_of:{prev_idx}")
                elif prof == "HRO":
                    _warn("L4W_DUPLICATE_ENVELOPE_ID", f"chain[{idx}]", f"duplicate_of:{prev_idx}")
            else:
                seen_env_id[envelope_id] = idx

    start = max(0, len(rows) - limit)
    checked = rows[start:]
    meta_rows: List[Dict[str, Any]] = []

    for pos, row in enumerate(checked, start=start):
        where = f"chain[{pos}]"
        rec_agent = str(row.get("agent_id") or "").strip()
        rec_event = str(row.get("quarantine_event_id") or "").strip()
        rec_hash = str(row.get("envelope_hash") or "").strip().lower()
        rec_prev = str(row.get("prev_hash") or "").strip().lower()
        rec_env_sha = str(row.get("envelope_sha256") or "").strip().lower()
        rec_env_path = str(row.get("envelope_path") or "").strip()
        rec_ts = int(row.get("ts") or 0)

        if rec_agent and rec_agent != aid:
            _fail("L4W_SUBJECT_MISMATCH", where, f"record_agent:{rec_agent}")
        if rec_prev and (not _is_sha256_hex(rec_prev)):
            _fail("L4W_CHAIN_BROKEN", f"{where}.prev_hash", "invalid_prev_hash")
        if not _is_sha256_hex(rec_hash):
            _fail("L4W_CHAIN_BROKEN", f"{where}.envelope_hash", "invalid_hash")
        if rec_env_sha and (not _is_sha256_hex(rec_env_sha)):
            _fail("L4W_CHAIN_BROKEN", f"{where}.envelope_sha256", "invalid_hash")

        expected_prev = "" if pos == 0 else str(rows[pos - 1].get("envelope_hash") or "").strip().lower()
        if rec_prev != expected_prev:
            _fail("L4W_CHAIN_BROKEN", f"{where}.prev_hash", f"expected:{expected_prev} got:{rec_prev}")

        path_rep = _audit_resolve_in_root(envelopes_root, rec_env_path, code_prefix="L4W")
        if not bool(path_rep.get("ok")):
            _fail(str(path_rep.get("code") or "L4W_PATH_FORBIDDEN"), f"{where}.envelope_path", str(path_rep.get("detail") or ""))
            continue
        env_path = Path(str(path_rep.get("path") or "")).resolve()
        if (not env_path.exists()) or (not env_path.is_file()):
            _fail("L4W_FILE_NOT_FOUND", f"{where}.envelope_path", str(env_path))
            continue

        actual_env_sha = sha256_file(env_path).lower()
        if rec_env_sha and rec_env_sha != actual_env_sha:
            _fail("L4W_HASH_MISMATCH", f"{where}.envelope_sha256", f"record:{rec_env_sha} actual:{actual_env_sha}")

        try:
            env_obj = json.loads(env_path.read_text(encoding="utf-8"))
        except Exception:
            _fail("L4W_SCHEMA_INVALID", where, "envelope_json_invalid")
            continue
        if not isinstance(env_obj, dict):
            _fail("L4W_SCHEMA_INVALID", where, "envelope_not_object")
            continue

        shape = _validate_envelope_shape(env_obj, require_sig=True)
        if not bool(shape.get("ok")):
            _fail(str(shape.get("error_code") or "L4W_SCHEMA_INVALID"), where, str(shape.get("error") or "shape_invalid"))

        comp_hash = compute_envelope_hash(env_obj)
        chain_obj = dict(env_obj.get("chain") or {})
        if str(chain_obj.get("envelope_hash") or "").strip().lower() != comp_hash:
            _fail("L4W_HASH_MISMATCH", f"{where}.chain.envelope_hash", "computed_mismatch")
        if rec_hash and rec_hash != comp_hash:
            _fail("L4W_HASH_MISMATCH", f"{where}.record.envelope_hash", "record_mismatch")
        if str(chain_obj.get("prev_hash") or "").strip().lower() != rec_prev:
            _fail("L4W_CHAIN_BROKEN", f"{where}.chain.prev_hash", "prev_mismatch")

        env_verify = verify_envelope(env_obj, pub_path=str(pub_path))
        if not bool(env_verify.get("ok")):
            v_code = str(env_verify.get("error_code") or "L4W_SIG_INVALID")
            if str(env_verify.get("error") or "") == "l4w_pub_fingerprint_mismatch":
                v_code = "L4W_PUBKEY_FINGERPRINT_MISMATCH"
            _fail(v_code, where, str(env_verify.get("error") or "sig_invalid"))

        subject = dict(env_obj.get("subject") or {})
        env_agent = str(subject.get("agent_id") or "").strip()
        env_event = str(subject.get("quarantine_event_id") or "").strip()
        if env_agent != aid:
            _fail("L4W_SUBJECT_MISMATCH", f"{where}.subject.agent_id", env_agent)
        if not env_event:
            _fail("L4W_SUBJECT_MISMATCH", f"{where}.subject.quarantine_event_id", "empty")
        if rec_event and env_event and rec_event != env_event:
            _fail("L4W_SUBJECT_MISMATCH", f"{where}.subject.quarantine_event_id", f"record:{rec_event} envelope:{env_event}")

        if prof in {"HRO", "FULL"}:
            claimed_fp = str((dict(env_obj.get("sig") or {})).get("pub_fingerprint") or "").strip().lower()
            if not cfg_pub_fp:
                _fail("L4W_PUBKEY_FINGERPRINT_MISMATCH", where, "configured_pubkey_missing")
            elif claimed_fp != cfg_pub_fp:
                _fail("L4W_PUBKEY_FINGERPRINT_MISMATCH", f"{where}.sig.pub_fingerprint", f"claimed:{claimed_fp} configured:{cfg_pub_fp}")

        evidence_ref = dict(env_obj.get("evidence_ref") or {})
        evidence_rel = _normalize_rel_path(str(evidence_ref.get("path") or ""))
        evidence_sha = str(evidence_ref.get("sha256") or "").strip().lower()
        evidence_payload_hash = str(evidence_ref.get("evidence_payload_hash") or "").strip().lower()
        if not _is_sha256_hex(evidence_sha):
            _fail("L4W_SCHEMA_INVALID", f"{where}.evidence_ref.sha256", "invalid_sha")

        ev_packet: Dict[str, Any] = {}
        ev_res = _audit_resolve_in_root(evidence_root, evidence_rel, code_prefix="EVIDENCE")
        if not bool(ev_res.get("ok")):
            _fail(str(ev_res.get("code") or "EVIDENCE_PATH_FORBIDDEN"), f"{where}.evidence_ref.path", str(ev_res.get("detail") or ""))
        else:
            ev_path = Path(str(ev_res.get("path") or "")).resolve()
            if ev_path.exists() and ev_path.is_file():
                report["evidence"]["files_checked"] = int(report["evidence"]["files_checked"]) + 1
                ev_actual_sha = sha256_file(ev_path).lower()
                if ev_actual_sha != evidence_sha:
                    _fail("EVIDENCE_HASH_MISMATCH", f"{where}.evidence_ref.sha256", f"ref:{evidence_sha} actual:{ev_actual_sha}")
                try:
                    ev_raw = json.loads(ev_path.read_text(encoding="utf-8"))
                    ev_packet = dict(ev_raw) if isinstance(ev_raw, dict) else {}
                except Exception:
                    ev_packet = {}
                    _fail("EVIDENCE_SCHEMA_INVALID", where, "evidence_json_invalid")
            elif require_evidence:
                _fail("EVIDENCE_NOT_FOUND", f"{where}.evidence_ref.path", str(ev_path))
            else:
                _warn("EVIDENCE_NOT_FOUND", f"{where}.evidence_ref.path", str(ev_path))

        if prof in {"HRO", "FULL"}:
            if not ev_packet:
                _fail("EVIDENCE_SCHEMA_INVALID", where, "evidence_packet_missing")
            elif evidence_signing is None or (hasattr(evidence_signing, "is_available") and not evidence_signing.is_available()):
                _fail("ED25519_UNAVAILABLE", where, "evidence_signing_unavailable")
            else:
                report["evidence"]["sig_checked"] = True
                ev_verify = evidence_signing.verify_packet(ev_packet, pub_path=str(pub_path))
                if not bool(ev_verify.get("ok")):
                    _fail(str(ev_verify.get("error_code") or "EVIDENCE_SIG_INVALID"), where, str(ev_verify.get("error") or "evidence_sig_invalid"))
                if evidence_payload_hash:
                    payload_now = str(ev_verify.get("payload_hash") or (dict(ev_packet.get("sig") or {})).get("payload_hash") or "").strip().lower()
                    if payload_now and payload_now != evidence_payload_hash:
                        _fail(
                            "EVIDENCE_PAYLOAD_HASH_MISMATCH",
                            f"{where}.evidence_ref.evidence_payload_hash",
                            f"ref:{evidence_payload_hash} packet:{payload_now}",
                        )
            ev_agent = str(ev_packet.get("agent_id") or "").strip()
            ev_event = str(ev_packet.get("quarantine_event_id") or "").strip()
            if ev_agent and ev_agent != env_agent:
                _fail("EVIDENCE_SUBJECT_MISMATCH", where, f"packet_agent:{ev_agent}")
            if ev_event and ev_event != env_event:
                _fail("EVIDENCE_SUBJECT_MISMATCH", where, f"packet_event:{ev_event}")

            disclosure_file = (disclosures_root / f"{comp_hash}.json").resolve()
            has_disclosure = disclosure_file.exists() and disclosure_file.is_file()
            if has_disclosure or require_disclosure:
                report["disclosure"]["checked"] = True
                if not has_disclosure:
                    _fail("L4W_DISCLOSURE_MISSING", where, str(disclosure_file))
                else:
                    try:
                        dis_raw = json.loads(disclosure_file.read_text(encoding="utf-8"))
                    except Exception:
                        dis_raw = {}
                        _fail("L4W_SCHEMA_INVALID", where, "disclosure_json_invalid")
                    if isinstance(dis_raw, dict):
                        dis_verify = verify_disclosure(env_obj, dis_raw)
                        if not bool(dis_verify.get("ok")):
                            _fail(str(dis_verify.get("error_code") or "L4W_SCHEMA_INVALID"), where, str(dis_verify.get("error") or "disclosure_invalid"))
                        paths_ok = dict(dis_verify.get("which_paths_ok") or {})
                        merged_paths = dict(report["disclosure"].get("paths_ok") or {})
                        for key, val in paths_ok.items():
                            merged_paths[str(key)] = bool(val)
                        report["disclosure"]["paths_ok"] = merged_paths
                        if not bool(paths_ok.get("claim.reviewer")):
                            _fail("L4W_SCHEMA_INVALID", where, "disclosure_reviewer_commit_mismatch")
                        if not bool(paths_ok.get("claim.summary")):
                            _fail("L4W_SCHEMA_INVALID", where, "disclosure_summary_commit_mismatch")

        meta_rows.append(
            {
                "row_index": pos,
                "ts": rec_ts,
                "event_id": str(env_event or rec_event or ""),
                "envelope_hash": comp_hash,
                "prev_hash": rec_prev,
                "evidence_sha256": evidence_sha,
                "record_envelope_sha256": str(rec_env_sha or actual_env_sha or ""),
            }
        )

    if meta_rows:
        tail = dict(meta_rows[-1] or {})
        report["checked_records"] = len(meta_rows)
        report["last"] = {
            "envelope_hash": str(tail.get("envelope_hash") or ""),
            "prev_hash": str(tail.get("prev_hash") or ""),
            "ts": int(tail.get("ts") or 0),
            "quarantine_event_id": str(tail.get("event_id") or ""),
        }

    if prof == "FULL" and meta_rows:
        events: List[Dict[str, Any]] = []
        if not events_path.exists():
            _fail("DRIFT_EVENTS_NOT_FOUND", "drift.events", str(events_path))
        else:
            try:
                with events_path.open("r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        s = line.strip()
                        if not s:
                            continue
                        try:
                            obj = json.loads(s)
                        except Exception:
                            continue
                        if isinstance(obj, dict):
                            events.append(dict(obj))
            except Exception as exc:
                _fail("DRIFT_EVENTS_NOT_FOUND", "drift.events", f"read_error:{exc.__class__.__name__}")

        for row in meta_rows:
            hit = False
            for event in events:
                if str(event.get("type") or "") != "QUARANTINE_CLEAR":
                    continue
                if str(event.get("agent_id") or "") != aid:
                    continue
                if str(event.get("event_id") or "") != str(row.get("event_id") or ""):
                    continue
                details = dict(event.get("details") or {})
                if (
                    str(details.get("l4w_envelope_hash") or "").strip().lower() == str(row.get("envelope_hash") or "").lower()
                    and str(details.get("evidence_sha256") or "").strip().lower() == str(row.get("evidence_sha256") or "").lower()
                ):
                    hit = True
                    break
            if not hit:
                _fail("DRIFT_EVENT_REF_MISSING", f"drift.events:{row.get('event_id')}", str(row.get("envelope_hash") or ""))

        if state_path.exists():
            try:
                state_raw = json.loads(state_path.read_text(encoding="utf-8"))
            except Exception:
                state_raw = {}
                _fail("DRIFT_STATE_REF_MISMATCH", "drift.state", "state_json_invalid")
            if isinstance(state_raw, dict):
                state_row = dict(state_raw.get(aid) or {})
                if state_row:
                    cleared = dict(state_row.get("cleared") or {})
                    tail = dict(meta_rows[-1] or {})
                    if str(cleared.get("l4w_envelope_hash") or "").strip().lower() != str(tail.get("envelope_hash") or "").lower():
                        _fail("DRIFT_STATE_REF_MISMATCH", "drift.state.l4w_envelope_hash", "mismatch")
                    if str(cleared.get("evidence_sha256") or "").strip().lower() != str(tail.get("evidence_sha256") or "").lower():
                        _fail("DRIFT_STATE_REF_MISMATCH", "drift.state.evidence_sha256", "mismatch")
                else:
                    _warn("DRIFT_STATE_REF_MISSING", "drift.state", f"agent_not_found:{aid}")

        journal_loc = _audit_locate_volition_journal(persist)
        if not bool(journal_loc.get("ok")):
            _fail(str(journal_loc.get("code") or "VOLITION_JOURNAL_NOT_FOUND"), "volition.journal", str(journal_loc.get("detail") or ""))
        else:
            journal_path = Path(str(journal_loc.get("path") or "")).resolve()
            if not journal_path.exists():
                _fail("VOLITION_JOURNAL_NOT_FOUND", "volition.journal", str(journal_path))
            else:
                entries: List[Dict[str, Any]] = []
                try:
                    with journal_path.open("r", encoding="utf-8", errors="replace") as f:
                        for line in f:
                            s = line.strip()
                            if not s:
                                continue
                            try:
                                obj = json.loads(s)
                            except Exception:
                                continue
                            if isinstance(obj, dict):
                                entries.append(dict(obj))
                except Exception as exc:
                    _fail("VOLITION_REF_MISSING", "volition.journal", f"read_error:{exc.__class__.__name__}")

                for row in meta_rows:
                    row_ts = int(row.get("ts") or 0)
                    row_eid = str(row.get("event_id") or "")
                    row_sha = str(row.get("evidence_sha256") or "").lower()
                    row_hash = str(row.get("envelope_hash") or "").lower()
                    row_env_sha = str(row.get("record_envelope_sha256") or "").lower()
                    hit = False
                    for entry in entries:
                        step = str(entry.get("step") or "").strip().lower()
                        action_id = str(entry.get("action_id") or "").strip().lower()
                        meta = dict(entry.get("metadata") or {})
                        meta_action = str(meta.get("action_id") or "").strip().lower()
                        if step != "drift.quarantine.clear" and action_id != "drift.quarantine.clear" and meta_action != "drift.quarantine.clear":
                            continue
                        ent_agent = str(entry.get("agent_id") or meta.get("agent_id") or "").strip()
                        if ent_agent and ent_agent != aid:
                            continue
                        ent_ts = int(entry.get("ts") or 0)
                        if ent_ts and row_ts and abs(ent_ts - row_ts) > 86400:
                            continue
                        ent_event = str(meta.get("quarantine_event_id") or entry.get("event_id") or "").strip()
                        if ent_event and row_eid and ent_event != row_eid:
                            continue
                        ent_sha = _audit_extract_meta_ref(meta, ("evidence_sha256", "evidence_hash"))
                        ent_l4w = _audit_extract_meta_ref(meta, ("l4w_envelope_hash", "l4w_hash", "l4w_envelope_sha256"))
                        if ent_sha == row_sha and ent_l4w in {row_hash, row_env_sha}:
                            hit = True
                            break
                    if not hit:
                        _fail("VOLITION_REF_MISSING", f"volition.event:{row_eid}", row_hash)

    report["ok"] = not bool(report["errors"])
    last_error = ""
    if report["errors"]:
        last_error = str(report["errors"][0].get("code") or "L4W_AUDIT_ERROR")
    elif report["warnings"]:
        last_error = str(report["warnings"][0].get("code") or "")
    _update_last_audit(prof, bool(report["ok"]), last_error)
    return report


def build_chain_status() -> Dict[str, Any]:
    out = {
        "agents_tracked": 0,
        "total_records": 0,
        "last_envelope_ts": 0,
        "last_envelope_hash": "",
        "last_prev_hash": "",
        "last_error": "",
    }
    chain_dir = _chain_dir()
    if not chain_dir.exists():
        return out

    last_row: Dict[str, Any] = {}
    for p in sorted(chain_dir.glob("*.jsonl")):
        rows: List[Dict[str, Any]] = []
        try:
            with p.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    s = line.strip()
                    if not s:
                        continue
                    try:
                        row = json.loads(s)
                    except Exception:
                        continue
                    if isinstance(row, dict):
                        rows.append(row)
        except Exception as exc:
            out["last_error"] = f"chain_read_error:{exc.__class__.__name__}"
            continue
        if not rows:
            continue
        out["agents_tracked"] = int(out["agents_tracked"]) + 1
        out["total_records"] = int(out["total_records"]) + len(rows)
        tail = dict(rows[-1] or {})
        tail_ts = int(tail.get("ts") or 0)
        if tail_ts >= int(out.get("last_envelope_ts") or 0):
            out["last_envelope_ts"] = tail_ts
            out["last_envelope_hash"] = str(tail.get("envelope_hash") or "")
            out["last_prev_hash"] = str(tail.get("prev_hash") or "")
            last_row = tail
    if last_row:
        out["last_envelope_ts"] = int(last_row.get("ts") or 0)
        out["last_envelope_hash"] = str(last_row.get("envelope_hash") or "")
        out["last_prev_hash"] = str(last_row.get("prev_hash") or "")
    return out


def build_l4w_status(
    *,
    slot: str,
    enforced: bool,
    degraded: bool,
    last_clear_l4w: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    last_audit = get_last_audit()
    chain = build_chain_status()
    if _env_bool("ESTER_L4W_CHAIN_DISABLED", False):
        chain["last_error"] = str(chain.get("last_error") or "chain_disabled")
    if (not _ED25519_OK) and bool(enforced):
        chain["last_error"] = str(chain.get("last_error") or "ED25519_UNAVAILABLE")
    last = {
        "ts": 0,
        "agent_id": "",
        "quarantine_event_id": "",
        "envelope_hash": "",
        "prev_hash": "",
        "envelope_path": "",
        "envelope_sha256": "",
        "pub_fingerprint": "",
    }
    if isinstance(last_clear_l4w, dict):
        last.update(
            {
                "ts": int(last_clear_l4w.get("ts") or 0),
                "agent_id": str(last_clear_l4w.get("agent_id") or ""),
                "quarantine_event_id": str(last_clear_l4w.get("quarantine_event_id") or ""),
                "envelope_hash": str(last_clear_l4w.get("envelope_hash") or ""),
                "prev_hash": str(last_clear_l4w.get("prev_hash") or ""),
                "envelope_path": str(last_clear_l4w.get("envelope_path") or ""),
                "envelope_sha256": str(last_clear_l4w.get("envelope_sha256") or ""),
                "pub_fingerprint": str(last_clear_l4w.get("pub_fingerprint") or ""),
            }
        )
    ok = bool(not str(chain.get("last_error") or "").strip())
    return {
        "ok": bool(ok),
        "slot": "B" if str(slot or "").strip().upper() == "B" else "A",
        "enforced": bool(enforced),
        "degraded": bool(degraded),
        "conformance": {
            "supported": list(_SUPPORTED_PROFILES),
            "default_profile": default_profile(),
            "last_audit_ts": int(last_audit.get("ts") or 0),
            "last_audit_profile": str(last_audit.get("profile") or ""),
            "last_audit_ok": bool(last_audit.get("ok")),
            "last_audit_error": str(last_audit.get("error") or ""),
        },
        "chain": chain,
        "last_clear_l4w": last,
    }


__all__ = [
    "is_available",
    "ensure_keypair",
    "supported_profiles",
    "default_profile",
    "normalize_profile",
    "get_last_audit",
    "verify_agent_chain",
    "canonical_bytes",
    "compute_envelope_hash",
    "build_envelope_for_clear",
    "sign_envelope",
    "verify_envelope",
    "build_disclosure",
    "verify_disclosure",
    "resolve_envelope_path",
    "envelope_storage_path",
    "disclosure_storage_path",
    "write_envelope",
    "write_disclosure",
    "chain_path",
    "chain_head",
    "verify_chain_prev_hash",
    "append_chain_record",
    "build_chain_status",
    "build_l4w_status",
    "sha256_file",
]
