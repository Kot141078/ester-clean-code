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

from modules.garage import agent_factory, agent_runner
from modules.runtime import oracle_requests, oracle_window
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
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_agent_resume_smoke_")).resolve()
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
        "ESTER_ORACLE_DRY_RUN_DISABLE",
        "ESTER_VOLITION_ALLOWED_HOURS",
    ]
    old_env = {k: os.environ.get(k) for k in env_keys}

    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["GARAGE_ROOT"] = str(garage_root)
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "1"
    os.environ["ESTER_ORACLE_ENABLE"] = "0"
    os.environ["ESTER_ORACLE_DRY_RUN_DISABLE"] = "0"
    os.environ["ESTER_VOLITION_ALLOWED_HOURS"] = "00:00-23:59"

    try:
        create = agent_factory.create_agent(
            {
                "name": "agent_resume_smoke",
                "goal": "Pause on oracle then resume from same step",
                "template_id": "oracle.v1",
                "capabilities": ["cap.oracle.remote.call", "cap.fs.sandbox.write"],
                "allowed_actions": ["llm.remote.call", "files.sandbox_write"],
                "budgets": {"max_actions": 20, "max_work_ms": 20000, "window": 120, "est_work_ms": 200},
                "owner": "tools.agent_resume_smoke",
                "oracle_policy": {"allow_remote": True},
            }
        )
        if not bool(create.get("ok")):
            print(json.dumps({"ok": False, "error": "create_failed", "create": create}, ensure_ascii=True, indent=2))
            return 2

        agent_id = str(create.get("agent_id") or "")
        chain_id = "chain_agent_resume_smoke"
        plan = {
            "steps": [
                {
                    "action_id": "llm.remote.call",
                    "args": {
                        "prompt": "agent_resume_smoke_ping",
                        "purpose": "agent_resume_smoke",
                        "model": "gpt-4o-mini",
                        "max_tokens": 24,
                        "dry_run": True,
                    },
                },
                {
                    "action_id": "files.sandbox_write",
                    "args": {"relpath": "after_resume.txt", "content": "resume_ok"},
                },
            ]
        }

        run_a = agent_runner.run_once(agent_id, plan, {"intent": "agent_resume_smoke_a", "chain_id": chain_id})
        request_id = str(run_a.get("pending_request_id") or "")
        state_path = (persist_dir / "agents" / agent_id / "state.json").resolve()
        state_a = {}
        if state_path.exists():
            state_a = json.loads(state_path.read_text(encoding="utf-8"))

        os.environ["ESTER_ORACLE_ENABLE"] = "1"
        approve = oracle_requests.approve_request(
            request_id,
            actor="ester:smoke",
            reason="agent_resume_smoke_approve",
            ttl_sec=60,
            budgets={"max_calls": 1, "max_est_tokens_in_total": 1000, "max_tokens_out_total": 100},
            allow_agents=True,
        )

        resume = action_registry.invoke(
            "agent.resume",
            {
                "agent_id": agent_id,
                "reason": "oracle approved",
                "actor": "ester:smoke",
            },
        )

        state_b = {}
        if state_path.exists():
            state_b = json.loads(state_path.read_text(encoding="utf-8"))

        runs_path = (agent_factory.agents_root() / agent_id / "runs.jsonl").resolve()
        runs = _read_jsonl(runs_path)
        calls = _read_jsonl(oracle_window.calls_path())
        decisions = _read_jsonl(journal_path())

        sandbox_file = (agent_factory.agents_root() / agent_id / "sandbox" / "after_resume.txt").resolve()

        has_pause_event = any(
            (str(r.get("event") or "") == "pause")
            and (int(r.get("step_index") or 0) == 1)
            and (str(r.get("request_id") or "") == request_id)
            for r in runs
        )
        has_resume_event = any(
            (str(r.get("event") or "") == "resume")
            and (int(r.get("from_step") or 0) == 1)
            and str(r.get("by") or "").lower().startswith("ester")
            for r in runs
        )
        has_agent_resume_decision = any(
            str(r.get("action_kind") or "") == "agent.resume" and bool(r.get("allowed"))
            for r in decisions
        )
        has_call_link = any(str(r.get("request_id") or "") == request_id for r in calls)

        ok = (
            bool(run_a.get("ok"))
            and bool(run_a.get("paused"))
            and (str(run_a.get("pause_reason") or "") == "pending_oracle")
            and bool(request_id)
            and bool(state_a)
            and (str(state_a.get("status") or "") == "paused")
            and (str(state_a.get("paused_reason") or "") == "pending_oracle")
            and (int(state_a.get("next_step_index") or 0) == 1)
            and bool(approve.get("ok"))
            and bool(resume.get("ok"))
            and bool(resume.get("resumed"))
            and (str((resume or {}).get("status") or "") == "done")
            and bool(state_b)
            and (str(state_b.get("status") or "") == "done")
            and (int(state_b.get("next_step_index") or 0) >= 3)
            and bool(sandbox_file.exists())
            and has_pause_event
            and has_resume_event
            and has_agent_resume_decision
            and has_call_link
        )

        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "agent_id": agent_id,
            "request_id": request_id,
            "run_a": run_a,
            "approve": approve,
            "resume": resume,
            "state_path": str(state_path),
            "state_a": state_a,
            "state_b": state_b,
            "runs_path": str(runs_path),
            "has_pause_event": has_pause_event,
            "has_resume_event": has_resume_event,
            "has_agent_resume_decision": has_agent_resume_decision,
            "has_call_link": has_call_link,
            "sandbox_file_exists": bool(sandbox_file.exists()),
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0 if ok else 2
    finally:
        cur = oracle_window.current_window()
        if bool(cur.get("open")) and str(cur.get("window_id") or "").strip():
            oracle_window.close_window(str(cur.get("window_id") or ""), actor="ester:smoke", reason="cleanup")
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
