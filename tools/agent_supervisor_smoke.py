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

from modules.garage import agent_factory, agent_queue, agent_supervisor
from modules.runtime import execution_window


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
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_agent_supervisor_smoke_")).resolve()
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
        create = agent_factory.create_agent(
            {
                "name": "agent_supervisor_smoke",
                "goal": "Supervisor queue smoke",
                "template_id": "builder.v1",
                "capabilities": ["cap.fs.sandbox.write"],
                "allowed_actions": ["files.sandbox_write"],
                "budgets": {"max_actions": 10, "max_work_ms": 10000, "window": 120, "est_work_ms": 150},
                "owner": "tools.agent_supervisor_smoke",
                "oracle_policy": {"allow_remote": False},
            }
        )
        if not bool(create.get("ok")):
            print(json.dumps({"ok": False, "error": "create_failed", "create": create}, ensure_ascii=True, indent=2))
            return 2
        agent_id = str(create.get("agent_id") or "")

        enqueue_rep = agent_queue.enqueue(
            {
                "steps": [
                    {
                        "action_id": "files.sandbox_write",
                        "args": {"relpath": "supervisor_smoke.txt", "content": "supervisor_ok"},
                    }
                ]
            },
            priority=90,
            challenge_sec=0,
            actor="ester:smoke",
            reason="agent_supervisor_smoke",
            agent_id=agent_id,
        )
        queue_id = str(enqueue_rep.get("queue_id") or "")

        tick_closed = agent_supervisor.tick_once(actor="ester:smoke", reason="smoke_closed", dry_run=False)
        open_rep = execution_window.open_window(
            actor="ester:smoke",
            reason="agent_supervisor_smoke_open",
            ttl_sec=30,
            budget_seconds=60,
            budget_energy=5,
        )
        window_id = str(open_rep.get("window_id") or "")
        tick_open = agent_supervisor.tick_once(actor="ester:smoke", reason="smoke_open", dry_run=False)

        close_rep: Dict[str, Any]
        cur = execution_window.current_window()
        if bool(cur.get("open")) and str(cur.get("window_id") or "").strip():
            close_rep = execution_window.close_window(str(cur.get("window_id") or ""), actor="ester:smoke", reason="cleanup")
        elif window_id:
            close_rep = execution_window.close_window(window_id, actor="ester:smoke", reason="cleanup")
        else:
            close_rep = {"ok": True, "note": "already_closed"}

        queue_events = _read_jsonl(agent_queue.queue_path())
        runs_path = (agent_factory.agents_root() / agent_id / "runs.jsonl").resolve()
        runs = _read_jsonl(runs_path)
        sandbox_file = (agent_factory.agents_root() / agent_id / "sandbox" / "supervisor_smoke.txt").resolve()

        has_claim = any(str(r.get("type") or "") == "claim" and str(r.get("queue_id") or "") == queue_id for r in queue_events)
        has_start = any(str(r.get("type") or "") == "start" and str(r.get("queue_id") or "") == queue_id for r in queue_events)
        has_done = any(str(r.get("type") or "") == "done" and str(r.get("queue_id") or "") == queue_id for r in queue_events)
        has_run_result_done = any(
            str(r.get("event") or "") == "result" and str(r.get("status") or "") == "done"
            for r in runs
        )

        ok = (
            bool(enqueue_rep.get("ok"))
            and bool(queue_id)
            and bool(tick_closed.get("ok"))
            and (not bool(tick_closed.get("ran")))
            and (str(tick_closed.get("blocked") or "") == "window_closed")
            and bool(open_rep.get("ok"))
            and bool(window_id)
            and bool(tick_open.get("ok"))
            and bool(tick_open.get("ran"))
            and bool(sandbox_file.exists())
            and has_claim
            and has_start
            and has_done
            and has_run_result_done
            and bool(close_rep.get("ok"))
        )
        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "agent_id": agent_id,
            "queue_id": queue_id,
            "enqueue": enqueue_rep,
            "tick_closed": tick_closed,
            "open_window": open_rep,
            "tick_open": tick_open,
            "close_window": close_rep,
            "queue_events_summary": {
                "total": len(queue_events),
                "has_claim": has_claim,
                "has_start": has_start,
                "has_done": has_done,
            },
            "runs_path": str(runs_path),
            "runs_total": len(runs),
            "has_run_result_done": has_run_result_done,
            "sandbox_file": str(sandbox_file),
            "sandbox_file_exists": bool(sandbox_file.exists()),
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
