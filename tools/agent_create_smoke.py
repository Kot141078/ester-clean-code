# -*- coding: utf-8 -*-
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import agent_create as agent_create_tool


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


def _invoke(argv: list[str]) -> Tuple[int, Dict[str, Any], str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = int(agent_create_tool.main(list(argv)))
    raw = str(buf.getvalue() or "").strip()
    rep: Dict[str, Any] = {}
    if raw:
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                rep = dict(obj)
        except Exception:
            rep = {"ok": False, "error": "invalid_json_output", "raw": raw}
            rc = 2
    return rc, rep, raw


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_agent_create_smoke_")).resolve()
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
        before_agents = _count_agent_dirs(garage_root)

        rc_dry, rep_dry, _ = _invoke(["builder", "--dry-run", "--name", "iter69.smoke.dry"])
        after_dry_snapshot = _snapshot(tmp_root)
        after_dry_agents = _count_agent_dirs(garage_root)
        dry_ok = (
            rc_dry == 0
            and bool(rep_dry.get("ok"))
            and bool(rep_dry.get("dry_run"))
            and (bool(rep_dry.get("created")) is False)
            and (not str(rep_dry.get("agent_id") or "").strip())
            and (not str(rep_dry.get("path") or "").strip())
            and (after_dry_agents == before_agents)
            and (after_dry_snapshot == before_snapshot)
        )

        rc_real, rep_real, _ = _invoke(["builder", "--name", "iter69.smoke.real"])
        real_path = Path(str(rep_real.get("path") or "")).resolve() if rep_real.get("path") else Path("")
        real_ok = (
            rc_real == 0
            and bool(rep_real.get("ok"))
            and (bool(rep_real.get("created")) is True)
            and bool(str(rep_real.get("agent_id") or "").strip())
            and bool(str(rep_real.get("path") or "").strip())
            and bool(real_path and real_path.exists() and real_path.is_dir())
            and (real_path / "plan.json").exists()
            and (real_path / "README_agent.txt").exists()
            and (_count_agent_dirs(garage_root) >= after_dry_agents + 1)
        )

        rc_reviewer, rep_reviewer, _ = _invoke(["--template", "reviewer.v1", "--dry-run"])
        reviewer_ok = (
            rc_reviewer == 0
            and bool(rep_reviewer.get("ok"))
            and (str(rep_reviewer.get("template_id") or "") == "reviewer.v1")
            and bool(rep_reviewer.get("dry_run"))
            and (bool(rep_reviewer.get("created")) is False)
        )

        ok = bool(dry_ok and real_ok and reviewer_ok)
        out = {
            "ok": ok,
            "dry_run_ok": bool(dry_ok),
            "real_ok": bool(real_ok),
            "reviewer_dry_ok": bool(reviewer_ok),
            "tmp_root": str(tmp_root),
            "dry_run_report": rep_dry,
            "real_report": rep_real,
            "reviewer_dry_report": rep_reviewer,
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0 if ok else 2
    finally:
        for key, val in old_env.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
