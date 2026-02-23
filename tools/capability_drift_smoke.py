# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.garage import agent_factory
from modules.runtime import capability_drift


def _read_json(path: Path) -> Dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return raw
    return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_capability_drift_smoke_")).resolve()
    persist_dir = (tmp_root / "persist").resolve()
    garage_root = (tmp_root / "garage").resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)
    garage_root.mkdir(parents=True, exist_ok=True)

    env_keys = [
        "PERSIST_DIR",
        "GARAGE_ROOT",
        "ESTER_VOLITION_SLOT",
        "ESTER_ALLOW_OUTBOUND_NETWORK",
        "ESTER_ORACLE_ENABLE",
        "ESTER_DRIFT_TTL_SEC",
        "ESTER_DRIFT_FAIL_MAX",
        "ESTER_DRIFT_MAX_AGENTS_SCAN",
    ]
    old_env = {k: os.environ.get(k) for k in env_keys}
    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["GARAGE_ROOT"] = str(garage_root)
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "0"
    os.environ["ESTER_ORACLE_ENABLE"] = "0"
    os.environ["ESTER_DRIFT_TTL_SEC"] = "1"
    os.environ["ESTER_DRIFT_FAIL_MAX"] = "3"
    os.environ["ESTER_DRIFT_MAX_AGENTS_SCAN"] = "2000"

    try:
        create = agent_factory.create_agent(
            {
                "name": "agent_capability_drift_smoke",
                "goal": "detect capability drift",
                "template_id": "builder.v1",
                "capabilities": ["cap.fs.sandbox.write"],
                "owner": "tools.capability_drift_smoke",
                "budgets": {"max_actions": 6, "max_work_ms": 3000, "window": 60, "est_work_ms": 250},
                "oracle_policy": {"allow_remote": False},
            }
        )
        if not bool(create.get("ok")):
            out = {"ok": False, "error": "create_failed", "create": create}
            print(json.dumps(out, ensure_ascii=True, indent=2))
            return 2

        spec_path = Path(str(create.get("spec_path") or "")).resolve()
        if not spec_path.exists():
            out = {"ok": False, "error": "spec_path_missing", "spec_path": str(spec_path)}
            print(json.dumps(out, ensure_ascii=True, indent=2))
            return 2

        scan1 = capability_drift.scan_agents_for_drift(write=True, max_agents=2000)

        spec = _read_json(spec_path)
        tampered_allow = capability_drift.normalize_allowlist(
            list(spec.get("allowed_actions") or []) + ["llm.remote.call"]
        )
        spec["allowed_actions"] = tampered_allow
        spec["allowed_actions_hash"] = capability_drift.allowlist_hash(tampered_allow)
        _write_json(spec_path, spec)

        scan2 = capability_drift.scan_agents_for_drift(write=True, max_agents=2000)
        recent = [dict(x) for x in list(scan2.get("recent_events") or []) if isinstance(x, dict)]
        mismatch_events: List[Dict[str, Any]] = [
            row
            for row in recent
            if str(row.get("kind") or "") == "SPEC_MISMATCH"
        ]
        has_tamper = any(str(row.get("reason_code") or "") == "TAMPER_SUSPECT" for row in mismatch_events)

        ok = (
            bool(scan1.get("ok"))
            and int(scan1.get("mismatches") or 0) == 0
            and int(scan1.get("changed") or 0) == 0
            and int(scan1.get("caps_changed") or 0) == 0
            and bool(scan2.get("ok"))
            and int(scan2.get("mismatches") or 0) >= 1
            and bool(mismatch_events)
            and bool(has_tamper)
        )

        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "agent_id": str(create.get("agent_id") or ""),
            "spec_path": str(spec_path),
            "scan1": scan1,
            "scan2": scan2,
            "mismatch_events": mismatch_events,
            "has_tamper": has_tamper,
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

