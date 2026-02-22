# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List

ALLOWED_LOCAL_ACTIONS = [
    "local.search",
    "local.extract",
    "local.crosscheck",
    "crystallize.fact",
    "crystallize.negative",
    "close.ticket",
]
ALLOWED_WEB_ACTIONS = ["web.search"]


def _safe_int(value: Any, default: int, *, min_value: int = 0) -> int:
    try:
        out = int(value)
    except Exception:
        out = int(default)
    return max(min_value, out)


def _mode(value: str) -> str:
    raw = str(value or "local_only").strip().lower()
    return "web_allowed" if raw == "web_allowed" else "local_only"


def _ticket_fields(ticket: Dict[str, Any]) -> Dict[str, Any]:
    src = dict(ticket or {})
    budgets = dict(src.get("budgets") or {})
    max_docs = _safe_int(budgets.get("max_docs"), 12, min_value=1)
    max_depth = _safe_int(budgets.get("max_depth"), 2, min_value=1)
    max_hops = _safe_int(budgets.get("max_hops"), 2, min_value=1)
    max_work_ms = _safe_int(budgets.get("max_work_ms"), 1500, min_value=100)
    return {
        "ticket_id": str(src.get("ticket_id") or ""),
        "query": str(src.get("query") or "").strip(),
        "source": str(src.get("source") or "dialog"),
        "priority": float(src.get("priority") or 0.5),
        "max_docs": max_docs,
        "max_depth": max_depth,
        "max_hops": max_hops,
        "max_work_ms": max_work_ms,
    }


def canonical_json_hash(payload: Dict[str, Any]) -> str:
    body = json.dumps(dict(payload or {}), ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def plan_hash(plan: Dict[str, Any]) -> str:
    src = dict(plan or {})
    src.pop("created_ts", None)
    return canonical_json_hash(src)


def build_plan(ticket: Dict[str, Any], mode: str = "local_only") -> Dict[str, Any]:
    t = _ticket_fields(ticket)
    if not t["ticket_id"]:
        raise ValueError("ticket_id_required")
    if not t["query"]:
        raise ValueError("query_required")

    plan_mode = _mode(mode)
    steps: List[Dict[str, Any]] = []
    if plan_mode == "web_allowed":
        steps.append(
            {
                "action": "web.search",
                "args": {
                    "ticket_id": t["ticket_id"],
                    "query": t["query"],
                    "max_docs": min(8, t["max_docs"]),
                    "reason": "curiosity_planner",
                },
                "why": "optional_web_evidence_when_policy_allows",
            }
        )

    steps.extend(
        [
            {
                "action": "local.search",
                "args": {
                    "ticket_id": t["ticket_id"],
                    "query": t["query"],
                    "max_docs": t["max_docs"],
                    "max_depth": t["max_depth"],
                    "max_hops": t["max_hops"],
                    "source": t["source"],
                },
                "why": "collect_local_candidates",
            },
            {
                "action": "local.extract",
                "args": {
                    "ticket_id": t["ticket_id"],
                    "query": t["query"],
                    "top_k": min(12, t["max_docs"]),
                },
                "why": "extract_claim_candidates",
            },
            {
                "action": "local.crosscheck",
                "args": {
                    "ticket_id": t["ticket_id"],
                    "query": t["query"],
                    "min_sources": 2,
                },
                "why": "crosscheck_local_sources",
            },
            {
                "action": "crystallize.fact",
                "args": {
                    "ticket_id": t["ticket_id"],
                    "query": t["query"],
                    "source": t["source"],
                },
                "why": "write_fact_or_negative_with_evidence_l4w",
            },
            {
                "action": "close.ticket",
                "args": {
                    "ticket_id": t["ticket_id"],
                    "default_event": "resolve",
                },
                "why": "finish_ticket_lifecycle",
            },
        ]
    )

    out = {
        "schema": "ester.plan.v1",
        "plan_id": "",
        "title": f"curiosity:{t['ticket_id']}",
        "intent": "curiosity_research",
        "template_id": "curiosity_researcher",
        "initiative_id": t["ticket_id"],
        "steps": steps,
        "budgets": {
            "max_ms": t["max_work_ms"],
            "max_steps": max(1, len(steps)),
            "window_sec": _safe_int(os.getenv("ESTER_CURIOSITY_PLAN_WINDOW_SEC", "120"), 120, min_value=1),
        },
        "meta": {
            "ticket_id": t["ticket_id"],
            "ticket_source": t["source"],
            "priority": t["priority"],
            "planner_mode": plan_mode,
            "allowed_actions": list(ALLOWED_LOCAL_ACTIONS) + list(ALLOWED_WEB_ACTIONS),
        },
    }
    out["plan_id"] = "plan_curiosity_" + plan_hash(out)[:12]
    return out


__all__ = [
    "ALLOWED_LOCAL_ACTIONS",
    "ALLOWED_WEB_ACTIONS",
    "build_plan",
    "canonical_json_hash",
    "plan_hash",
]
