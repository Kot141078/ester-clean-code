# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Sequence

TARGET_DIRS = ("templates", "static")
TARGET_EXTS = {".html", ".js", ".mjs", ".ts", ".tsx", ".vue"}

UNSAFE_SET_RE = re.compile(
    r"(?i)\b(?:headers\s*\.\s*set|setRequestHeader)\s*\(\s*['\"]X-(?:Subject|User)['\"]"
)
UNSAFE_OBJECT_RE = re.compile(r"(?i)['\"]X-(?:Subject|User)['\"]\s*:")
SAFE_INLINE_MARKERS = ("setHeaderUtf8Safe", "X-Subject-B64", "X-User-B64", "__EsterHeaderSafe")


def _iter_files(root: Path):
    for top in TARGET_DIRS:
        base = root / top
        if not base.exists() or not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() in TARGET_EXTS:
                yield path


def run_scan(root: Path) -> Dict[str, object]:
    findings: List[Dict[str, object]] = []
    scanned = 0

    for path in _iter_files(root):
        scanned += 1
        rel = path.resolve().relative_to(root.resolve()).as_posix()
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue

        for lineno, line in enumerate(lines, start=1):
            text = str(line or "")
            if any(marker in text for marker in SAFE_INLINE_MARKERS):
                continue

            if UNSAFE_SET_RE.search(text):
                findings.append(
                    {
                        "path": rel,
                        "line": lineno,
                        "kind": "unsafe_set_call",
                        "snippet": text.strip()[:240],
                    }
                )
                continue

            if UNSAFE_OBJECT_RE.search(text):
                findings.append(
                    {
                        "path": rel,
                        "line": lineno,
                        "kind": "unsafe_header_literal",
                        "snippet": text.strip()[:240],
                    }
                )

    ok = len(findings) == 0
    return {
        "ok": ok,
        "scanned_files": scanned,
        "found_unsafe_sets": findings,
        "exit_code": 0 if ok else 2,
    }


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Static scan for unsafe Unicode-prone X-Subject/X-User header usage.")
    parser.add_argument("--root", default=".", help="Project root path.")
    parser.add_argument("--json-out", default="", help="Optional JSON output file.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    root = Path(args.root).resolve()
    payload = run_scan(root)

    if str(args.json_out or "").strip():
        out = Path(args.json_out).resolve()
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return int(payload["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
