# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.thinking import action_registry
from modules.volition.volition_gate import VolitionContext


def _truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def _read_prompt(text: str, file_path: str) -> str:
    if str(file_path or "").strip():
        p = Path(file_path).resolve()
        return p.read_text(encoding="utf-8", errors="replace")
    return str(text or "")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Run single llm.remote.call via ActionRegistry.")
    ap.add_argument("--purpose", required=True)
    ap.add_argument("--prompt-text", default="")
    ap.add_argument("--prompt-file", default="")
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--model", default="")
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--window-id", default="")
    args = ap.parse_args(argv)

    if (not str(args.prompt_text or "").strip()) and (not str(args.prompt_file or "").strip()):
        out = {"ok": False, "error": "prompt_required"}
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 2

    if not _truthy(os.getenv("ESTER_ORACLE_CONFIRM", "0")):
        out = {
            "ok": False,
            "error": "oracle_confirmation_required",
            "hint": "Set ESTER_ORACLE_CONFIRM=1 to allow this tool to proceed.",
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 2

    prompt = _read_prompt(str(args.prompt_text or ""), str(args.prompt_file or ""))
    payload = {
        "prompt": prompt,
        "model": str(args.model or ""),
        "max_tokens": int(args.max_tokens),
        "temperature": float(args.temperature),
        "purpose": str(args.purpose or "").strip(),
        "window_id": str(args.window_id or "").strip(),
        "actor": "tool.oracle_call_once",
        "plan_id": "tool_oracle_call_once",
        "step_index": 0,
    }
    args_digest = hashlib.sha256(
        json.dumps(
            {k: payload[k] for k in ["model", "max_tokens", "temperature", "purpose", "window_id"]},
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    ctx = VolitionContext(
        chain_id="oracle_call_" + uuid.uuid4().hex[:10],
        step="action",
        actor="tool.oracle_call_once",
        intent=str(args.purpose or "oracle_call"),
        action_kind="llm.remote.call",
        needs=["network", "oracle"],
        budgets={"max_actions": 1, "max_work_ms": 20000, "window": 60, "est_work_ms": 500},
        metadata={
            "agent_id": "",
            "plan_id": "tool_oracle_call_once",
            "step_index": 0,
            "action_id": "llm.remote.call",
            "args_digest": args_digest,
            "policy_hit": "oracle_window",
            "oracle_window": str(args.window_id or ""),
        },
    )
    rep = action_registry.invoke_guarded("llm.remote.call", payload, ctx=ctx)
    out = dict(rep if isinstance(rep, dict) else {"ok": False, "error": "invalid_reply"})
    if bool(out.get("ok")):
        out["text"] = str(out.get("text") or "")[:800]
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if bool(out.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
