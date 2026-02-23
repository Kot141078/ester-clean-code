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

from modules.garage import agent_factory, agent_queue
from modules.runtime import execution_window
from modules.thinking import action_registry
from modules.volition.journal import journal_path


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                row = json.loads(s)
            except Exception:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_agent_capabilities_smoke_")).resolve()
    persist_dir = (tmp_root / "persist").resolve()
    garage_root = (tmp_root / "garage").resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)
    garage_root.mkdir(parents=True, exist_ok=True)

    env_keys = [
        "PERSIST_DIR",
        "GARAGE_ROOT",
        "ESTER_VOLITION_SLOT",
        "ESTER_VOLITION_ALLOWED_HOURS",
        "ESTER_ALLOW_OUTBOUND_NETWORK",
        "ESTER_ORACLE_ENABLE",
    ]
    old_env = {k: os.environ.get(k) for k in env_keys}
    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["GARAGE_ROOT"] = str(garage_root)
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_VOLITION_ALLOWED_HOURS"] = "00:00-23:59"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "0"
    os.environ["ESTER_ORACLE_ENABLE"] = "0"

    try:
        cur = execution_window.current_window()
        if bool(cur.get("open")) and str(cur.get("window_id") or "").strip():
            execution_window.close_window(str(cur.get("window_id") or ""), actor="ester:smoke", reason="capabilities_smoke_reset")

        create = agent_factory.create_agent(
            {
                "name": "agent_capabilities_smoke",
                "goal": "enqueue capability checks",
                "template_id": "builder.v1",
                "capabilities": ["cap.fs.sandbox.write"],
                "owner": "tools.agent_capabilities_smoke",
                "budgets": {"max_actions": 6, "max_work_ms": 3000, "window": 60, "est_work_ms": 200},
                "oracle_policy": {"allow_remote": False},
            }
        )
        if not bool(create.get("ok")):
            print(json.dumps({"ok": False, "error": "create_failed", "create": create}, ensure_ascii=True, indent=2))
            return 2

        agent_id = str(create.get("agent_id") or "")
        spec = dict((create.get("spec") or {}))
        before_live = int((agent_queue.fold_state().get("live_total") or 0))

        allow_enqueue = action_registry.invoke(
            "agent.queue.enqueue",
            {
                "agent_id": agent_id,
                "actor": "ester:smoke",
                "reason": "capabilities_smoke_allow",
                "challenge_sec": 0,
                "plan": {
                    "schema": "ester.plan.v1",
                    "plan_id": "caps_smoke_allow",
                    "steps": [{"action": "files.sandbox_write", "args": {"relpath": "caps.txt", "content": "ok"}}],
                },
            },
        )
        after_allow_live = int((agent_queue.fold_state().get("live_total") or 0))

        deny_enqueue = action_registry.invoke(
            "agent.queue.enqueue",
            {
                "agent_id": agent_id,
                "actor": "ester:smoke",
                "reason": "capabilities_smoke_deny",
                "challenge_sec": 0,
                "plan": {
                    "schema": "ester.plan.v1",
                    "plan_id": "caps_smoke_deny",
                    "steps": [{"action": "llm.remote.call", "args": {"prompt": "nope", "purpose": "deny"}}],
                },
            },
        )

        journal_rows = _read_jsonl(journal_path())
        deny_rows = [
            row
            for row in journal_rows
            if str(row.get("step") or "") == "agent.queue.enqueue"
            and (not bool(row.get("allowed")))
            and "llm.remote.call" in list(((row.get("metadata") or {}).get("disallowed_actions") or []))
        ]

        ok = (
            bool(create.get("ok"))
            and bool(agent_id)
            and bool(spec.get("template_id") == "builder.v1")
            and bool(spec.get("capabilities_effective"))
            and bool(allow_enqueue.get("ok"))
            and (after_allow_live == before_live + 1)
            and (not bool(deny_enqueue.get("ok")))
            and (str(deny_enqueue.get("error_code") or "") == "ACTION_NOT_ALLOWED")
            and bool(deny_rows)
        )
        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "agent_id": agent_id,
            "create": create,
            "allow_enqueue": allow_enqueue,
            "deny_enqueue": deny_enqueue,
            "queue_live_before": before_live,
            "queue_live_after_allow": after_allow_live,
            "deny_rows": len(deny_rows),
            "journal_path": str(journal_path()),
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

