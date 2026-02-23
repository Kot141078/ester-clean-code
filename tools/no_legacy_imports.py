#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail if project code imports legacy _patch3 package."""

from __future__ import annotations

import argparse
import ast
import fnmatch
from pathlib import Path
from typing import Iterable, List


ROOT = Path(__file__).resolve().parents[1]
IGNORE_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "_patch3",
    "node_modules",
    "tools/_rollback",
    "venv",
}
DEFAULT_WHITELIST = {
    "tools/no_legacy_imports.py",
}


def _iter_python_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        parts = set(rel.split("/"))
        if any(token in parts for token in IGNORE_DIRS):
            continue
        if rel.startswith("tools/_rollback/"):
            continue
        yield path


def _match_any(path: str, patterns: Iterable[str]) -> bool:
    for pattern in patterns:
        p = (pattern or "").strip().replace("\\", "/")
        if not p:
            continue
        if fnmatch.fnmatch(path, p):
            return True
    return False


def _iter_legacy_imports(tree: ast.AST) -> Iterable[tuple[int, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name or ""
                if name == "_patch3" or name.startswith("_patch3."):
                    yield int(getattr(node, "lineno", 0) or 0), f"import {name}"
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "_patch3" or module.startswith("_patch3."):
                yield int(getattr(node, "lineno", 0) or 0), f"from {module} import ..."


def run(root: Path, whitelist: List[str]) -> int:
    findings: List[tuple[str, int, str]] = []
    parse_errors: List[tuple[str, str]] = []
    scanned = 0

    for path in _iter_python_files(root):
        scanned += 1
        rel = path.relative_to(root).as_posix()
        if _match_any(rel, whitelist):
            continue
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            tree = ast.parse(text, filename=rel)
        except SyntaxError as exc:
            parse_errors.append((rel, f"{exc.msg} @ line {int(exc.lineno or 0)}"))
            continue
        for lineno, stmt in _iter_legacy_imports(tree):
            findings.append((rel, lineno, stmt))

    print(f"checked_files={scanned}")
    if parse_errors:
        print(f"parse_warnings={len(parse_errors)}")
        for rel, msg in parse_errors:
            print(f"WARN {rel}: {msg}")

    if findings:
        print(f"legacy_imports_found={len(findings)}")
        for rel, lineno, stmt in findings:
            print(f"FAIL {rel}:{lineno} -> {stmt}")
        return 1

    print("legacy_imports_found=0")
    print("OK: no imports of _patch3 detected.")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect imports of legacy _patch3 package.")
    parser.add_argument("--root", default=str(ROOT), help="Project root (default: repo root).")
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        help="Whitelist glob pattern (repeatable), e.g. tests/*",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = Path(args.root).resolve()
    whitelist = sorted(set(DEFAULT_WHITELIST | set(args.allow or [])))
    return run(root=root, whitelist=whitelist)


if __name__ == "__main__":
    raise SystemExit(main())
