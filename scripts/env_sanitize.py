# -*- coding: utf-8 -*-
"""
scripts/env_sanitize.py - sanitize .env lines that python-dotenv cannot parse.

The script keeps comments/empty lines, validates KEY=value format,
strips inline comments outside quotes, and writes two outputs:
- config/.env.cleaned
- config/.env.invalid
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import List, Tuple

ENV_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), ".env")
OUT_DIR = os.path.join(os.getcwd(), "config")
OUT_CLEAN = os.path.join(OUT_DIR, ".env.cleaned")
OUT_BAD = os.path.join(OUT_DIR, ".env.invalid")

KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def strip_inline_comment(value: str) -> str:
    out: List[str] = []
    quote = None
    for ch in value:
        if ch in ('"', "'"):
            quote = None if quote == ch else ch
        if ch == "#" and quote is None:
            break
        out.append(ch)
    return "".join(out).rstrip()


def normalize_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1]
    return value


def sanitize_lines(lines: List[str]) -> Tuple[List[str], List[str]]:
    clean: List[str] = []
    bad: List[str] = []
    for i, raw in enumerate(lines, start=1):
        line = raw.rstrip("\r\n")
        if not line or line.lstrip().startswith("#"):
            clean.append(line)
            continue
        if "=" not in line:
            bad.append(f"{i}:{line}")
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not KEY_RE.match(key):
            bad.append(f"{i}:{line}")
            continue

        value = strip_inline_comment(value)
        value = normalize_value(value)
        clean.append(f"{key}={value}")
    return clean, bad


def main() -> int:
    if not os.path.isfile(ENV_PATH):
        print(json.dumps({"ok": False, "error": ".env not found", "path": ENV_PATH}, ensure_ascii=False))
        return 1

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(ENV_PATH, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    clean, bad = sanitize_lines(lines)

    with open(OUT_CLEAN, "w", encoding="utf-8") as f:
        f.write("\n".join(clean) + "\n")

    with open(OUT_BAD, "w", encoding="utf-8") as f:
        f.write("\n".join(bad) + "\n")

    print(
        json.dumps(
            {
                "ok": True,
                "in": ENV_PATH,
                "clean": OUT_CLEAN,
                "invalid": OUT_BAD,
                "invalid_count": len(bad),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
