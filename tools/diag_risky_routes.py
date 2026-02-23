#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List


DEFAULT_PREFIXES = [
    "/sync",
    "/sync/kbd",
    "/p2p/bloom",
    "/p2p/memory",
    "/survival",
]


def _fetch_json(url: str, timeout_sec: float) -> Dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("diag_response_not_object")
    return payload


def _extract_rules(routes_obj: Any) -> List[str]:
    rules: List[str] = []
    if isinstance(routes_obj, list):
        for item in routes_obj:
            if isinstance(item, str):
                rule = item.strip()
            elif isinstance(item, dict):
                rule = str(item.get("rule") or "").strip()
            else:
                rule = ""
            if rule:
                rules.append(rule)
    return rules


def _match_prefixes(rules: List[str], prefixes: List[str]) -> List[str]:
    found: List[str] = []
    for rule in rules:
        for prefix in prefixes:
            if rule.startswith(prefix):
                if rule not in found:
                    found.append(rule)
                break
    return found


def _parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Check risky routes exposure via /_diag/routes.")
    p.add_argument("--base", default="http://127.0.0.1:8090", help="Base URL, default: http://127.0.0.1:8090")
    p.add_argument(
        "--expect",
        choices=["disabled", "enabled"],
        default="disabled",
        help="Expected risky routes state (default: disabled).",
    )
    p.add_argument("--timeout", type=float, default=3.0, help="HTTP timeout in seconds (default: 3.0)")
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = _parse_args(argv)
    base = str(args.base or "").rstrip("/")
    diag_url = base + "/_diag/routes"

    try:
        payload = _fetch_json(diag_url, timeout_sec=float(args.timeout))
        rules = _extract_rules(payload.get("routes"))
        risky_found = _match_prefixes(rules, DEFAULT_PREFIXES)
    except urllib.error.URLError as e:
        out = {
            "ok": False,
            "error": f"url_error:{e}",
            "base": base,
            "diag_url": diag_url,
            "expect": args.expect,
        }
        print(json.dumps(out, ensure_ascii=False))
        return 2
    except Exception as e:
        out = {
            "ok": False,
            "error": f"{type(e).__name__}:{e}",
            "base": base,
            "diag_url": diag_url,
            "expect": args.expect,
        }
        print(json.dumps(out, ensure_ascii=False))
        return 2

    if args.expect == "disabled":
        ok = len(risky_found) == 0
    else:
        ok = len(risky_found) > 0

    out = {
        "ok": bool(ok),
        "expect": args.expect,
        "base": base,
        "diag_url": diag_url,
        "risky_prefixes": list(DEFAULT_PREFIXES),
        "risky_routes_found": list(risky_found),
        "routes_total": len(rules),
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

