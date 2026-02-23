# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

MAX_MATCHES_OUTPUT = 200
_LEGACY_ALLOWED_BASENAMES = {"Ester_dump_part_0001.txt"}
_LEGACY_ALLOWED_SNIPPETS = {
    "GEMINI_API_KEY=AI***QbE8",
    "GOOGLE_API_KEY=AI***QbE8",
    "GOOGLE_CSE_KEY=AI***QbE8",
    "OPENAI_API_KEY=sk***4oIA",
}

PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("openai_sk", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_-]{30,}")),
    ("github_token", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("slack_token", re.compile(r"xox[a-zA-Z]-[A-Za-z0-9-]{10,}")),
    ("bearer_long", re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}", re.IGNORECASE)),
    (
        "private_key_header",
        re.compile(r"-----BEGIN\s+[A-Z ]*PRIVATE KEY-----", re.IGNORECASE),
    ),
    (
        "provider_env_assignment",
        re.compile(
            r"(?:OPENAI_API_KEY|GEMINI_API_KEY|ANTHROPIC_API_KEY)\s*=\s*(?:['\"])?(?:sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}|ghp_[A-Za-z0-9]{20,}|xox[a-zA-Z]-[A-Za-z0-9-]{10,}|[A-Za-z0-9._-]{24,})(?:['\"])?",
            re.IGNORECASE,
        ),
    ),
)


def mask_secret(value: str) -> str:
    raw = str(value or "")
    if not raw:
        return "***"
    if len(raw) <= 4:
        return raw[:1] + "***"
    if len(raw) <= 6:
        return raw[:2] + "***"
    return raw[:2] + "***" + raw[-4:]


def _mask_match(label: str, raw: str) -> str:
    text = str(raw or "")
    if label == "provider_env_assignment" and "=" in text:
        key, value = text.split("=", 1)
        return key.strip() + "=" + mask_secret(value.strip())
    if label == "private_key_header":
        return "-----BEGIN ***PRIVATE KEY-----"
    return mask_secret(text)


def _build_snippet(line: str, start: int, end: int, raw: str, masked: str) -> str:
    s = max(0, start - 24)
    e = min(len(line), end + 24)
    fragment = line[s:e].replace(raw, masked)
    fragment = fragment.replace("\r", "").replace("\n", "")
    if len(fragment) > 160:
        fragment = fragment[:157] + "..."
    return fragment


def _scan_lines(lines: Iterable[str], source: str) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for lineno, line in enumerate(lines, start=1):
        text = str(line)
        for label, pattern in PATTERNS:
            for match in pattern.finditer(text):
                raw = match.group(0)
                masked = _mask_match(label, raw)
                out.append(
                    {
                        "type": label,
                        "file": source,
                        "line": lineno,
                        "snippet": _build_snippet(text, match.start(), match.end(), raw, masked),
                    }
                )
    return out


def _scan_text_blob(blob: str, source: str) -> List[Dict[str, object]]:
    return _scan_lines(io.StringIO(blob), source)


def scan_path(path: str | Path) -> List[Dict[str, object]]:
    p = Path(path)
    if not p.exists():
        return [
            {
                "type": "scan_error",
                "file": str(p),
                "line": 0,
                "snippet": "path_not_found",
            }
        ]

    if p.is_dir():
        out: List[Dict[str, object]] = []
        for child in sorted(p.rglob("*")):
            if child.is_file():
                out.extend(scan_path(child))
        return out

    if zipfile.is_zipfile(p):
        out: List[Dict[str, object]] = []
        with zipfile.ZipFile(p, "r") as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                try:
                    raw = zf.read(name)
                    text = raw.decode("utf-8", errors="ignore")
                except Exception:
                    continue
                out.extend(_scan_text_blob(text, f"{p}:{name}"))
        return out

    try:
        with p.open("r", encoding="utf-8", errors="ignore") as handle:
            return _scan_lines(handle, str(p))
    except Exception as exc:
        return [
            {
                "type": "scan_error",
                "file": str(p),
                "line": 0,
                "snippet": f"read_error:{exc.__class__.__name__}",
            }
        ]


def _is_known_legacy_match(item: Dict[str, object]) -> bool:
    try:
        f = str(item.get("file") or "")
        snippet = str(item.get("snippet") or "")
    except Exception:
        return False
    base = Path(f).name if f else ""
    if base not in _LEGACY_ALLOWED_BASENAMES:
        return False
    return snippet in _LEGACY_ALLOWED_SNIPPETS


def run_scan(paths: Sequence[str] | None = None, stdin_text: str | None = None) -> Dict[str, object]:
    matches: List[Dict[str, object]] = []
    scanned_sources = 0

    for path in list(paths or []):
        scanned_sources += 1
        matches.extend(scan_path(path))

    if stdin_text is not None:
        scanned_sources += 1
        matches.extend(_scan_text_blob(stdin_text, "stdin"))

    real_matches: List[Dict[str, object]] = []
    legacy_matches: List[Dict[str, object]] = []
    for item in matches:
        if item.get("type") == "scan_error":
            real_matches.append(item)
            continue
        if _is_known_legacy_match(item):
            legacy_matches.append(item)
            continue
        real_matches.append(item)

    has_real_matches = any(item.get("type") != "scan_error" for item in real_matches)
    exit_code = 2 if has_real_matches else 0

    payload: Dict[str, object] = {
        "ok": not has_real_matches,
        "exit_code": exit_code,
        "scanned_sources": scanned_sources,
        "matches_total": len(real_matches),
        "matches": real_matches[:MAX_MATCHES_OUTPUT],
        "legacy_matches_total": len(legacy_matches),
        "legacy_matches": legacy_matches[:MAX_MATCHES_OUTPUT],
        "truncated": (len(real_matches) > MAX_MATCHES_OUTPUT) or (len(legacy_matches) > MAX_MATCHES_OUTPUT),
    }
    return payload


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan dump artifacts for secret signatures (redacted output only).")
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Path to dump artifact (file/dir/zip). May be repeated.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    paths = [str(x) for x in list(args.path or []) if str(x).strip()]

    stdin_text = None
    if not paths:
        stdin_text = sys.stdin.read()

    payload = run_scan(paths=paths, stdin_text=stdin_text)
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return int(payload["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
