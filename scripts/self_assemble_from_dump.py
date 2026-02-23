# -*- coding: utf-8 -*-
"""
scripts/self_assemble_from_dump.py — CLI: samosborka iz dampa/arkhiva i aktivatsiya.

Primery:
  ESTER_RUN_ROOT=/opt/ester/runroot ESTER_MOVE_TOKEN=yes \\
    python -m scripts.self_assemble_from_dump --path /media/owner/USB/ESTER/dumps/ester_dump.tar.gz --target-parent /opt/ester/runroot
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from modules.selfmanage.dump_assembler import assemble_from_archive
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Self assemble from dump/archive")
    p.add_argument("--path", required=True, help="Put k zip/tar.gz arkhivu")
    p.add_argument(
        "--target-parent",
        type=str,
        default=None,
        help="Koren, gde lezhit runroot/releases (esli ne zadan — ESTER_RUN_ROOT ili cwd)",
    )
    p.add_argument(
        "--no-token",
        action="store_true",
        help="Ne trebovat ESTER_MOVE_TOKEN (ispolzovat tolko lokalno)",
    )
    a = p.parse_args(argv)

    target = a.target_parent or (os.getenv("ESTER_RUN_ROOT") or os.getcwd())
    res = assemble_from_archive(a.path, target_parent=target, require_token=(not a.no_token))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())