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

from modules.garage import agent_factory
from modules.runtime.status_iter18 import runtime_status
from modules.thinking import action_registry


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_capability_audit_view_smoke_")).resolve()
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
        "ESTER_BG_ENABLE",
        "ESTER_CAP_AUDIT_TTL_SEC",
        "ESTER_CAP_AUDIT_TAIL_LINES",
        "ESTER_CAP_AUDIT_MAX_AGENTS_SCAN",
    ]
    old_env = {k: os.environ.get(k) for k in env_keys}
    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["GARAGE_ROOT"] = str(garage_root)
    os.environ["ESTER_VOLITION_ALLOWED_HOURS"] = "00:00-23:59"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "0"
    os.environ["ESTER_ORACLE_ENABLE"] = "0"
    os.environ["ESTER_BG_ENABLE"] = "0"
    os.environ["ESTER_CAP_AUDIT_TTL_SEC"] = "1"
    os.environ["ESTER_CAP_AUDIT_TAIL_LINES"] = "2000"
    os.environ["ESTER_CAP_AUDIT_MAX_AGENTS_SCAN"] = "2000"

    try:
        action_registry.list_action_ids()

        os.environ["ESTER_VOLITION_SLOT"] = "A"
        legacy_create = agent_factory.create_agent(
            {
                "name": "agent_capability_audit_legacy",
                "goal": "legacy agent for audit view",
                "allowed_actions": ["files.sandbox_write"],
                "owner": "tools.capability_audit_view_smoke",
                "budgets": {"max_actions": 4, "max_work_ms": 2000, "window": 60, "est_work_ms": 200},
                "oracle_policy": {"allow_remote": False},
            }
        )

        os.environ["ESTER_VOLITION_SLOT"] = "B"
        capability_create = agent_factory.create_agent(
            {
                "name": "agent_capability_audit_caps",
                "goal": "capability agent for audit view",
                "template_id": "builder.v1",
                "capabilities": ["cap.fs.sandbox.write"],
                "owner": "tools.capability_audit_view_smoke",
                "budgets": {"max_actions": 6, "max_work_ms": 3000, "window": 60, "est_work_ms": 250},
                "oracle_policy": {"allow_remote": False},
            }
        )
        cap_agent_id = str(capability_create.get("agent_id") or "")

        deny_enqueue = action_registry.invoke(
            "agent.queue.enqueue",
            {
                "agent_id": cap_agent_id,
                "actor": "ester:smoke",
                "reason": "capability_audit_deny_case",
                "challenge_sec": 0,
                "plan": {
                    "schema": "ester.plan.v1",
                    "plan_id": "capability_audit_view_smoke_deny",
                    "steps": [{"action": "llm.remote.call", "args": {"prompt": "deny", "purpose": "audit"}}],
                },
            },
        )

        status = runtime_status()
        audit = dict(status.get("capability_audit") or {})
        agents = dict(audit.get("agents") or {})
        deny = dict(audit.get("deny") or {})
        recent_events = [dict(x) for x in list(audit.get("recent_events") or []) if isinstance(x, dict)]

        has_deny_recent = any(
            (not bool(row.get("allowed")))
            and str(row.get("reason_code") or "") == "ACTION_NOT_ALLOWED"
            for row in recent_events
        )

        ok = (
            bool(legacy_create.get("ok"))
            and bool(capability_create.get("ok"))
            and (not bool(deny_enqueue.get("ok")))
            and str(deny_enqueue.get("error_code") or "") == "ACTION_NOT_ALLOWED"
            and int(agents.get("pure_legacy") or 0) >= 1
            and int(agents.get("capability_mode") or 0) >= 1
            and int(deny.get("total_recent") or 0) >= 1
            and has_deny_recent
        )

        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "legacy_create": legacy_create,
            "capability_create": capability_create,
            "deny_enqueue": deny_enqueue,
            "audit": audit,
            "has_deny_recent": has_deny_recent,
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0 if ok else 2
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

