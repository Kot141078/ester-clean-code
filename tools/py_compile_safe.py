# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import os
import py_compile
import sys
import tempfile
from pathlib import Path
from typing import Iterable, List

DEFAULT_ROOTS = ["modules", "routes", "security", "tools", "scripts"]
SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules"}


def _ensure_env() -> None:
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    if "PYTHONPYCACHEPREFIX" not in os.environ:
        os.environ["PYTHONPYCACHEPREFIX"] = str(Path(tempfile.gettempdir()) / "ester_pycache")
    Path(os.environ["PYTHONPYCACHEPREFIX"]).mkdir(parents=True, exist_ok=True)


def _compile_one(p: Path) -> None:
    target_root = Path(os.environ.get("PYTHONPYCACHEPREFIX", str(Path(tempfile.gettempdir()) / "ester_pycache"))).resolve()
    key = hashlib.sha256(str(p.resolve()).encode("utf-8")).hexdigest()
    cfile = (target_root / "safe_compile" / f"{key}.pyc").resolve()
    cfile.parent.mkdir(parents=True, exist_ok=True)
    py_compile.compile(str(p), cfile=str(cfile), doraise=True)


def _iter_python_files_from_roots(roots: Iterable[str]) -> List[Path]:
    out: List[Path] = []
    seen = set()
    for root in list(roots or []):
        rp = Path(str(root or "").strip())
        if not str(rp):
            continue
        if not rp.exists():
            continue
        if rp.is_file():
            if rp.suffix.lower() == ".py":
                key = str(rp.resolve()).lower()
                if key not in seen:
                    seen.add(key)
                    out.append(rp.resolve())
            continue
        for p in rp.rglob("*.py"):
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            key = str(p.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(p.resolve())
    out.sort(key=lambda x: str(x).lower())
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", nargs="*", default=None, help="Explicit .py files to compile.")
    ap.add_argument("--roots", nargs="*", default=None, help="Directories to scan for .py files.")
    args = ap.parse_args(argv)

    _ensure_env()

    paths: List[Path]
    if args.paths:
        paths = _iter_python_files_from_roots(args.paths)
    else:
        roots = list(args.roots or DEFAULT_ROOTS)
        paths = _iter_python_files_from_roots(roots)

    if not paths:
        print("PY_COMPILE_SAFE_FAIL")
        print("no_python_files_found")
        return 2

    failed: list[str] = []

    for p in paths:
        if not p.exists():
            failed.append(f"{p}:NOT_FOUND")
            continue
        try:
            _compile_one(p)
        except Exception as e:
            failed.append(f"{p}:{e}")

    if failed:
        print("PY_COMPILE_SAFE_FAIL")
        for x in failed:
            print(x)
        return 2

    print("PY_COMPILE_SAFE_OK")
    print(f"compiled={len(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
