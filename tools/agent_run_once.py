# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.agents import runtime as agents_runtime


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Run one Agent Runtime JSON plan once (offline).")
    ap.add_argument("--agent", "--agent-id", dest="agent_id", default="", help="existing agent id")
    ap.add_argument("--plan", default="data/plans/demo_builder_plan.json", help="path to JSON plan")
    ap.add_argument("--dry", default="0", help="dry run flag 1/0")
    ap.add_argument("--template", default="builder", help="template for auto-create if --agent is empty")
    ap.add_argument("--write-demo-plan", default="0", help="write demo plan to --plan path before run")
    args = ap.parse_args(argv)

    dry = str(args.dry or "").strip().lower() in {"1", "true", "yes", "on", "y"}
    write_demo = str(args.write_demo_plan or "").strip().lower() in {"1", "true", "yes", "on", "y"}
    plan_path = Path(str(args.plan or "data/plans/demo_builder_plan.json")).resolve()

    agent_id = str(args.agent_id or "").strip()
    if not agent_id:
        created = agents_runtime.create_agent(str(args.template or "builder"), {"meta": {"source": "tools.agent_run_once"}})
        if not created.get("ok"):
            print(json.dumps({"ok": False, "error": "agent_create_failed", "create": created}, ensure_ascii=True, indent=2))
            return 2
        agent_id = str(created.get("agent_id") or "")

    if write_demo or (not plan_path.exists()):
        agents_runtime.write_demo_plan(str(plan_path), agent_id=agent_id)

    run_rep = agents_runtime.run_plan_once(agent_id, str(plan_path), dry=dry)
    out = {
        "ok": bool(run_rep.get("ok")),
        "agent_id": agent_id,
        "plan_path": str(plan_path),
        "run": run_rep,
    }
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
