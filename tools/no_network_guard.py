# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

DEFAULT_ROOTS = ["modules", "routes", "security", "tools", "scripts", "run_ester_fixed.py"]
DEFAULT_ALLOWLIST = "config/no_network_allowlist.json"

RULES: List[Tuple[str, re.Pattern[str]]] = [
    ("import.requests", re.compile(r"^\s*(?:from\s+requests\b|import\s+requests\b)")),
    ("import.httpx", re.compile(r"^\s*(?:from\s+httpx\b|import\s+httpx\b)")),
    ("import.aiohttp", re.compile(r"^\s*(?:from\s+aiohttp\b|import\s+aiohttp\b)")),
    ("import.websockets", re.compile(r"^\s*(?:from\s+websockets\b|import\s+websockets\b)")),
    ("import.urllib.request", re.compile(r"\burllib\.request\b")),
    ("socket.create_connection", re.compile(r"\bsocket\.create_connection\s*\(")),
]


def _iter_py_files(roots: Iterable[str]) -> Iterable[Path]:
    seen: set[str] = set()
    for root in roots:
        p = Path(root)
        if not p.exists():
            continue
        if p.is_file():
            if p.suffix == ".py":
                key = str(p.resolve()).lower()
                if key not in seen:
                    seen.add(key)
                    yield p
            continue
        for child in p.rglob("*.py"):
            if any(part in {".git", ".venv", "venv", "__pycache__"} for part in child.parts):
                continue
            key = str(child.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            yield child


def _scan_file(path: Path) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return findings
    rel = str(path).replace("\\", "/")
    for idx, line in enumerate(lines, start=1):
        for rule_id, rx in RULES:
            if rx.search(line):
                findings.append(
                    {
                        "path": rel,
                        "line": idx,
                        "rule": rule_id,
                        "snippet": line.strip()[:220],
                    }
                )
    return findings


def _load_allowlist(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "pattern": str(row.get("pattern") or "").replace("\\", "/"),
                "why": str(row.get("why") or ""),
                "expires_ts": int(row.get("expires_ts") or 0),
            }
        )
    return out


def _allowed(finding: Dict[str, Any], allowlist: List[Dict[str, Any]], now_ts: int) -> bool:
    fpath = str(finding.get("path") or "").replace("\\", "/")
    for row in allowlist:
        patt = str(row.get("pattern") or "").replace("\\", "/")
        if not patt:
            continue
        exp = int(row.get("expires_ts") or 0)
        if exp > 0 and now_ts > exp:
            continue
        if fnmatch.fnmatch(fpath, patt):
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Static no-network guard scanner.")
    ap.add_argument("--strict", action="store_true", help="Fail when unallowlisted findings exist.")
    ap.add_argument("--quiet", action="store_true", help="Print one-line summary only.")
    ap.add_argument("--allowlist", default=DEFAULT_ALLOWLIST, help="Path to allowlist JSON.")
    ap.add_argument("--roots", nargs="*", default=DEFAULT_ROOTS, help="Roots/files to scan.")
    args = ap.parse_args()

    allowlist = _load_allowlist(Path(args.allowlist))
    findings: List[Dict[str, Any]] = []
    for file_path in _iter_py_files(args.roots):
        findings.extend(_scan_file(file_path))

    now_ts = int(time.time())
    violations = [f for f in findings if not _allowed(f, allowlist, now_ts)]
    allowed = [f for f in findings if _allowed(f, allowlist, now_ts)]

    if args.quiet:
        print(
            "NO_NETWORK_GUARD findings={f} violations={v} allowlisted={a} strict={s}".format(
                f=len(findings),
                v=len(violations),
                a=len(allowed),
                s=int(bool(args.strict)),
            )
        )
    else:
        print(
            json.dumps(
                {
                    "ok": (not args.strict) or (len(violations) == 0),
                    "strict": bool(args.strict),
                    "allowlist_path": str(args.allowlist),
                    "findings_total": len(findings),
                    "violations_total": len(violations),
                    "allowlisted_total": len(allowed),
                    "violations": violations[:200],
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    if bool(args.strict) and violations:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
