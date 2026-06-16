# -*- coding: utf-8 -*-
"""Offline runner for the SRLM growth_engine test surface."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_growth_engine.py",
        "-q",
    ]
    return subprocess.call(cmd, cwd=str(repo))


if __name__ == "__main__":
    raise SystemExit(main())
