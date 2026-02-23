# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.garage import agent_factory, agent_runner
from modules.volition.journal import journal_path


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    n = 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def _tail_jsonl(path: Path, limit: int) -> list[dict]:
    if (not path.exists()) or limit <= 0:
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
    return rows[-limit:]


def main() -> int:
    os.environ["ESTER_VOLITION_SLOT"] = "A"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "0"

    content = "hello_builder: agent os smoke"
    expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    spec = {
        "name": "hello_builder",
        "goal": "Write hello file and verify hash in sandbox",
        "allowed_actions": ["files.sandbox_write", "files.sha256_verify", "memory.add_note"],
        "budgets": {"max_actions": 6, "max_work_ms": 4000, "window": 60, "est_work_ms": 250},
        "owner": "tools.agent_os_smoke",
        "oracle_policy": {"allow_remote": False},
    }
    create_rep = agent_factory.create_agent(spec)
    if not create_rep.get("ok"):
        print(json.dumps({"ok": False, "error": "create_failed", "create": create_rep}, ensure_ascii=True, indent=2))
        return 2

    agent_id = str(create_rep.get("agent_id") or "")
    plan = {
        "steps": [
            {
                "action_id": "files.sandbox_write",
                "args": {"relpath": "hello.txt", "content": content},
            },
            {
                "action_id": "files.sha256_verify",
                "args": {"relpath": "hello.txt", "expected_sha256": expected_hash},
            },
            {
                "action_id": "memory.add_note",
                "args": {
                    "text": "agent_os_smoke: hello_builder completed",
                    "tags": ["iter29", "agent_os", "smoke"],
                    "source": "tools.agent_os_smoke",
                },
            },
        ]
    }

    jp = journal_path()
    before = _count_lines(jp)
    run_rep = agent_runner.run_once(agent_id, plan, {"intent": "agent_os_smoke"})
    after = _count_lines(jp)
    delta = max(0, after - before)

    step1 = {}
    if isinstance(run_rep.get("steps"), list) and run_rep.get("steps"):
        step1 = dict((run_rep.get("steps") or [{}])[0].get("result") or {})
    stored_path = str(step1.get("stored_path") or "")
    file_ok = bool(stored_path and Path(stored_path).exists())
    hash_ok = bool((run_rep.get("steps") or [{}, {}])[1].get("ok")) if len(run_rep.get("steps") or []) >= 2 else False
    oracle_used = any(
        str((row or {}).get("action_id") or "").strip() == "oracle.openai.call"
        for row in list(run_rep.get("steps") or [])
    )
    tail = _tail_jsonl(jp, max(1, delta + 2))
    chain_id = str(run_rep.get("chain_id") or "")
    chain_rows = [r for r in tail if str(r.get("chain_id") or "") == chain_id]
    journal_allow_reason_ok = any(bool(r.get("allowed")) and str(r.get("reason_code") or "").strip() for r in chain_rows)

    ok = bool(run_rep.get("ok")) and file_ok and hash_ok and (delta >= 3) and (not oracle_used) and journal_allow_reason_ok
    out = {
        "ok": ok,
        "agent_id": agent_id,
        "create": create_rep,
        "run": run_rep,
        "stored_path_exists": file_ok,
        "hash_ok": hash_ok,
        "oracle_used": oracle_used,
        "journal_allow_reason_ok": journal_allow_reason_ok,
        "journal_path": str(jp),
        "journal_added": delta,
    }
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    old_slot = os.environ.get("ESTER_VOLITION_SLOT")
    old_net = os.environ.get("ESTER_ALLOW_OUTBOUND_NETWORK")
    try:
        raise SystemExit(main())
    finally:
        if old_slot is None:
            os.environ.pop("ESTER_VOLITION_SLOT", None)
        else:
            os.environ["ESTER_VOLITION_SLOT"] = old_slot
        if old_net is None:
            os.environ.pop("ESTER_ALLOW_OUTBOUND_NETWORK", None)
        else:
            os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = old_net
