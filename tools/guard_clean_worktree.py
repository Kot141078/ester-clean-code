# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[1]
WATCH = [
    ROOT / "ester_manifest.json",
    ROOT / "secrets" / "ed25519.pk",
    ROOT / "secrets" / "ed25519.sk",
]


def _sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _snapshot(paths: List[Path]) -> Dict[str, str]:
    return {str(p): _sha256(p) for p in paths}


def _run(cmd: List[str], env: Dict[str, str]) -> int:
    proc = subprocess.run(cmd, cwd=str(ROOT), env=env)
    return int(proc.returncode or 0)


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-health", action="store_true")
    ap.add_argument("--skip-compileall", action="store_true")
    args = ap.parse_args(argv)

    env = dict(os.environ)
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    env.setdefault("PYTHONPYCACHEPREFIX", str(Path(os.getenv("TEMP", str(ROOT / "tmp"))) / "ester_pycache"))
    env.setdefault("PYTHONPATH", ".")
    env.setdefault("ESTER_ALLOW_SECRET_WRITE", "0")

    before = _snapshot(WATCH)
    codes: List[int] = []

    if not args.skip_health:
        codes.append(_run([sys.executable, "-B", "modules/health_check.py"], env))
    if not args.skip_compileall:
        codes.append(_run([sys.executable, "-B", "-m", "compileall", "modules", "routes", "tools"], env))

    after = _snapshot(WATCH)
    changed = [k for k in before if before[k] != after[k]]

    print("GUARD_REPORT")
    print(f"before={before}")
    print(f"after={after}")
    print(f"changed={changed}")
    print(f"codes={codes}")
    print(f"commands_ok={all(code == 0 for code in codes)}")

    # This guard focuses on side effects; compile errors can be pre-existing.
    if changed:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
