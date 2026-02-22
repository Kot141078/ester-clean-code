# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[2]
ROUTES_DIR = ROOT / "routes"

IGNORE_DIRS = {"__pycache__", "__disabled__", "_disabled"}
IGNORE_SUFFIXES = (".disabled.py", "_legacy.py")
HTTP_DECORATORS = {
    "route",
    "get",
    "post",
    "put",
    "delete",
    "patch",
    "head",
    "options",
    "websocket",
}
RUNTIME_STATUS_PATH = "/debug/runtime/status"


def _const_str(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_ignored_path(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if any(name in parts for name in IGNORE_DIRS):
        return True
    low_name = path.name.lower()
    if any(low_name.endswith(sfx) for sfx in IGNORE_SUFFIXES):
        return True
    return False


def _iter_all_route_files() -> Iterable[Path]:
    if not ROUTES_DIR.exists():
        return
    for path in ROUTES_DIR.rglob("*.py"):
        if _is_ignored_path(path):
            continue
        yield path


def _module_to_file(module_name: str) -> Optional[Path]:
    if not module_name.startswith("routes."):
        return None
    return ROOT / (module_name.replace(".", "/") + ".py")


def _iter_active_route_files() -> Tuple[List[Path], List[str]]:
    from routes.route_registry import get_route_modules

    files: List[Path] = []
    warnings: List[str] = []
    seen: set[str] = set()

    for mod in get_route_modules(strict=False):
        path = _module_to_file(mod)
        if path is None:
            warnings.append(f"skip_non_routes_module:{mod}")
            continue
        if _is_ignored_path(path):
            warnings.append(f"skip_ignored_path:{path.as_posix()}")
            continue
        if not path.exists():
            warnings.append(f"skip_missing_file:{mod}->{path.as_posix()}")
            continue
        key = str(path.resolve()).casefold()
        if key in seen:
            continue
        seen.add(key)
        files.append(path)

    return files, warnings


def _route_decorator_meta(dec: ast.AST) -> Optional[Tuple[str, str]]:
    if not isinstance(dec, ast.Call):
        return None
    fn = dec.func
    if not isinstance(fn, ast.Attribute):
        return None
    attr = (fn.attr or "").strip()
    if attr not in HTTP_DECORATORS:
        return None

    for arg in dec.args:
        s = _const_str(arg)
        if isinstance(s, str) and s.strip().startswith("/"):
            return attr, s.strip()
    for kw in dec.keywords:
        s = _const_str(kw.value)
        if isinstance(s, str) and s.strip().startswith("/"):
            return attr, s.strip()
    return None


def _is_terminating_call(stmt: ast.stmt) -> bool:
    if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
        return False
    fn = stmt.value.func
    if isinstance(fn, ast.Name) and fn.id in {"abort", "exit"}:
        return True
    if isinstance(fn, ast.Attribute):
        if isinstance(fn.value, ast.Name) and fn.value.id == "sys" and fn.attr == "exit":
            return True
        if fn.attr == "abort":
            return True
    return False


def _match_has_wildcard(match_node: ast.Match) -> bool:
    for case in match_node.cases:
        if isinstance(case.pattern, ast.MatchAs) and case.pattern.name is None:
            return True
    return False


def _check_block(stmts: Sequence[ast.stmt]) -> Tuple[bool, bool]:
    """
    Returns:
      may_fall_through: at least one path can reach end of block
      has_bare_return: any `return` without value
    """
    may_fall_through = True
    has_bare_return = False

    for stmt in stmts:
        if not may_fall_through:
            break
        stmt_fall, stmt_bare = _check_stmt(stmt)
        has_bare_return = has_bare_return or stmt_bare
        may_fall_through = stmt_fall

    return may_fall_through, has_bare_return


def _check_stmt(stmt: ast.stmt) -> Tuple[bool, bool]:
    if isinstance(stmt, ast.Return):
        return False, (stmt.value is None)
    if isinstance(stmt, ast.Raise):
        return False, False
    if _is_terminating_call(stmt):
        return False, False

    if isinstance(stmt, ast.With):
        return _check_block(stmt.body)
    if isinstance(stmt, ast.AsyncWith):
        return _check_block(stmt.body)

    if isinstance(stmt, ast.If):
        body_fall, body_bare = _check_block(stmt.body)
        if not stmt.orelse:
            return True, body_bare
        else_fall, else_bare = _check_block(stmt.orelse)
        return (body_fall or else_fall), (body_bare or else_bare)

    if isinstance(stmt, ast.Try):
        body_fall, body_bare = _check_block(stmt.body)
        handlers_fall: List[bool] = []
        handlers_bare = False
        for handler in stmt.handlers:
            hf, hb = _check_block(handler.body)
            handlers_fall.append(hf)
            handlers_bare = handlers_bare or hb

        if stmt.orelse:
            else_fall, else_bare = _check_block(stmt.orelse)
        else:
            else_fall, else_bare = True, False

        non_exc_fall = body_fall or (not body_fall and else_fall)
        exc_fall = any(handlers_fall) if handlers_fall else False

        finally_bare = False
        if stmt.finalbody:
            finally_fall, finally_bare = _check_block(stmt.finalbody)
            if not finally_fall:
                return False, (body_bare or handlers_bare or else_bare or finally_bare)

        return (non_exc_fall or exc_fall), (body_bare or handlers_bare or else_bare or finally_bare)

    if isinstance(stmt, ast.Match):
        has_wild = _match_has_wildcard(stmt)
        case_fall = False
        case_bare = False
        for case in stmt.cases:
            cf, cb = _check_block(case.body)
            case_fall = case_fall or cf
            case_bare = case_bare or cb
        if not has_wild:
            return True, case_bare
        return case_fall, case_bare

    if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
        body_fall, body_bare = _check_block(stmt.body)
        if stmt.orelse:
            _else_fall, else_bare = _check_block(stmt.orelse)
        else:
            else_bare = False
        # Loops are conservatively treated as potentially falling through.
        return True, (body_bare or else_bare)

    return True, False


def _lint_file(path: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, List[Dict[str, Any]]]:
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    text = path.read_text(encoding="utf-8-sig", errors="replace")

    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return (
            [],
            [{"file": rel, "line": int(exc.lineno or 0), "message": str(exc.msg)}],
            0,
            [],
        )

    failures: List[Dict[str, Any]] = []
    parse_errors: List[Dict[str, Any]] = []
    runtime_defs: List[Dict[str, Any]] = []
    checked_handlers = 0

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        decorators: List[Tuple[str, str]] = []
        for dec in node.decorator_list:
            meta = _route_decorator_meta(dec)
            if meta is None:
                continue
            decorators.append(meta)

        if not decorators:
            continue

        checked_handlers += 1
        for dec_attr, route_path in decorators:
            if route_path == RUNTIME_STATUS_PATH:
                runtime_defs.append(
                    {
                        "file": rel,
                        "line": int(getattr(node, "lineno", 0)),
                        "func": node.name,
                        "decorator": dec_attr,
                    }
                )

        may_fall_through, has_bare_return = _check_block(node.body)
        if may_fall_through:
            failures.append(
                {
                    "file": rel,
                    "line": int(getattr(node, "lineno", 0)),
                    "func": node.name,
                    "reason": "may_fall_through_without_return",
                }
            )
        if has_bare_return:
            failures.append(
                {
                    "file": rel,
                    "line": int(getattr(node, "lineno", 0)),
                    "func": node.name,
                    "reason": "has_bare_return",
                }
            )

    return failures, parse_errors, checked_handlers, runtime_defs


def lint_routes(active_only: bool = True) -> Dict[str, Any]:
    warnings: List[str] = []
    parse_errors: List[Dict[str, Any]] = []

    if active_only:
        files, active_warnings = _iter_active_route_files()
        warnings.extend(active_warnings)
    else:
        files = list(_iter_all_route_files())

    failures: List[Dict[str, Any]] = []
    runtime_defs: List[Dict[str, Any]] = []
    checked_handlers = 0

    for path in files:
        ff, pe, checked, rd = _lint_file(path)
        failures.extend(ff)
        parse_errors.extend(pe)
        checked_handlers += checked
        runtime_defs.extend(rd)

    failures.sort(key=lambda x: (x["file"], int(x["line"]), x["func"], x["reason"]))
    runtime_defs.sort(key=lambda x: (x["file"], int(x["line"]), x["func"], x["decorator"]))
    parse_errors.sort(key=lambda x: (x["file"], int(x["line"])))

    runtime_status = {
        "path": RUNTIME_STATUS_PATH,
        "defs": runtime_defs,
        "count": len(runtime_defs),
        "ok": len(runtime_defs) == 1,
    }
    fail_count = len(failures)
    ok = (fail_count == 0) and runtime_status["ok"] and (len(parse_errors) == 0)

    return {
        "ok": ok,
        "checked_files": len(files),
        "checked_handlers": checked_handlers,
        "fail_count": fail_count,
        "failures": failures,
        "runtime_status": runtime_status,
        "parse_errors": parse_errors,
        "warnings": warnings,
        "active_only": bool(active_only),
    }
