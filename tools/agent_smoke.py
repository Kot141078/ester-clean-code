# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.agents import runtime as agents_runtime
from modules.volition.journal import journal_path


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def main() -> int:
    created = agents_runtime.create_agent("builder", {"name": "iter37.smoke.builder", "meta": {"source": "tools.agent_smoke"}})
    if not created.get("ok"):
        print(json.dumps({"ok": False, "error": "agent_create_failed", "create": created}, ensure_ascii=True, indent=2))
        return 2

    agent_id = str(created.get("agent_id") or "")
    plan_write = agents_runtime.write_demo_plan(agent_id=agent_id)
    plan_path = Path(str(plan_write.get("plan_path") or "data/plans/demo_builder_plan.json")).resolve()
    if not plan_path.exists():
        print(json.dumps({"ok": False, "error": "plan_not_written", "path": str(plan_path)}, ensure_ascii=True, indent=2))
        return 2

    run_rep = agents_runtime.run_plan_once(agent_id, str(plan_path), dry=False)
    plan_id = str(run_rep.get("plan_id") or "")

    jp = journal_path()
    rows = _read_jsonl(jp)
    filtered = [
        r
        for r in rows
        if str(r.get("agent_id") or ((r.get("metadata") or {}).get("agent_id") or "")).strip() == agent_id
        and str(r.get("plan_id") or ((r.get("metadata") or {}).get("plan_id") or "")).strip() == plan_id
    ]
    required_fields = ["agent_id", "plan_id", "step_index", "action_id", "args_digest", "budgets_snapshot", "decision"]
    enriched_ok = bool(filtered) and all(all(k in row for k in required_fields) for row in filtered)

    agent_root = ROOT / "data" / "agents" / agent_id
    files_ok = (agent_root / "agent.json").exists() and (agent_root / "runs.jsonl").exists() and (agent_root / "artifacts").exists()

    ok = bool(run_rep.get("ok")) and enriched_ok and files_ok
    out = {
        "ok": ok,
        "agent_id": agent_id,
        "plan_path": str(plan_path),
        "plan_id": plan_id,
        "run": run_rep,
        "journal_path": str(jp),
        "journal_rows_for_plan": len(filtered),
        "journal_enriched_ok": enriched_ok,
        "files_ok": files_ok,
    }
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
