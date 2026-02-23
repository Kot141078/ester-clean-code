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


def _find_last(rows: List[Dict[str, Any]], request_id: str, status: str) -> Dict[str, Any]:
    for row in reversed(rows):
        if str(row.get("request_id") or "").strip() != str(request_id or "").strip():
            continue
        if str(row.get("status") or "").strip() != str(status or "").strip():
            continue
        return row
    return {}


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_oracle_agent_smoke_")).resolve()
    persist_dir = (tmp_root / "persist").resolve()
    garage_root = (tmp_root / "garage").resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)
    garage_root.mkdir(parents=True, exist_ok=True)

    old_env = {
        "PERSIST_DIR": os.environ.get("PERSIST_DIR"),
        "GARAGE_ROOT": os.environ.get("GARAGE_ROOT"),
        "ESTER_ORACLE_ENABLE": os.environ.get("ESTER_ORACLE_ENABLE"),
        "ESTER_ALLOW_OUTBOUND_NETWORK": os.environ.get("ESTER_ALLOW_OUTBOUND_NETWORK"),
        "ESTER_VOLITION_SLOT": os.environ.get("ESTER_VOLITION_SLOT"),
        "ESTER_ORACLE_DRY_RUN_DISABLE": os.environ.get("ESTER_ORACLE_DRY_RUN_DISABLE"),
        "ESTER_VOLITION_ALLOWED_HOURS": os.environ.get("ESTER_VOLITION_ALLOWED_HOURS"),
    }

    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["GARAGE_ROOT"] = str(garage_root)
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "1"
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_ORACLE_DRY_RUN_DISABLE"] = "0"
    os.environ["ESTER_VOLITION_ALLOWED_HOURS"] = "00:00-23:59"
    os.environ["ESTER_ORACLE_ENABLE"] = "0"

    chain_id = "chain_oracle_agent_smoke"
    request_id = ""
    try:
        create = agent_factory.create_agent(
            {
                "name": "oracle_agent_smoke",
                "goal": "Validate oracle-by-agent request flow",
                "template_id": "oracle.v1",
                "capabilities": ["cap.oracle.remote.call"],
                "allowed_actions": ["llm.remote.call"],
                "budgets": {"max_actions": 20, "max_work_ms": 20000, "window": 120, "est_work_ms": 200},
                "owner": "tools.oracle_by_agent_smoke",
                "oracle_policy": {"allow_remote": True},
            }
        )
        if not bool(create.get("ok")):
            print(json.dumps({"ok": False, "error": "create_failed", "create": create}, ensure_ascii=True, indent=2))
            return 2
        agent_id = str(create.get("agent_id") or "")
        plan = {
            "steps": [
                {
                    "action_id": "llm.remote.call",
                    "args": {
                        "prompt": "oracle_by_agent_smoke_ping",
                        "purpose": "oracle_by_agent_smoke",
                        "model": "gpt-4o-mini",
                        "max_tokens": 32,
                        "dry_run": True,
                    },
                }
            ]
        }

        # A) oracle disabled -> pending request, no call.
        os.environ["ESTER_VOLITION_SLOT"] = "B"
        run_a = agent_runner.run_once(agent_id, plan, {"intent": "oracle_by_agent_smoke_a", "chain_id": chain_id})
        request_id = str(run_a.get("pending_request_id") or "")
        calls_a = _read_jsonl(oracle_window.calls_path())

        # B) oracle enabled but still not approved -> still pending, no network/call.
        os.environ["ESTER_ORACLE_ENABLE"] = "1"
        os.environ["ESTER_VOLITION_SLOT"] = "B"
        run_b = agent_runner.run_once(agent_id, plan, {"intent": "oracle_by_agent_smoke_b", "chain_id": chain_id})
        request_id_b = str(run_b.get("pending_request_id") or "")
        calls_b = _read_jsonl(oracle_window.calls_path())

        # C) Ester approves request and opens window; agent resumes and executes dry-run call.
        approve = oracle_requests.approve_request(
            request_id,
            actor="ester:smoke",
            reason="oracle_by_agent_smoke_approve",
            ttl_sec=60,
            budgets={"max_calls": 1, "max_est_tokens_in_total": 1000, "max_tokens_out_total": 100},
            allow_agents=True,
        )
        os.environ["ESTER_VOLITION_SLOT"] = "B"
        run_c = agent_runner.run_once(agent_id, plan, {"intent": "oracle_by_agent_smoke_c", "chain_id": chain_id})
        calls_c = _read_jsonl(oracle_window.calls_path())
        req_rows = _read_jsonl((persist_dir / "oracle" / "requests.jsonl").resolve())
        win_rows = _read_jsonl((persist_dir / "oracle" / "windows.jsonl").resolve())

        pending_row = _find_last(req_rows, request_id, "pending")
        approved_row = _find_last(req_rows, request_id, "approved")
        approved_window_id = str((approved_row or {}).get("window_id") or "")
        win_open_row = {}
        for row in reversed(win_rows):
            if str(row.get("event") or "") != "open":
                continue
            if str(row.get("window_id") or "") != approved_window_id:
                continue
            approved_ids = [str(x) for x in list(((row.get("meta") or {}).get("approved_request_ids") or []))]
            if request_id in approved_ids:
                win_open_row = row
                break

        call_row = {}
        for row in reversed(calls_c):
            if str(row.get("request_id") or "") != request_id:
                continue
            if bool(row.get("ok")):
                call_row = row
                break

        step_c = {}
        if isinstance(run_c.get("steps"), list) and run_c.get("steps"):
            step_c = dict((run_c.get("steps") or [{}])[0].get("result") or {})

        ok = (
            bool(run_a.get("ok"))
            and bool(run_a.get("paused"))
            and (str(run_a.get("pause_reason") or "") == "pending_oracle")
            and bool(request_id)
            and (len(calls_a) == 0)
            and bool(run_b.get("ok"))
            and bool(run_b.get("paused"))
            and (str(run_b.get("pause_reason") or "") == "pending_oracle")
            and (request_id_b == request_id)
            and (len(calls_b) == 0)
            and bool(approve.get("ok"))
            and bool(run_c.get("ok"))
            and (not bool(run_c.get("paused")))
            and bool(step_c.get("ok"))
            and bool(step_c.get("dry_run"))
            and (not bool(step_c.get("network_attempted")))
            and (str(step_c.get("request_id") or "") == request_id)
            and bool(pending_row)
            and bool(approved_row)
            and bool(win_open_row)
            and bool(call_row)
        )

        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "request_id": request_id,
            "run_a": run_a,
            "run_b": run_b,
            "approve": approve,
            "run_c": run_c,
            "pending_row_found": bool(pending_row),
            "approved_row_found": bool(approved_row),
            "window_open_event_found": bool(win_open_row),
            "call_row_found": bool(call_row),
            "calls_count": len(calls_c),
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0 if ok else 2
    finally:
        cur = oracle_window.current_window()
        if bool(cur.get("open")) and str(cur.get("window_id") or "").strip():
            oracle_window.close_window(str(cur.get("window_id") or ""), actor="ester:smoke", reason="cleanup")
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
