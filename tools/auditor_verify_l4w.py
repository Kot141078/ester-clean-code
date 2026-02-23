# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.runtime import l4w_witness


def _normalize_profile(raw: str) -> str:
    value = str(raw or "").strip().upper()
    if not value:
        value = l4w_witness.default_profile()
    return value


def _exit_code(report: Dict[str, Any]) -> int:
    profile = str(report.get("profile") or "").strip().upper()
    errors = list(report.get("errors") or [])
    warnings = list(report.get("warnings") or [])
    if errors:
        return 2
    if profile == "BASE" and warnings:
        return 3
    return 0


def _print_text(report: Dict[str, Any], rc: int) -> None:
    ok = bool(rc in {0, 3})
    status = "PASS" if ok else "FAIL"
    print(status)
    if not ok:
        errors = list(report.get("errors") or [])
        for row in errors[:10]:
            code = str((dict(row or {})).get("code") or "L4W_AUDIT_ERROR")
            where = str((dict(row or {})).get("where") or "")
            detail = str((dict(row or {})).get("detail") or "")
            print(f"{code} {where} {detail}".strip())


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit L4 Witness chain by agent with BASE/HRO/FULL profiles")
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--profile", default="")
    ap.add_argument("--max-records", type=int, default=0)
    ap.add_argument("--check-disclosure", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--persist-dir", default="")
    ns = ap.parse_args()

    profile = _normalize_profile(str(ns.profile or ""))
    report = l4w_witness.verify_agent_chain(
        str(ns.agent_id or ""),
        profile=profile,
        max_records=int(ns.max_records or 0),
        check_disclosure=bool(ns.check_disclosure),
        persist_dir_override=str(ns.persist_dir or ""),
    )
    rc = _exit_code(report)

    if bool(ns.json):
        print(json.dumps(report, ensure_ascii=True, indent=2))
    elif bool(ns.quiet):
        print("PASS" if rc in {0, 3} else "FAIL")
    else:
        _print_text(report, rc)
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
