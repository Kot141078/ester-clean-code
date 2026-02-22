# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from modules.runtime import bundle_signing

ENTRY_SCHEMA_V1 = "ester.publisher.roster_log_entry.v1"
ENTRY_SIG_SCHEMA_V1 = "ester.publisher.roster_log_sig.v1"
ENTRY_SIG_MSG_V1 = "ester.publisher.roster_log_entry_hash.v1"


def _is_sha256_hex(value: str) -> bool:
    s = str(value or "").strip().lower()
    return len(s) == 64 and all(ch in "0123456789abcdef" for ch in s)


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _log_root(log_path: Path) -> Path:
    parent = log_path.resolve().parent
    if parent.name.lower() == "keys":
        return parent.parent.resolve()
    return parent.resolve()


def canonical_entry_body(entry: Dict[str, Any]) -> Dict[str, Any]:
    src = dict(entry or {})
    src.pop("sig_entry", None)
    src.pop("entry_hash", None)
    return src


def compute_entry_hash(entry_body_dict: Dict[str, Any]) -> str:
    body = canonical_entry_body(entry_body_dict)
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _entry_message(entry_hash: str) -> bytes:
    s = str(entry_hash or "").strip().lower()
    if not _is_sha256_hex(s):
        raise ValueError("log_entry_hash_invalid")
    return f"{ENTRY_SIG_MSG_V1}:{s}".encode("ascii")


def sign_entry_hash(entry_hash: str, roster_root_privkey_path: str, roster_root_pubkey_path: str) -> Dict[str, Any]:
    if not bundle_signing.is_available():
        return {"ok": False, "error_code": "ED25519_UNAVAILABLE", "error": "ed25519_unavailable"}
    try:
        sk = bundle_signing.load_privkey(str(roster_root_privkey_path or "").strip())
    except Exception:
        return {"ok": False, "error_code": "LOG_SIG_INVALID", "error": "roster_root_privkey_invalid"}
    pub_fp = bundle_signing.pub_fingerprint_from_path(str(roster_root_pubkey_path or "").strip())
    if not pub_fp:
        return {"ok": False, "error_code": "LOG_SIG_INVALID", "error": "roster_root_pubkey_invalid"}
    try:
        sig_raw = sk.sign(_entry_message(entry_hash))
    except Exception:
        return {"ok": False, "error_code": "LOG_SIG_INVALID", "error": "log_sig_sign_failed"}
    return {
        "ok": True,
        "sig_entry": {
            "schema": ENTRY_SIG_SCHEMA_V1,
            "alg": "ed25519",
            "key_id": "roster-root",
            "msg": ENTRY_SIG_MSG_V1,
            "signed": str(entry_hash or "").strip().lower(),
            "pub_fingerprint": str(pub_fp),
            "sig_b64": base64.b64encode(sig_raw).decode("ascii"),
        },
    }


def append_entry(log_path: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    p = Path(str(log_path or "").strip()).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(entry or {}), ensure_ascii=True, separators=(",", ":"))
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return {"ok": True, "log_path": str(p)}


def read_entries(log_path: str, max_entries: int = 0) -> Dict[str, Any]:
    p = Path(str(log_path or "").strip()).resolve()
    if not p.exists() or not p.is_file():
        return {"ok": False, "error_code": "LOG_MISSING", "error": "log_missing", "entries": [], "log_path": str(p)}
    rows: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8", errors="replace") as f:
        for line_no, line in enumerate(f, start=1):
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except Exception:
                return {
                    "ok": False,
                    "error_code": "LOG_PARSE_ERROR",
                    "error": "log_parse_error",
                    "line": line_no,
                    "entries": rows,
                    "log_path": str(p),
                }
            if not isinstance(obj, dict):
                return {
                    "ok": False,
                    "error_code": "LOG_PARSE_ERROR",
                    "error": "log_entry_not_object",
                    "line": line_no,
                    "entries": rows,
                    "log_path": str(p),
                }
            rows.append(dict(obj))
    if int(max_entries or 0) > 0:
        rows = rows[-max(1, int(max_entries or 0)) :]
    return {"ok": True, "entries": rows, "log_path": str(p)}


