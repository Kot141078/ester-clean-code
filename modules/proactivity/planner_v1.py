# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, Dict, List


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _contains_any(text: str, words: List[str]) -> bool:
    low = str(text or "").lower()
    return any(w in low for w in words)


def _text_blob(initiative: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("title", "text", "kind", "source", "priority"):
        val = str(initiative.get(key) or "").strip()
        if val:
            parts.append(val)
    for tag in list(initiative.get("tags") or []):
        sval = str(tag or "").strip()
        if sval:
            parts.append(sval)
    return " | ".join(parts)


def _oracle_needed(initiative: Dict[str, Any]) -> bool:
    blob = _text_blob(initiative)
    return _contains_any(blob, ["oracle", "openai", "remote", "internet", "web search", "llm"])


def build_plan(initiative: Dict[str, Any], budgets: Dict[str, Any]) -> Dict[str, Any]:
    src = dict(initiative or {})
    b = dict(budgets or {})
    max_work_ms = max(200, _as_int(b.get("max_work_ms"), 2000))
    max_actions = max(1, _as_int(b.get("max_actions"), 4))
    per_step = max(100, min(400, int(max_work_ms / max_actions)))

    initiative_id = str(src.get("id") or ("initiative_" + uuid.uuid4().hex[:8]))
    title = str(src.get("title") or "initiative")
    text = str(src.get("text") or title)
    query = title if len(title) >= 4 else text[:64]
    needs_oracle = _oracle_needed(src)
    artifact_relpath = f"proactivity/{initiative_id}.txt"
    artifact_content = (
        f"initiative_id={initiative_id}\n"
        f"title={title}\n"
        f"text={text}\n"
        f"query={query}\n"
        f"needs_oracle={str(bool(needs_oracle)).lower()}\n"
    )
    artifact_sha256 = hashlib.sha256(artifact_content.encode("utf-8")).hexdigest()

    # Planner v1 is deterministic and offline-first: known safe actions only.
    steps: List[Dict[str, Any]] = [
        {
            "action": "memory.add_note",
            "args": {
                "text": f"planner_v1:start:{initiative_id}:{title}",
                "tags": ["proactivity", "planner_v1", "start"],
                "source": "modules.proactivity.planner_v1",
            },
            "why": "agent_step:memory.add_note",
        },
        {
            "action": "files.sandbox_write",
            "args": {"relpath": artifact_relpath, "content": artifact_content},
            "why": "agent_step:files.sandbox_write",
        },
        {
            "action": "files.sha256_verify",
            "args": {"relpath": artifact_relpath, "expected_sha256": artifact_sha256},
            "why": "agent_step:files.sha256_verify",
        },
        {
            "action": "memory.add_note",
            "args": {
                "text": f"planner_v1:artifact_ready:{initiative_id}:{artifact_relpath}",
                "tags": ["proactivity", "planner_v1", "ready"],
                "source": "modules.proactivity.planner_v1",
            },
            "why": "agent_step:memory.add_note",
        },
    ]

    plan_id = "plan_" + hashlib.sha1(f"{initiative_id}|{title}|{int(time.time())}".encode("utf-8")).hexdigest()[:12]
    return {
        "ok": True,
        "schema": "ester.plan.v1",
        "plan_id": plan_id,
        "created_ts": int(time.time()),
        "initiative_id": initiative_id,
        "title": title,
        "intent": "proactivity_enqueue",
        "needs_oracle": bool(needs_oracle),
        "steps": steps,
        "budgets": {
            "max_ms": max_work_ms,
            "max_steps": max_actions,
            "window_sec": max(1, _as_int(b.get("window"), 60)),
            "oracle_window": ("required" if needs_oracle else "not_required"),
        },
    }


__all__ = ["build_plan"]
