#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VDESK text hygiene: scan/apply mojibake fixes with safe defaults.

Default mode is scan-only. Use --apply explicitly to write changes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = REPO_ROOT / "Virtual Desktop for Ester"
TEXT_EXTS = {
    ".txt",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".toml",
    ".py",
    ".ps1",
    ".sh",
    ".bat",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".css",
    ".html",
    ".xml",
    ".csv",
}
MAX_FILE_BYTES = 2 * 1024 * 1024

CYR_RE = re.compile(r"[A-Yaa-yaEe]")
LATIN_MOJIBAKE_RE = re.compile(r"(?:Ð.|Ñ.){2,}")
RS_PAIR_RE = re.compile(r"(?:[RS][A-Yaa-yaEeҐґЇїІіЄє]){2,}")
ODD_PAIR_RE = re.compile(r"[RS][ґ№їЅЎўЈђћџ]")
BAD_HINTS = ("Re", "R°", "S‚", "SЃ", "S‡", "SЂ", "SЏ", "Ð", "Ñ")


@dataclass
class LineFix:
    line_no: int
    old: str
    new: str
    method: str
    confidence: int


def _count_cyr(text: str) -> int:
    return len(CYR_RE.findall(text or ""))


def _marker_score(text: str) -> int:
    marks = "ÐÑÃÂ�RS"
    return sum((text or "").count(ch) for ch in marks)


def _printable_text(text: str) -> bool:
    return all((ch in "\n\r\t") or ch.isprintable() for ch in text)


def _suspicious(text: str) -> bool:
    if not text:
        return False
    if LATIN_MOJIBAKE_RE.search(text):
        return True
    if ODD_PAIR_RE.search(text):
        return True
    if "R" in text or "S" in text:
        if RS_PAIR_RE.search(text):
            return True
        if any(tok in text for tok in BAD_HINTS):
            return True
    return False


def _decode_cp1251_utf8(value: str) -> str | None:
    try:
        return value.encode("cp1251", errors="strict").decode("utf-8", errors="strict")
    except Exception:
        return None


def _decode_latin1_utf8(value: str) -> str | None:
    try:
        return value.encode("latin-1", errors="strict").decode("utf-8", errors="strict")
    except Exception:
        return None


def _score_candidate(original: str, candidate: str) -> int:
    if not candidate or candidate == original:
        return -1
    if "\ufffd" in candidate:
        return -1
    if not _printable_text(candidate):
        return -1

    base_mark = _marker_score(original)
    base_cyr = _count_cyr(original)
    cand_mark = _marker_score(candidate)
    cand_cyr = _count_cyr(candidate)

    mark_drop = base_mark - cand_mark
    cyr_gain = cand_cyr - base_cyr
    if mark_drop < 2:
        return -1
    if cyr_gain < 1:
        return -1

    # Higher is better; tuned for conservative apply.
    return (mark_drop * 3) + cyr_gain


def _pick_fix(line: str) -> LineFix | None:
    if not _suspicious(line):
        return None

    best: tuple[str, str, int] | None = None
    for method, candidate in (
        ("cp1251->utf8", _decode_cp1251_utf8(line)),
        ("latin1->utf8", _decode_latin1_utf8(line)),
    ):
        if candidate is None:
            continue
        score = _score_candidate(line, candidate)
        if score < 0:
            continue
        if best is None or score > best[2]:
            best = (candidate, method, score)

    if best is None:
        return None
    return LineFix(line_no=0, old=line, new=best[0], method=best[1], confidence=best[2])


def _iter_text_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_EXTS:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yield path


def _read_utf8(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            # UTF-8 with BOM fallback
            return path.read_text(encoding="utf-8-sig")
        except Exception:
            return None
    except Exception:
        return None


def _backup_path(path: Path) -> Path:
    return path.with_name(path.name + ".bak")


def _scan_file(path: Path) -> List[LineFix]:
    text = _read_utf8(path)
    if text is None:
        return []
    out: List[LineFix] = []
    for idx, line in enumerate(text.splitlines(keepends=True), start=1):
        fix = _pick_fix(line)
        if fix is None:
            continue
        fix.line_no = idx
        out.append(fix)
    return out


def _apply_file(path: Path, fixes: Sequence[LineFix], min_confidence: int) -> int:
    if not fixes:
        return 0
    text = _read_utf8(path)
    if text is None:
        return 0

    lines = text.splitlines(keepends=True)
    changed = 0
    for fix in fixes:
        if fix.confidence < min_confidence:
            continue
        i = fix.line_no - 1
        if i < 0 or i >= len(lines):
            continue
        if lines[i] != fix.old:
            continue
        lines[i] = fix.new
        changed += 1

    if changed == 0:
        return 0

    backup = _backup_path(path)
    if not backup.exists():
        backup.write_bytes(path.read_bytes())
    path.write_text("".join(lines), encoding="utf-8")
    return changed


def _to_rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="VDESK mojibake hygiene tool (scan/apply).")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="Scan root (default: VDESK directory).")
    ap.add_argument("--scan", action="store_true", help="Report only (default if no mode).")
    ap.add_argument("--apply", action="store_true", help="Apply high-confidence fixes with .bak backups.")
    ap.add_argument(
        "--min-confidence",
        type=int,
        default=8,
        help="Minimum confidence score for apply (default: 8).",
    )
    ap.add_argument("--max-report", type=int, default=200, help="Max findings to print.")
    return ap.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)

    if args.scan and args.apply:
        print("error: choose either --scan or --apply", file=sys.stderr)
        return 2

    mode = "apply" if args.apply else "scan"
    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        print(json.dumps({"ok": False, "mode": mode, "error": f"root_not_found:{root}"}))
        return 2

    findings: List[dict] = []
    files_scanned = 0
    files_with_issues = 0
    files_changed = 0
    lines_changed = 0

    for path in _iter_text_files(root):
        files_scanned += 1
        fixes = _scan_file(path)
        if not fixes:
            continue
        files_with_issues += 1
        if mode == "apply":
            changed = _apply_file(path, fixes, min_confidence=int(args.min_confidence))
            if changed > 0:
                files_changed += 1
                lines_changed += changed

        for fix in fixes:
            findings.append(
                {
                    "path": _to_rel(path),
                    "line": fix.line_no,
                    "method": fix.method,
                    "confidence": fix.confidence,
                    "before": fix.old.rstrip("\n")[:180],
                    "after": fix.new.rstrip("\n")[:180],
                }
            )

    summary = {
        "ok": True,
        "mode": mode,
        "root": _to_rel(root),
        "files_scanned": files_scanned,
        "files_with_issues": files_with_issues,
        "findings": len(findings),
        "files_changed": files_changed,
        "lines_changed": lines_changed,
        "safe_apply": True,
    }
    print(json.dumps(summary, ensure_ascii=False))

    limit = max(0, int(args.max_report))
    for item in findings[:limit]:
        print(
            f"{item['path']}:{item['line']} "
            f"[{item['method']} conf={item['confidence']}] {item['before']}"
        )
    if len(findings) > limit:
        print(f"... truncated: {len(findings) - limit} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

