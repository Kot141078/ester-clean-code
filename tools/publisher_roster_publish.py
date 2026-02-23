# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.runtime import publisher_roster, publisher_transparency_log


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _slot() -> str:
    raw = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if raw == "B" else "A"


def _write_json(path: Path, payload: Dict[str, Any], *, canonical: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if canonical:
        path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(raw) if isinstance(raw, dict) else {}


def _persist_dir(raw: str) -> Path:
    if str(raw or "").strip():
        return Path(str(raw or "").strip()).resolve()
    env = str(os.getenv("PERSIST_DIR") or "").strip()
    if env:
        return Path(env).resolve()
    return (ROOT / "data").resolve()


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish roster snapshot + transparency log entry")
    ap.add_argument("--persist-dir", default="")
    ap.add_argument("--roster", default="")
    ap.add_argument("--roster-root-privkey", default="")
    ap.add_argument("--roster-root-pubkey", default="")
    ap.add_argument("--op", default="update")
    ap.add_argument("--reason", default="")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--no-strict", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ns = ap.parse_args()

    persist = _persist_dir(str(ns.persist_dir or ""))
    keys_dir = (persist / "keys").resolve()
    keys_dir.mkdir(parents=True, exist_ok=True)
    roster_path = Path(str(ns.roster or "")).resolve() if str(ns.roster or "").strip() else (keys_dir / "publisher_roster.json").resolve()
    root_priv = Path(str(ns.roster_root_privkey or os.getenv("ESTER_ROSTER_ROOT_PRIVKEY_PATH") or "")).resolve() if str(ns.roster_root_privkey or os.getenv("ESTER_ROSTER_ROOT_PRIVKEY_PATH") or "").strip() else Path("")
    root_pub = Path(str(ns.roster_root_pubkey or os.getenv("ESTER_ROSTER_ROOT_PUBKEY_PATH") or "")).resolve() if str(ns.roster_root_pubkey or os.getenv("ESTER_ROSTER_ROOT_PUBKEY_PATH") or "").strip() else Path("")
    warnings: List[str] = []
    errors: List[Dict[str, str]] = []
    slot = _slot()
    strict = slot == "B"
    if bool(ns.strict):
        strict = True
    if bool(ns.no_strict):
        if slot == "B":
            warnings.append("strict_forced_in_slot_b")
        else:
            strict = False

    if not roster_path.exists() or not roster_path.is_file():
        out = {"ok": False, "error_code": "ROSTER_REQUIRED", "error": "roster_missing", "roster_path": str(roster_path)}
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 2
    if not _path_within(roster_path, persist):
        out = {"ok": False, "error_code": "ROSTER_REQUIRED", "error": "roster_path_forbidden", "roster_path": str(roster_path)}
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 2
    if (not root_priv) or (not root_pub):
        out = {"ok": False, "error_code": "ROSTER_ROOT_PUBKEY_REQUIRED", "error": "roster_root_keys_missing"}
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 2
    if (not root_priv.exists()) or (not root_priv.is_file()) or (not root_pub.exists()) or (not root_pub.is_file()):
        out = {"ok": False, "error_code": "ROSTER_ROOT_PUBKEY_REQUIRED", "error": "roster_root_keys_missing"}
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 2
    if (not _path_within(root_priv, persist)) or (not _path_within(root_pub, persist)):
        out = {"ok": False, "error_code": "ROSTER_ROOT_PUBKEY_REQUIRED", "error": "roster_root_key_path_forbidden"}
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 2

    roster_obj = publisher_roster.normalize_roster(_load_json(roster_path))
    verify_roster = publisher_roster.verify_roster_sig(roster_obj, str(root_pub))
    if not bool(verify_roster.get("ok")):
        code = str(verify_roster.get("error_code") or "ROSTER_SIG_INVALID")
        detail = str(verify_roster.get("error") or "roster_sig_invalid")
        if strict:
            out = {"ok": False, "error_code": code, "error": detail}
            print(json.dumps(out, ensure_ascii=True, indent=2))
            return 2
        warnings.append(f"roster_sig_warning:{code}:{detail}")

    body_sha = publisher_roster.compute_body_sha256(roster_obj)
    ts = int(time.time())
    pub_dir = (keys_dir / "roster_publications" / f"{ts}_{body_sha[:8]}").resolve()
    if not _path_within(pub_dir, persist):
        out = {"ok": False, "error_code": "LOG_PUBLICATION_MISSING", "error": "publication_path_forbidden"}
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 2
    pub_dir.mkdir(parents=True, exist_ok=True)
    pub_roster = (pub_dir / "publisher_roster.json").resolve()
    _write_json(pub_roster, roster_obj, canonical=True)
    pub_sha = hashlib.sha256(pub_roster.read_bytes()).hexdigest()
    (pub_dir / "publisher_roster.sha256").write_text(pub_sha + "\n", encoding="utf-8")
    publication_rel = str(pub_roster.relative_to(persist)).replace("\\", "/")

    log_path = (keys_dir / "publisher_roster_log.jsonl").resolve()
    head_path = (keys_dir / "publisher_roster_log_head.json").resolve()
    if log_path.exists():
        verify_log = publisher_transparency_log.verify_log_chain(
            str(log_path),
            str(root_pub),
            require_strict_append=True,
            require_publications=True,
        )
        if not bool(verify_log.get("ok")):
            out = {
                "ok": False,
                "error_code": str(verify_log.get("error_code") or "LOG_CHAIN_BROKEN"),
                "error": str(verify_log.get("error") or "log_verify_failed"),
                "errors": list(verify_log.get("errors") or []),
            }
            print(json.dumps(out, ensure_ascii=True, indent=2))
            return 2
        prev_hash = str(verify_log.get("last_entry_hash") or "")
        entries_count = int(verify_log.get("entries_count") or 0)
    else:
        prev_hash = ""
        entries_count = 0

    entry: Dict[str, Any] = {
        "schema": publisher_transparency_log.ENTRY_SCHEMA_V1,
        "ts": ts,
        "roster_id": str(roster_obj.get("roster_id") or ""),
        "op": str(ns.op or "update"),
        "reason": str(ns.reason or ""),
        "body_sha256": body_sha,
        "roster_sig": dict(roster_obj.get("sig") or {}),
        "publication": {
            "relpath": publication_rel,
            "sha256": pub_sha,
        },
        "prev_hash": str(prev_hash or ""),
    }
    entry_hash = publisher_transparency_log.compute_entry_hash(entry)
    entry["entry_hash"] = entry_hash
    sig_entry = publisher_transparency_log.sign_entry_hash(entry_hash, str(root_priv), str(root_pub))
    if not bool(sig_entry.get("ok")):
        out = {
            "ok": False,
            "error_code": str(sig_entry.get("error_code") or "LOG_SIG_INVALID"),
            "error": str(sig_entry.get("error") or "log_sig_invalid"),
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 2
    entry["sig_entry"] = dict(sig_entry.get("sig_entry") or {})

    appended = publisher_transparency_log.append_entry(str(log_path), entry)
    if not bool(appended.get("ok")):
        out = {"ok": False, "error_code": "LOG_CHAIN_BROKEN", "error": "log_append_failed"}
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 2

    head = publisher_transparency_log.update_head(str(head_path), entry_hash, entries_count + 1, ts)
    if not bool(head.get("ok")):
        out = {"ok": False, "error_code": "LOG_CHAIN_BROKEN", "error": "head_update_failed"}
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 2

    out = {
        "ok": True,
        "entry_hash": entry_hash,
        "prev_hash": str(prev_hash or ""),
        "body_sha256": body_sha,
        "publication_relpath": publication_rel,
        "log_path": str(log_path),
        "head_path": str(head_path),
        "strict": bool(strict),
        "warnings": warnings,
        "errors": errors,
    }
    if bool(ns.json):
        print(json.dumps(out, ensure_ascii=True, indent=2))
    elif not bool(ns.quiet):
        print(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
