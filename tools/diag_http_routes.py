# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple


def _request(
    method: str,
    url: str,
    *,
    headers: Dict[str, str],
    body: Dict[str, Any] | None = None,
    timeout: float = 5.0,
) -> Tuple[int, Dict[str, Any]]:
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method.upper())
    req.add_header("Accept", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = int(resp.getcode() or 0)
            raw = resp.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"ok": False, "error": "non_json_response", "raw": raw[:500]}
        return code, payload
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"ok": False, "error": raw[:500]}
        return int(e.code or 0), payload
    except Exception as e:
        return 0, {"ok": False, "error": str(e)}


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8090")
    ap.add_argument("--timeout", type=float, default=5.0)
    args = ap.parse_args(argv)

    base = args.base.rstrip("/")
    headers = {"X-User-Roles": "admin"}
    checks = [
        ("GET", "/debug/runtime/status", None),
        ("GET", "/debug/dreams/status", None),
        ("GET", "/debug/initiatives/status", None),
    ]

    results = []
    failed = 0
    for method, path, body in checks:
        code, payload = _request(
            method,
            f"{base}{path}",
            headers=headers,
            body=body,
            timeout=args.timeout,
        )
        ok = bool(code and code < 400 and isinstance(payload, dict) and payload.get("ok") is not False)
        if not ok:
            failed += 1
        results.append({"method": method, "path": path, "code": code, "ok": ok, "payload": payload})

    out = {"ok": failed == 0, "failed": failed, "results": results}
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
