# -*- coding: utf-8 -*-
"""
UI hardening smoke (fixed targets only, localhost only).

Explicit bridge (Ashby): fixed smoke targets constrain UI variety with measurable checks.
Hidden bridge #1 (Enderton): mapping (rule, method) -> status becomes total for critical endpoints.
Hidden bridge #2 (Guyton/Hall): fail-closed pages surface "not ready" status instead of crashing.

Earth paragraph: this is the electrical tester for the panel's critical breakers.
"""
from __future__ import annotations

import argparse
import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPRedirectHandler, Request, build_opener

SMOKE_PATHS = [
    "/admin",
    "/admin/portal",
    "/admin/identity",
    "/admin/settings",
    "/admin/keys/vault",
    "/admin/keys/",
    "/ops/p2p",
]


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _http_get(url: str, timeout_sec: float) -> Dict[str, Any]:
    opener = build_opener(HTTPRedirectHandler())
    req = Request(url=url, method="GET")
    try:
        with opener.open(req, timeout=max(0.1, timeout_sec)) as resp:
            status = int(getattr(resp, "status", 0) or resp.getcode() or 0)
            final = str(resp.geturl() or url)
            return {"status": status, "final_url": final, "error": None}
    except HTTPError as exc:
        status = int(getattr(exc, "code", 0) or 0)
        final = str(exc.geturl() or url)
        return {"status": status, "final_url": final, "error": None}
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, socket.timeout):
            err = "timeout"
        else:
            err = str(reason)
        return {"status": "ERR", "final_url": url, "error": err}
    except Exception as exc:
        return {"status": "ERR", "final_url": url, "error": str(exc)}


def run_smoke(base: str, timeout_sec: float) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for path in SMOKE_PATHS:
        url = urljoin(base.rstrip("/") + "/", path.lstrip("/"))
        res = _http_get(url, timeout_sec)
        final_url = str(res.get("final_url") or url)
        rows.append(
            {
                "path": path,
                "url": url,
                "status": res.get("status"),
                "final_url": final_url,
                "redirected": final_url != url,
                "error": res.get("error"),
            }
        )

    has_500 = any(int(row["status"]) == 500 for row in rows if isinstance(row.get("status"), int))
    exit_code = 2 if has_500 else 0
    return {
        "generated_at": _iso_now(),
        "base": base,
        "rows": rows,
        "ok": not has_500,
        "exit_code": exit_code,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke critical UI endpoints and fail on HTTP 500.")
    parser.add_argument("--base", default="http://127.0.0.1:8090", help="Base URL.")
    parser.add_argument("--timeout", type=float, default=4.0, help="Timeout in seconds.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Compatibility flag: emit JSON to stdout (enabled by default).",
    )
    parser.add_argument(
        "--json-out",
        default="ui_smoke_targets.json",
        help="Optional output JSON file path relative to project root.",
    )
    args = parser.parse_args(argv)

    payload = run_smoke(base=args.base.strip().rstrip("/"), timeout_sec=float(args.timeout))
    out_path = Path(args.json_out).resolve()
    try:
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        pass

    # Contract: print a single-line JSON to stdout.
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return int(payload["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