def update_head(head_path: str, last_entry_hash: str, entries_count: int, last_ts: int) -> Dict[str, Any]:
    p = Path(str(head_path or "").strip()).resolve()
    payload = {
        "schema": "ester.publisher.roster_log_head.v1",
        "last_entry_hash": str(last_entry_hash or "").strip().lower(),
        "entries_count": int(max(0, int(entries_count or 0))),
        "last_ts": int(max(0, int(last_ts or 0))),
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return {"ok": True, "head_path": str(p), "head": payload}


def _verify_sig_entry(entry_hash: str, sig_entry: Dict[str, Any], roster_root_pubkey_path: str) -> Dict[str, Any]:
    if not bundle_signing.is_available():
        return {"ok": False, "error_code": "ED25519_UNAVAILABLE", "error": "ed25519_unavailable"}
    sig = dict(sig_entry or {})
    if str(sig.get("schema") or "") != ENTRY_SIG_SCHEMA_V1:
        return {"ok": False, "error_code": "LOG_SIG_INVALID", "error": "log_sig_schema_invalid"}
    if str(sig.get("alg") or "").strip().lower() != "ed25519":
        return {"ok": False, "error_code": "LOG_SIG_INVALID", "error": "log_sig_alg_invalid"}
    if str(sig.get("msg") or "") != ENTRY_SIG_MSG_V1:
        return {"ok": False, "error_code": "LOG_SIG_INVALID", "error": "log_sig_msg_invalid"}
    if str(sig.get("signed") or "").strip().lower() != str(entry_hash or "").strip().lower():
        return {"ok": False, "error_code": "LOG_SIG_INVALID", "error": "log_sig_signed_mismatch"}
    try:
        pk = bundle_signing.load_pubkey(str(roster_root_pubkey_path or "").strip())
    except Exception:
        return {"ok": False, "error_code": "LOG_SIG_INVALID", "error": "roster_root_pubkey_invalid"}
    fp = bundle_signing.pub_fingerprint(pk)
    claimed_fp = str(sig.get("pub_fingerprint") or "").strip().lower()
    if claimed_fp and claimed_fp != fp:
        return {"ok": False, "error_code": "LOG_SIG_INVALID", "error": "log_sig_pub_fingerprint_mismatch"}
    try:
        sig_raw = base64.b64decode(str(sig.get("sig_b64") or "").strip(), validate=True)
    except Exception:
        return {"ok": False, "error_code": "LOG_SIG_INVALID", "error": "log_sig_invalid"}
    if len(sig_raw) != 64:
        return {"ok": False, "error_code": "LOG_SIG_INVALID", "error": "log_sig_invalid"}
    try:
        pk.verify(sig_raw, _entry_message(entry_hash))
    except Exception:
        return {"ok": False, "error_code": "LOG_SIG_INVALID", "error": "log_sig_invalid"}
    return {"ok": True}


def verify_log_chain(
    log_path: str,
    roster_root_pubkey_path: str,
    *,
    require_strict_append: bool = True,
    require_publications: bool = False,
) -> Dict[str, Any]:
    loaded = read_entries(log_path, max_entries=0)
    if not bool(loaded.get("ok")):
        return {
            "ok": False,
            "error_code": str(loaded.get("error_code") or "LOG_MISSING"),
            "error": str(loaded.get("error") or "log_missing"),
            "entries_count": 0,
            "last_entry_hash": "",
            "last_ts": 0,
            "errors": [{"code": str(loaded.get("error_code") or "LOG_MISSING"), "detail": str(loaded.get("error") or "log_missing")}],
            "entries": [],
        }
    entries = [dict(x) for x in list(loaded.get("entries") or []) if isinstance(x, dict)]
    if not entries:
        return {
            "ok": False,
            "error_code": "LOG_MISSING",
            "error": "log_missing",
            "entries_count": 0,
            "last_entry_hash": "",
            "last_ts": 0,
            "errors": [{"code": "LOG_MISSING", "detail": "empty"}],
            "entries": [],
        }

    p = Path(str(log_path or "").strip()).resolve()
    root = _log_root(p)
    errors: List[Dict[str, Any]] = []
    prev_hash_expected = ""
    for idx, row in enumerate(entries):
        where = f"entry[{idx}]"
        schema = str(row.get("schema") or "")
        if schema != ENTRY_SCHEMA_V1:
            errors.append({"code": "LOG_PARSE_ERROR", "where": where, "detail": "schema_invalid"})
            break
        entry_hash = str(row.get("entry_hash") or "").strip().lower()
        calc_hash = compute_entry_hash(row)
        if entry_hash != calc_hash:
            errors.append({"code": "LOG_ENTRY_HASH_MISMATCH", "where": where, "detail": f"claimed:{entry_hash} actual:{calc_hash}"})
            break

        prev_hash = str(row.get("prev_hash") or "").strip().lower()
        if idx == 0:
            if require_strict_append and prev_hash:
                errors.append({"code": "LOG_CHAIN_BROKEN", "where": f"{where}.prev_hash", "detail": f"expected_empty got:{prev_hash}"})
                break
            prev_hash_expected = entry_hash
        else:
            if prev_hash != prev_hash_expected:
                errors.append({"code": "LOG_CHAIN_BROKEN", "where": f"{where}.prev_hash", "detail": f"expected:{prev_hash_expected} got:{prev_hash}"})
                break
            prev_hash_expected = entry_hash

        sig_rep = _verify_sig_entry(entry_hash, dict(row.get("sig_entry") or {}), roster_root_pubkey_path)
        if not bool(sig_rep.get("ok")):
            errors.append({"code": "LOG_SIG_INVALID", "where": f"{where}.sig_entry", "detail": str(sig_rep.get("error") or "log_sig_invalid")})
            break

        if require_publications:
            pub = dict(row.get("publication") or {})
            relpath = str(pub.get("relpath") or "").strip().replace("\\", "/")
            sha = str(pub.get("sha256") or "").strip().lower()
            if not relpath or Path(relpath).is_absolute():
                errors.append({"code": "LOG_PUBLICATION_MISSING", "where": f"{where}.publication.relpath", "detail": "invalid_relpath"})
                break
            pub_file = (root / relpath).resolve()
            if not _path_within(pub_file, root) or (not pub_file.exists()) or (not pub_file.is_file()):
                errors.append({"code": "LOG_PUBLICATION_MISSING", "where": f"{where}.publication.relpath", "detail": relpath})
                break
            if not _is_sha256_hex(sha):
                errors.append({"code": "LOG_PUBLICATION_SHA_MISMATCH", "where": f"{where}.publication.sha256", "detail": "invalid_sha256"})
                break
            actual_sha = hashlib.sha256(pub_file.read_bytes()).hexdigest()
            if actual_sha != sha:
                errors.append({"code": "LOG_PUBLICATION_SHA_MISMATCH", "where": f"{where}.publication.sha256", "detail": f"claimed:{sha} actual:{actual_sha}"})
                break

    last = dict(entries[-1]) if entries else {}
    return {
        "ok": bool(not errors),
        "error_code": str((errors[0] if errors else {}).get("code") or ""),
        "error": str((errors[0] if errors else {}).get("detail") or ""),
        "entries_count": len(entries),
        "last_entry_hash": str(last.get("entry_hash") or ""),
        "last_ts": _to_int(last.get("ts")),
        "errors": errors,
        "entries": entries,
    }


__all__ = [
    "ENTRY_SCHEMA_V1",
    "ENTRY_SIG_SCHEMA_V1",
    "ENTRY_SIG_MSG_V1",
    "compute_entry_hash",
    "sign_entry_hash",
    "append_entry",
    "read_entries",
    "verify_log_chain",
    "update_head",
]
