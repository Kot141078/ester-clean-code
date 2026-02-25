# -*- coding: utf-8 -*-
"""Generatsiya CHANGELOG.md iz git-logov (Keep a Changelog stil, kratko).
Use:
  python3 scripts/changelog_from_commits.py > CHANGELOG.md

Optsii via ENV:
  - CHANGELOG_SINCE_TAG (for example, v0.0.0) — ogranichit spisok kommitov."""
from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from typing import List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _sh(args: List[str]) -> str:
    return (
        subprocess.check_output(args, stderr=subprocess.DEVNULL).decode("utf-8", "ignore").strip()
    )


def _git_commits(since_tag: str | None) -> List[str]:
    fmt = "%h %ad %s"
    args = ["git", "log", f"--date=short", f"--pretty=format:{fmt}"]
    if since_tag:
        args.insert(2, f"{since_tag}..HEAD")
    out = _sh(args)
    return [line for line in out.splitlines() if line]


def main() -> int:
    since_tag = os.getenv("CHANGELOG_SINCE_TAG")
    today = dt.date.today().isoformat()
    commits = _git_commits(since_tag)

    print("# Changelog")
    print("")
    print("All notable changes to this project will be documented in this file.")
    print("This file is generated from git history; manual edits are allowed above release blocks.")
    print("")
    print(f"## [v0.1-preview] - {today}")
    print("")
    if not commits:
        print("*No changes recorded.*")
    else:
        for line in commits:
            print(f"- {line}")
    print("")
    print("## [Unreleased]")
    print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())