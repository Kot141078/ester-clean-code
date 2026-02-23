# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.runtime import oracle_window
from modules.thinking import action_registry
from modules.volition.journal import journal_path
from modules.volition.volition_gate import VolitionContext


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
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "0"
    os.environ["ESTER_ORACLE_ENABLE"] = "0"
    os.environ.pop("ESTER_ORACLE_CONFIRM", None)

    cur = oracle_window.current_window()
    if bool(cur.get("open")) and str(cur.get("window_id") or "").strip():
        oracle_window.close_window(str(cur.get("window_id")), actor="tools.oracle_smoke_deny", reason="ensure_closed")

    prompt = "oracle smoke deny"
    args_digest = hashlib.sha256(
        json.dumps(
            {"prompt": prompt, "purpose": "oracle_smoke_deny", "window_id": ""},
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    chain_id = "oracle_smoke_" + uuid.uuid4().hex[:10]
    payload = {
        "prompt": prompt,
        "purpose": "oracle_smoke_deny",
        "window_id": "",
        "actor": "tools.oracle_smoke_deny",
        "plan_id": chain_id,
        "step_index": 0,
    }
    ctx = VolitionContext(
        chain_id=chain_id,
        step="action",
        actor="tools.oracle_smoke_deny",
        intent="oracle smoke deny",
        action_kind="llm.remote.call",
        needs=["network", "oracle"],
        budgets={"max_actions": 1, "max_work_ms": 2000, "window": 60, "est_work_ms": 200},
        metadata={
            "agent_id": "",
            "plan_id": chain_id,
            "step_index": 0,
            "action_id": "llm.remote.call",
            "args_digest": args_digest,
            "policy_hit": "oracle_window",
            "oracle_window": "",
        },
    )

    before_journal = _read_jsonl(journal_path())
    before_calls = _read_jsonl(oracle_window.calls_path())
    rep = action_registry.invoke_guarded("llm.remote.call", payload, ctx=ctx)
    after_journal = _read_jsonl(journal_path())
    after_calls = _read_jsonl(oracle_window.calls_path())

    result_ok = (not bool(rep.get("ok"))) and str(rep.get("error") or "") == "oracle_window_closed"

    new_journal = after_journal[len(before_journal) :]
    has_deny_decision = any(
        (str(row.get("decision") or "").strip().lower() == "deny")
        and (str(row.get("policy_hit") or "").strip() in {"oracle_window_closed", "oracle_window"})
        for row in new_journal
    )

    new_calls = after_calls[len(before_calls) :]
    has_deny_call = any(
        (not bool(row.get("ok")))
        and str(row.get("error") or "").strip() == "oracle_window_closed"
        for row in new_calls
    )

    ok = bool(result_ok and has_deny_decision and has_deny_call)
    out = {
        "ok": ok,
        "result": rep,
        "deny_decision_found": has_deny_decision,
        "deny_call_found": has_deny_call,
        "journal_path": str(journal_path()),
        "calls_path": str(oracle_window.calls_path()),
    }
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
