# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Set

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.garage.templates import create_agent_from_template


def _snapshot(root: Path) -> Set[str]:
    out: Set[str] = set()
    if not root.exists():
        return out
    for p in root.rglob("*"):
        out.add(str(p.relative_to(root)).replace("\\", "/"))
    return out


def _count_agent_dirs(garage_root: Path) -> int:
    agents = (garage_root / "agents").resolve()
    if not agents.exists():
        return 0
    return sum(1 for p in agents.iterdir() if p.is_dir())


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_garage_dry_run_smoke_")).resolve()
    persist_dir = (tmp_root / "persist").resolve()
    garage_root = (tmp_root / "garage").resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)
    garage_root.mkdir(parents=True, exist_ok=True)

    env_keys = ["PERSIST_DIR", "GARAGE_ROOT", "ESTER_VOLITION_SLOT"]
    old_env = {k: os.environ.get(k) for k in env_keys}
    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["GARAGE_ROOT"] = str(garage_root)
    os.environ["ESTER_VOLITION_SLOT"] = "A"

    try:
        before_snapshot = _snapshot(tmp_root)
        before_dirs = _count_agent_dirs(garage_root)

        rep_dry = create_agent_from_template(
            "builder.v1",
            {"name": "smoke", "owner": "smoke", "goal": "dry-run-check"},
            dry_run=True,
        )

        after_dry_snapshot = _snapshot(tmp_root)
        after_dry_dirs = _count_agent_dirs(garage_root)

        dry_ok = (
            bool(rep_dry.get("ok"))
            and bool(rep_dry.get("dry_run"))
            and (bool(rep_dry.get("created")) is False)
            and (not str(rep_dry.get("agent_id") or "").strip())
            and (not str(rep_dry.get("path") or "").strip())
            and (after_dry_dirs == before_dirs)
            and (after_dry_snapshot == before_snapshot)
        )

        rep_real = create_agent_from_template(
            "builder.v1",
            {"name": "smoke2", "owner": "smoke", "goal": "real-run-check"},
            dry_run=False,
        )

        real_path = Path(str(rep_real.get("path") or "")).resolve() if rep_real.get("path") else Path("")
        real_ok = (
            bool(rep_real.get("ok"))
            and (bool(rep_real.get("created")) is True)
            and bool(str(rep_real.get("agent_id") or "").strip())
            and bool(str(rep_real.get("path") or "").strip())
            and bool(real_path and real_path.exists() and real_path.is_dir())
            and (real_path / "plan.json").exists()
            and (real_path / "README_agent.txt").exists()
            and (_count_agent_dirs(garage_root) >= after_dry_dirs + 1)
        )

        ok = bool(dry_ok and real_ok)
        out: Dict[str, Any] = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "dry_run_created_dirs": int(after_dry_dirs - before_dirs),
            "real_created_dirs": int(_count_agent_dirs(garage_root) - after_dry_dirs),
            "dry_run_report": rep_dry,
            "real_run_report": {
                "ok": bool(rep_real.get("ok")),
                "created": bool(rep_real.get("created")),
                "agent_id": str(rep_real.get("agent_id") or ""),
                "path": str(rep_real.get("path") or ""),
            },
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0 if ok else 2
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

