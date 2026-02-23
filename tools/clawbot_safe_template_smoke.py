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

from modules.garage.templates import create_agent_from_template
from modules.thinking import action_registry


def _as_list(value: Any) -> List[str]:
    out: List[str] = []
    for row in list(value or []):
        s = str(row or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_clawbot_safe_template_smoke_")).resolve()
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
        create = create_agent_from_template(
            "clawbot.safe.v1",
            {
                "name": "clawbot_safe_template_smoke",
                "goal": "Draft a safe clawbot plan for operator review",
                "owner": "tools.clawbot_safe_template_smoke",
            },
        )

        if not bool(create.get("ok")):
            print(json.dumps({"ok": False, "error": "create_failed", "create": create}, ensure_ascii=True, indent=2))
            return 2

        agent_id = str(create.get("agent_id") or "")
        spec = dict(create.get("spec") or {})
        plan = dict(create.get("plan") or {})

        allowed_actions = _as_list(create.get("allowed_actions") or spec.get("allowed_actions"))
        expected_actions = {"files.sandbox_write", "files.sha256_verify", "messages.outbox.enqueue", "memory.add_note"}
        banned_signals = ("remote", "oracle", "telegram.send", "desktop", "rpa", "computer_use", "web.search")
        disallowed_found = sorted(
            {
                a
                for a in allowed_actions
                if (a not in expected_actions) or any(sig in a for sig in banned_signals)
            }
        )

        scopes = dict(spec.get("scopes") or {})
        fs_roots = _as_list(scopes.get("fs_roots") or [])
        network_mode = str(scopes.get("network") or "")
        oracle_policy = dict(spec.get("oracle_policy") or {})
        comm_policy = dict(spec.get("comm_policy") or {})
        plan_steps = [dict(x or {}) for x in list(plan.get("steps") or [])]
        plan_actions = _as_list([row.get("action_id") for row in plan_steps])

        deny_enqueue = action_registry.invoke(
            "agent.queue.enqueue",
            {
                "agent_id": agent_id,
                "actor": "ester:smoke",
                "reason": "clawbot_safe_template_smoke_deny",
                "challenge_sec": 0,
                "plan": {
                    "schema": "ester.plan.v1",
                    "plan_id": "clawbot_safe_smoke_deny",
                    "steps": [{"action": "llm.remote.call", "args": {"prompt": "must be denied"}}],
                },
            },
        )

        ok = (
            bool(agent_id)
            and (str(spec.get("template_id") or "") == "clawbot.safe.v1")
            and (network_mode == "disabled")
            and ("data/garage/sandbox" in fs_roots)
            and bool(allowed_actions)
            and (set(allowed_actions).issubset(expected_actions))
            and (len(disallowed_found) == 0)
            and all(a in expected_actions for a in plan_actions)
            and (bool(oracle_policy.get("enabled")) is False)
            and (bool(oracle_policy.get("requires_window")) is True)
            and (bool(comm_policy.get("enabled")) is False)
            and (bool(comm_policy.get("requires_window")) is True)
            and (not bool(deny_enqueue.get("ok")))
            and (str(deny_enqueue.get("error_code") or "") == "ACTION_NOT_ALLOWED")
        )

        out: Dict[str, Any] = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "agent_id": agent_id,
            "allowed_actions": allowed_actions,
            "expected_actions": sorted(expected_actions),
            "plan_actions": plan_actions,
            "disallowed_found": disallowed_found,
            "scopes": scopes,
            "oracle_policy": oracle_policy,
            "comm_policy": comm_policy,
            "deny_enqueue": deny_enqueue,
            "create": create,
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

