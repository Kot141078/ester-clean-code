# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.diagnostics.route_lint import lint_routes


def _print_failures(failures: List[Dict[str, Any]]) -> None:
    for f in failures:
        print(f'{f.get("file")}:{f.get("line")} :: {f.get("func")} :: {f.get("reason")}')


def _print_runtime_defs(runtime_status: Dict[str, Any]) -> None:
    defs = runtime_status.get("defs") or []
    for d in defs:
        print(
            f'{d.get("file")}:{d.get("line")} :: {d.get("func")} :: '
            f'RUNTIME_STATUS_DECORATOR={d.get("decorator")}'
        )


def _print_parse_errors(parse_errors: List[Dict[str, Any]]) -> None:
    for e in parse_errors:
        print(f'{e.get("file")}:{e.get("line")} :: parse_error :: {e.get("message")}')


def _print_warnings(warnings: List[str]) -> None:
    for w in warnings:
        print(f"WARNING: {w}")


def main(argv: List[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    active_only = "--all" not in args

    try:
        result = lint_routes(active_only=active_only)
    except Exception as exc:
        print(f"route_return_lint: INTERNAL_ERROR {exc}")
        return 3

    parse_errors = list(result.get("parse_errors") or [])
    warnings = list(result.get("warnings") or [])
    if parse_errors:
        print("route_return_lint: SYNTAX_PARSE_FAILURES")
        _print_parse_errors(parse_errors)
        _print_warnings(warnings)
        return 3

    fail_count = int(result.get("fail_count", 0))
    checked = int(result.get("checked_handlers", 0))
    files = int(result.get("checked_files", 0))
    runtime_status = dict(result.get("runtime_status") or {})
    runtime_ok = bool(runtime_status.get("ok", False))

    if fail_count > 0 or not runtime_ok:
        print(
            "route_return_lint: FAIL_COUNT=%d checked=%d files=%d runtime_status_count=%d"
            % (fail_count, checked, files, int(runtime_status.get("count", 0)))
        )
        _print_failures(list(result.get("failures") or []))
        if not runtime_ok:
            print(
                "route_return_lint: runtime status path '%s' count=%d (expected 1)"
                % (runtime_status.get("path"), int(runtime_status.get("count", 0)))
            )
            _print_runtime_defs(runtime_status)
        _print_warnings(warnings)
        return 2

    print(f"route_return_lint: OK (checked={checked} handlers, files={files})")
    _print_warnings(warnings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
