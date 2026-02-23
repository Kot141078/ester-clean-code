# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.agents import runtime as agents_runtime
from modules.proactivity import state_store
from modules.proactivity.executor import run_once as proactivity_run_once
from modules.volition.journal import journal_path
from modules.volition.volition_gate import get_default_gate


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    n = 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def main() -> int:
    old = {
        "slot": os.environ.get("ESTER_VOLITION_SLOT"),
        "hours": os.environ.get("ESTER_VOLITION_ALLOWED_HOURS"),
        "proactivity": os.environ.get("ESTER_PROACTIVITY_REAL_ACTIONS_ENABLED"),
        "agents": os.environ.get("ESTER_AGENTS_RUNTIME_ENABLED"),
    }
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_VOLITION_ALLOWED_HOURS"] = "00:00-23:59"
    os.environ["ESTER_PROACTIVITY_REAL_ACTIONS_ENABLED"] = "1"
    os.environ["ESTER_AGENTS_RUNTIME_ENABLED"] = "1"

    jp = journal_path()
    before_journal = _count_lines(jp)
    try:
        lst = agents_runtime.list_agents()
        agent_id = ""
        for a in list(lst.get("agents") or []):
            if str(a.get("name") or "") == "iter28.smoke.agent":
                agent_id = str(a.get("id") or "")
                break
        if not agent_id:
            agent_id = agents_runtime.spawn_agent("procedural", "iter28.smoke.agent", {"tool": "agents_smoke"})

        agent_rep = agents_runtime.run_agent_once(
            agent_id,
            {
                "intent": "iter28_agents_smoke",
                "action": "memory.add_note",
                "args": {
                    "text": "Iter28 agents smoke: procedural action",
                    "tags": ["iter28", "smoke", "agent"],
                    "source": "tools.agents_smoke",
                },
                "needs": [],
            },
            {"max_work_ms": 2000, "max_actions": 3, "window": 60, "est_work_ms": 200},
            get_default_gate(),
        )

        seed = state_store.queue_add(
            title="Iter28 agents smoke initiative",
            text="Executor should run real action memory.add_note and mark done.",
            priority="high",
            source="tools.agents_smoke",
            meta={"iter": 28, "smoke": True},
        )
        proactive_rep = proactivity_run_once(dry=False)
        after_journal = _count_lines(jp)
        delta = max(0, after_journal - before_journal)

        paths = agents_runtime.list_agents().get("paths") or {}
        agents_events_path = Path(str(paths.get("agents_events") or ""))
        runs_path = Path(str(paths.get("runs") or ""))
        files_ok = agents_events_path.exists() and runs_path.exists() and runs_path.stat().st_size > 0

        real_action_kind = str(
            (proactive_rep.get("action") or {}).get("action_kind")
            or ((proactive_rep.get("action") or {}).get("result") or {}).get("kind")
            or ""
        )
        real_action_ok = bool(
            proactive_rep.get("ok")
            and (real_action_kind == "memory.add_note")
            and bool((proactive_rep.get("mark_done") or {}).get("ok"))
        )

        ok = bool(agent_rep.get("ok")) and real_action_ok and files_ok and delta >= 4
        out = {
            "ok": ok,
            "agent_id": agent_id,
            "agent_run": agent_rep,
            "seeded": seed,
            "proactivity_run": proactive_rep,
            "real_action_kind": real_action_kind,
            "journal_path": str(jp),
            "journal_added": delta,
            "agents_files_ok": files_ok,
            "paths": paths,
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0 if ok else 2
    finally:
        for k, v in old.items():
            env_key = {
                "slot": "ESTER_VOLITION_SLOT",
                "hours": "ESTER_VOLITION_ALLOWED_HOURS",
                "proactivity": "ESTER_PROACTIVITY_REAL_ACTIONS_ENABLED",
                "agents": "ESTER_AGENTS_RUNTIME_ENABLED",
            }[k]
            if v is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = v


if __name__ == "__main__":
    raise SystemExit(main())

