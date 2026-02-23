# -*- coding: utf-8 -*-
"""
RBAC diagnostics (offline).

Prints key RBAC env values and verifies strict behavior with empty headers.
No network calls.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable, List

from flask import Flask, request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.auth import rbac


def _truthy(v: str) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "on", "y")


def _fmt_roles(xs: Iterable[str]) -> str:
    vals: List[str] = [str(x).strip() for x in xs if str(x).strip()]
    if not vals:
        return "[]"
    return "[" + ", ".join(vals) + "]"


def main() -> int:
    print("RBAC DIAG")
    print(f"ESTER_LAB_MODE={os.getenv('ESTER_LAB_MODE', '0')}")
    print(f"RBAC_DEV_ROLES={os.getenv('RBAC_DEV_ROLES', '')}")
    print(f"RBAC_HEADER_ROLES={os.getenv('RBAC_HEADER_ROLES', rbac.HDR_ROLES)}")

    app = Flask("diag_rbac")
    strict_pass = False

    with app.test_request_context("/_diag/rbac", method="GET", headers={}):
        hdr_seen = bool(request.headers.get(rbac.HDR_ROLES) or request.headers.get("X-Roles"))
        roles_empty = rbac.get_current_roles()
        print(f"headers_seen(empty)={'yes' if hdr_seen else 'no'}")
        print(f"roles_with_empty_headers={_fmt_roles(roles_empty)}")
        strict_pass = not rbac.has_any_role(["admin"])
        print(f"strict_denies_when_no_roles={'PASS' if strict_pass else 'FAIL'}")

    hdr_name = os.getenv("RBAC_HEADER_ROLES", rbac.HDR_ROLES) or rbac.HDR_ROLES
    with app.test_request_context("/_diag/rbac", method="GET", headers={hdr_name: "operator"}):
        hdr_seen = bool(request.headers.get(rbac.HDR_ROLES) or request.headers.get("X-Roles"))
        roles_hdr = rbac.get_current_roles()
        print(f"headers_seen(sample)={'yes' if hdr_seen else 'no'}")
        print(f"roles_with_sample_header={_fmt_roles(roles_hdr)}")

    if _truthy(os.getenv("ESTER_LAB_MODE", "0")):
        print("summary=LAB_MODE_ON (DEV fallback active by design)")
        return 0

    return 0 if strict_pass else 1


if __name__ == "__main__":
    rc = main()
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        os._exit(rc)
