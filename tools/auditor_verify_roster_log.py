# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.runtime import publisher_transparency_log


def _persist_dir(raw: str) -> Path:
    if str(raw or "").strip():
        return Path(str(raw or "").strip()).resolve()
    env = str(os.getenv("PERSIST_DIR") or "").strip()
    if env:
        return Path(env).resolve()
    return (ROOT / "data").resolve()


def _is_sha256_hex(value: str) -> bool:
    s = str(value or "").strip().lower()
    return len(s) == 64 and all(ch in "0123456789abcdef" for ch in s)


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(raw) if isinstance(raw, dict) else {}


def _add_error(report: Dict[str, Any], code: str, where: str, detail: str) -> None:
    report.setdefault("errors", []).append({"code": code, "where": where, "detail": detail})


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify publisher roster transparency log")
    ap.add_argument("--persist-dir", default="")
    ap.add_argument("--pubkey-roster-root", required=True)
    ap.add_argument("--log", default="")
    ap.add_argument("--head", default="")
    ap.add_argument("--require-publications", action="store_true")
    ap.add_argument("--find-body-sha256", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ns = ap.parse_args()

    persist = _persist_dir(str(ns.persist_dir or ""))
    keys_dir = (persist / "keys").resolve()
    log_path = Path(str(ns.log)).resolve() if str(ns.log or "").strip() else (keys_dir / "publisher_roster_log.jsonl").resolve()
    head_path = Path(str(ns.head)).resolve() if str(ns.head or "").strip() else (keys_dir / "publisher_roster_log_head.json").resolve()
    root_pub = Path(str(ns.pubkey_roster_root or "")).resolve()

    report: Dict[str, Any] = {
        "ok": False,
        "persist_dir": str(persist),
        "log_path": str(log_path),
        "head_path": str(head_path),
        "pubkey_roster_root": str(root_pub),
        "entries_count": 0,
        "last_entry_hash": "",
        "last_ts": 0,
        "target_body_sha256": str(ns.find_body_sha256 or "").strip().lower(),
        "target_found": False,
        "errors": [],
    }

    if not root_pub.exists() or not root_pub.is_file():
        _add_error(report, "ROSTER_ROOT_PUBKEY_REQUIRED", "pubkey_roster_root", "missing")
    if str(ns.find_body_sha256 or "").strip() and (not _is_sha256_hex(str(ns.find_body_sha256 or "").strip())):
        _add_error(report, "LOG_TARGET_NOT_FOUND", "find_body_sha256", "invalid")

    if not report["errors"]:
        verify = publisher_transparency_log.verify_log_chain(
            str(log_path),
            str(root_pub),
            require_strict_append=True,
            require_publications=bool(ns.require_publications),
        )
        report["entries_count"] = int(verify.get("entries_count") or 0)
        report["last_entry_hash"] = str(verify.get("last_entry_hash") or "")
        report["last_ts"] = int(verify.get("last_ts") or 0)
        for row in list(verify.get("errors") or []):
            if isinstance(row, dict):
                _add_error(
                    report,
                    str(row.get("code") or verify.get("error_code") or "LOG_CHAIN_BROKEN"),
                    str(row.get("where") or "log"),
                    str(row.get("detail") or verify.get("error") or "log_verify_failed"),
                )
        entries = [dict(x) for x in list(verify.get("entries") or []) if isinstance(x, dict)]
        if str(report.get("target_body_sha256") or ""):
            target = str(report.get("target_body_sha256") or "")
            report["target_found"] = bool(any(str(row.get("body_sha256") or "").strip().lower() == target for row in entries))
            if not bool(report["target_found"]):
                _add_error(report, "LOG_TARGET_NOT_FOUND", "find_body_sha256", target)

    if head_path.exists() and head_path.is_file():
        head = _load_json(head_path)
        head_last = str(head.get("last_entry_hash") or "").strip().lower()
        head_count = int(head.get("entries_count") or 0)
        if head_last and report.get("last_entry_hash") and head_last != str(report.get("last_entry_hash") or "").lower():
            _add_error(report, "LOG_CHAIN_BROKEN", "head.last_entry_hash", f"head:{head_last} log:{report.get('last_entry_hash')}")
        if int(report.get("entries_count") or 0) and head_count != int(report.get("entries_count") or 0):
            _add_error(report, "LOG_CHAIN_BROKEN", "head.entries_count", f"head:{head_count} log:{report.get('entries_count')}")

    report["ok"] = bool(not report["errors"])
    rc = 0 if bool(report["ok"]) else 2
    if bool(ns.json):
        print(json.dumps(report, ensure_ascii=True, indent=2))
    elif bool(ns.quiet):
        print("PASS" if rc == 0 else "FAIL")
    else:
        print("PASS" if rc == 0 else "FAIL")
        if rc != 0:
            for row in list(report.get("errors") or [])[:10]:
                print(f"{row.get('code')} {row.get('where')} {row.get('detail')}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
