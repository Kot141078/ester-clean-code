# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.runtime import oracle_requests
from modules.thinking import action_registry


def _as_bool(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Approve one oracle request and open window via Ester actor.")
    ap.add_argument("--request-id", required=True)
    ap.add_argument("--reason", default="approved_by_ester")
    ap.add_argument("--ttl", type=int, default=60)
    ap.add_argument("--max-calls", type=int, default=1)
    ap.add_argument("--max-tokens-in", type=int, default=4000)
    ap.add_argument("--max-tokens-out", type=int, default=800)
    ap.add_argument("--max-wall-ms-per-call", type=int, default=20000)
    ap.add_argument("--allow-agents", default="1")
    ap.add_argument("--actor", default="ester:core")
    ap.add_argument("--resume-agent", default="0", help="0/1: also trigger agent.resume after approval")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    request_id = str(args.request_id or "").strip()
    resume_requested = _as_bool(args.resume_agent)
    if args.dry_run:
        rep = oracle_requests.get_request(request_id)
        out = {
            "ok": bool(rep.get("ok")),
            "dry_run": True,
            "request_id": request_id,
            "request": rep.get("request"),
            "would_open_window": bool(rep.get("ok")),
            "actor": str(args.actor or "ester:core"),
            "allow_agents": _as_bool(args.allow_agents),
            "budgets": {
                "ttl_sec": int(args.ttl),
                "max_calls": int(args.max_calls),
                "max_est_tokens_in_total": int(args.max_tokens_in),
                "max_tokens_out_total": int(args.max_tokens_out),
                "max_wall_ms_per_call": int(args.max_wall_ms_per_call),
            },
            "resume_requested": bool(resume_requested),
        }
        if bool(resume_requested) and bool(rep.get("ok")):
            req = dict(rep.get("request") or {})
            agent_id = str(req.get("agent_id") or "")
            if agent_id:
                out["resume_preview"] = action_registry.invoke(
                    "agent.resume",
                    {
                        "agent_id": agent_id,
                        "reason": "oracle approved (dry-run)",
                        "dry_run": True,
                        "actor": str(args.actor or "ester:core"),
                    },
                )
        if not rep.get("ok"):
            out["error"] = rep.get("error")
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0 if bool(out.get("ok")) else 2

    rep = oracle_requests.approve_request(
        request_id,
        actor=str(args.actor or "ester:core"),
        reason=str(args.reason or ""),
        ttl_sec=int(args.ttl),
        budgets={
            "max_calls": int(args.max_calls),
            "max_est_tokens_in_total": int(args.max_tokens_in),
            "max_tokens_out_total": int(args.max_tokens_out),
            "max_wall_ms_per_call": int(args.max_wall_ms_per_call),
        },
        allow_agents=_as_bool(args.allow_agents),
    )
    out: dict = {"ok": bool(rep.get("ok")), "approve": rep, "resume_requested": bool(resume_requested)}
    if bool(rep.get("ok")) and bool(resume_requested):
        req_row = dict(rep.get("request") or {})
        if not req_row:
            get_rep = oracle_requests.get_request(request_id)
            req_row = dict(get_rep.get("request") or {})
        agent_id = str(req_row.get("agent_id") or "").strip()
        if not agent_id:
            out["resume"] = {"ok": False, "error": "agent_id_missing_in_request", "resumed": False}
            out["ok"] = False
        else:
            resume_rep = action_registry.invoke(
                "agent.resume",
                {
                    "agent_id": agent_id,
                    "reason": "oracle approved",
                    "dry_run": False,
                    "actor": str(args.actor or "ester:core"),
                },
            )
            out["resume"] = resume_rep
            out["ok"] = bool(out["ok"]) and bool((resume_rep or {}).get("ok"))
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if bool(out.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
