# -*- coding: utf-8 -*-
from __future__ import annotations

import builtins as _builtins
import importlib
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


def _safe_print(*args, **kwargs):
    try:
        _builtins.print(*args, **kwargs)
    except OSError:
        pass


print = _safe_print  # type: ignore


READ_ONLY = str(os.getenv("ESTER_HEALTHCHECK_READONLY", "1")).strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}


def _env_enabled(name: str, default: str = "1") -> bool:
    value = str(os.getenv(name, default)).strip().lower()
    return value not in {"0", "false", "no", "off"}


def _uniq(items: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


class HealthCheck:
    def __init__(self, core=None):
        self.core = core
        self.critical_registry = [
            "config",
            "session_guardian",
            "empathy_module",
            "vector_store",
            "rag",
            "knowledge_graph",
        ]
        self.perimeter_registry = [
            "modules.runtime.status_iter18",
            "modules.dreams.dream_engine",
            "modules.proactivity.initiative_engine",
            "modules.memory.memory_bus",
            "modules.security.admin_guard",
            "routes.dreams_routes",
            "routes.initiative_routes",
            "routes.initiatives_routes",
            "modules.dreams_engine",
        ]
        self.full_registry: List[str] = []

    def _discover_modules(self) -> None:
        self.full_registry = _uniq(self.critical_registry + self.perimeter_registry)

    def _check_iter18_runtime_status(self) -> Tuple[bool, Dict[str, Any]]:
        try:
            from modules.runtime.status_iter18 import runtime_status  # type: ignore

            st = runtime_status()
            return bool(st.get("ok", True)), {
                "ok": bool(st.get("ok", True)),
                "memory_ready": st.get("memory_ready"),
                "degraded_memory_mode": st.get("degraded_memory_mode"),
                "background": st.get("background"),
            }
        except Exception as exc:
            return False, {"ok": False, "error": str(exc)}

    def _run_module_import_checks(self) -> Dict[str, Any]:
        self._discover_modules()

        per_module: Dict[str, Dict[str, Any]] = {}
        failed_modules: List[str] = []
        passed = 0
        failed = 0

        os.environ.setdefault("ESTER_ALLOW_SECRET_WRITE", "0")
        os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

        for mod_name in self.full_registry:
            try:
                importlib.import_module(mod_name)
                per_module[mod_name] = {"ok": True}
                passed += 1
            except Exception as exc:
                per_module[mod_name] = {"ok": False, "error": str(exc).split("\n", 1)[0][:200]}
                failed_modules.append(mod_name)
                failed += 1

        return {
            "total": len(self.full_registry),
            "passed": passed,
            "failed": failed,
            "failed_modules": failed_modules,
            "per_module": per_module,
        }

    @staticmethod
    def _route_lint_stub(ok: bool, skipped: bool, error: str | None = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "ok": ok,
            "checked_files": 0,
            "checked_handlers": 0,
            "fail_count": 0,
            "failures": [],
            "runtime_status": {
                "path": "/debug/runtime/status",
                "defs": [],
                "count": 0,
                "ok": False,
            },
            "parse_errors": [],
            "warnings": [],
        }
        if skipped:
            payload["skipped"] = True
        if error:
            payload["error"] = error
        return payload

    def run_all_checks(self) -> Dict[str, Any]:
        modules_status = self._run_module_import_checks()
        iter18_ok, iter18_payload = self._check_iter18_runtime_status()

        issues: List[str] = []
        issues.extend(f"module_import_failed:{m}" for m in modules_status.get("failed_modules", []))
        if not iter18_ok:
            issues.append("iter18_runtime_status_failed")

        route_lint_enabled = _env_enabled("ESTER_HEALTH_ROUTE_LINT", "1")
        rollback = False
        route_lint_exception = False

        if route_lint_enabled:
            try:
                from modules.diagnostics.route_lint import lint_routes

                route_lint = lint_routes(active_only=True)
            except Exception as exc:
                route_lint_exception = True
                rollback = True
                issues.append("route_lint_exception")
                route_lint = self._route_lint_stub(ok=False, skipped=True, error=str(exc))
        else:
            route_lint = self._route_lint_stub(ok=True, skipped=True)

        runtime_status = dict(route_lint.get("runtime_status") or {})
        runtime_defs = list(runtime_status.get("defs") or [])
        runtime_count = int(runtime_status.get("count", 0))
        route_lint_fail_count = int(route_lint.get("fail_count", 0))
        route_lint_parse_errors = list(route_lint.get("parse_errors") or [])

        if route_lint_enabled:
            if route_lint_fail_count > 0:
                issues.append("route_lint_failures")
            if route_lint_parse_errors:
                issues.append("route_lint_parse_errors")
            if runtime_count != 1:
                issues.append("runtime_status_not_unique")

        modules_ok = int(modules_status.get("failed", 0)) == 0
        route_checks_ok = True
        if route_lint_enabled:
            route_checks_ok = (
                (not route_lint_exception)
                and route_lint_fail_count == 0
                and (len(route_lint_parse_errors) == 0)
                and runtime_count == 1
            )

        overall_ok = modules_ok and iter18_ok and route_checks_ok

        runtime_status_unique = bool(runtime_count == 1) if route_lint_enabled else True

        result: Dict[str, Any] = {
            "ok": overall_ok,
            "read_only": READ_ONLY,
            "slot_b_enabled": route_lint_enabled,
            "rollback": rollback,
            "modules": modules_status,
            "iter18_runtime_status": iter18_payload,
            "route_lint": route_lint,
            "runtime_status_unique": runtime_status_unique,
            "runtime_status_defs": {
                "count": runtime_count,
                "defs": runtime_defs,
            },
            "issues": issues,
            "issues_total": len(issues),
        }

        report_record = {
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "ok": bool(result["ok"]),
            "issues_total": int(result["issues_total"]),
            "route_lint_ok": bool(route_lint.get("ok", False)),
            "route_lint_fail_count": route_lint_fail_count,
            "runtime_status_count": runtime_count,
            "rollback": rollback,
            "summary": {
                "modules_failed": int(modules_status.get("failed", 0)),
                "iter18_ok": bool(iter18_ok),
                "slot_b_enabled": bool(route_lint_enabled),
            },
        }

        try:
            from modules.diagnostics.health_report import append_record

            report_path = append_record(report_record)
            if report_path:
                result["report_path"] = report_path
        except Exception as exc:
            result["report_error"] = str(exc).split("\n", 1)[0][:240]

        return result


def main() -> int:
    if os.getcwd() not in sys.path:
        sys.path.append(os.getcwd())

    try:
        result = HealthCheck().run_all_checks()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "health_check_internal_error",
                    "message": str(exc).split("\n", 1)[0][:240],
                },
                ensure_ascii=False,
            )
        )
        return 2

    print(json.dumps(result, ensure_ascii=False))
    return 0 if bool(result.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
