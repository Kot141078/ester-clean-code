# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.agents import plan_schema
from modules.garage import agent_queue


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_plan_schema_smoke_")).resolve()
    persist_dir = (tmp_root / "persist").resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)

    env_keys = ["PERSIST_DIR", "ESTER_VOLITION_SLOT", "ESTER_PLAN_SCHEMA_STRICT_FAIL_MAX"]
    old_env = {k: os.environ.get(k) for k in env_keys}

    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_PLAN_SCHEMA_STRICT_FAIL_MAX"] = "3"

    try:
        case_ok = agent_queue.enqueue(
            {
                "schema": "ester.plan.v1",
                "plan_id": "smoke_plan_ok",
                "steps": [{"action": "files.sandbox_write", "args": {"relpath": "ok.txt", "content": "ok"}}],
            },
            actor="ester:smoke",
            reason="plan_schema_smoke_case_ok",
            agent_id="agent_plan_schema_smoke",
            challenge_sec=0,
        )

        case_unknown = agent_queue.enqueue(
            {
                "schema": "ester.plan.v1",
                "plan_id": "smoke_plan_unknown",
                "steps": [{"action": "files.__nope__", "args": {}}],
            },
            actor="ester:smoke",
            reason="plan_schema_smoke_case_unknown",
            agent_id="agent_plan_schema_smoke",
            challenge_sec=0,
        )

        case_extra_key = agent_queue.enqueue(
            {
                "schema": "ester.plan.v1",
                "plan_id": "smoke_plan_extra",
                "steps": [{"action": "files.sandbox_write", "args": {}, "pwn": 1}],
            },
            actor="ester:smoke",
            reason="plan_schema_smoke_case_extra_key",
            agent_id="agent_plan_schema_smoke",
            challenge_sec=0,
        )

        case_legacy = agent_queue.enqueue(
            {
                "steps": [{"action_id": "files.sandbox_write", "args": {"relpath": "legacy.txt", "content": "legacy"}}]
            },
            actor="ester:smoke",
            reason="plan_schema_smoke_case_legacy",
            agent_id="agent_plan_schema_smoke",
            challenge_sec=0,
        )
        legacy_qid = str(case_legacy.get("queue_id") or "")
        folded = agent_queue.fold_state()
        legacy_item = dict((folded.get("items_by_id") or {}).get(legacy_qid) or {})
        legacy_plan = dict(legacy_item.get("plan") or {})
        legacy_steps = [dict(x) for x in list(legacy_plan.get("steps") or []) if isinstance(x, dict)]
        legacy_normalized = bool(legacy_steps and str(legacy_steps[0].get("action") or "").strip())

        yaml_case = {"ok": False, "skipped": False, "error": ""}
        yaml_path = (tmp_root / "plan.yaml").resolve()
        _write_text(
            yaml_path,
            (
                "schema: ester.plan.v1\n"
                "plan_id: yaml_plan_smoke\n"
                "steps:\n"
                "  - action: files.sandbox_write\n"
                "    args:\n"
                "      relpath: yaml.txt\n"
                "      content: yaml\n"
            ),
        )
        try:
            import yaml  # type: ignore  # noqa: F401

            yrep = plan_schema.load_plan_from_path(str(yaml_path))
            yaml_case = {"ok": bool(yrep.get("ok")), "skipped": False, "error": str(yrep.get("error") or "")}
        except Exception:
            yrep = plan_schema.load_plan_from_path(str(yaml_path))
            yaml_case = {
                "ok": str(yrep.get("error") or "") == "yaml_not_supported_no_deps",
                "skipped": True,
                "error": str(yrep.get("error") or ""),
            }

        ok = (
            bool(case_ok.get("ok"))
            and (not bool(case_unknown.get("ok")))
            and str(case_unknown.get("error") or "") == "plan_invalid"
            and (not bool(case_extra_key.get("ok")))
            and str(case_extra_key.get("error") or "") == "plan_invalid"
            and bool(case_legacy.get("ok"))
            and legacy_normalized
            and bool(yaml_case.get("ok"))
        )

        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "queue_path": str(agent_queue.queue_path()),
            "slot": os.environ.get("ESTER_VOLITION_SLOT", ""),
            "case_ok": case_ok,
            "case_unknown": case_unknown,
            "case_extra_key": case_extra_key,
            "case_legacy": case_legacy,
            "legacy_normalized": legacy_normalized,
            "yaml_case": yaml_case,
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

