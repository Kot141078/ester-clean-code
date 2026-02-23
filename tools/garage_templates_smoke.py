# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.companion import outbox
from modules.garage import agent_runner
from modules.garage.templates import list_templates
from modules.volition.journal import journal_path
from tools.garage_make_agent import create_from_template


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    n = 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except Exception:
        pass
    return {}


def _strict_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    out = {"steps": []}
    for row in list(plan.get("steps") or []):
        step = dict(row or {})
        args = dict(step.get("args") or {})
        step_out = {"action_id": str(step.get("action_id") or ""), "args": args}
        step_out["budgets"] = {"max_actions": 4, "max_work_ms": 2200, "window": 60, "est_work_ms": 220}
        out["steps"].append(step_out)
    return out


def _run_template_once(template_id: str, owner: str) -> Dict[str, Any]:
    create_rep = create_from_template(
        template_id=template_id,
        name=f"smoke.run.{template_id.replace('.', '_')}",
        goal=f"Smoke run for {template_id}",
        owner=owner,
        dry_run=False,
    )
    if not create_rep.get("ok"):
        return {"ok": False, "stage": "create", "template_id": template_id, "create": create_rep}

    plan_path = Path(str(create_rep.get("plan_path") or "")).resolve()
    plan = _strict_plan(_load_json(plan_path))
    jid_before = _count_jsonl(journal_path())
    outbox_before = _count_jsonl(outbox.messages_path())
    run_rep = agent_runner.run_once(
        str(create_rep.get("agent_id") or ""),
        plan,
        {"intent": f"garage_templates_smoke:{template_id}"},
    )
    jid_after = _count_jsonl(journal_path())
    outbox_after = _count_jsonl(outbox.messages_path())
    jid_delta = max(0, jid_after - jid_before)
    outbox_delta = max(0, outbox_after - outbox_before)
    ok = bool(run_rep.get("ok")) and jid_delta >= 3 and outbox_delta >= 1
    return {
        "ok": ok,
        "template_id": template_id,
        "create": create_rep,
        "run": run_rep,
        "journal_delta": jid_delta,
        "outbox_delta": outbox_delta,
    }


def _oracle_default_safe(run_row: Dict[str, Any]) -> bool:
    run = dict(run_row.get("run") or {})
    saw_oracle = False
    for step in list(run.get("steps") or []):
        action_id = str((step or {}).get("action_id") or "")
        if action_id != "oracle.openai.call":
            continue
        saw_oracle = True
        result = dict((step or {}).get("result") or {})
        if bool(result.get("network_attempted")):
            return False
    if not saw_oracle:
        return True
    return True


def main() -> int:
    old_slot = os.environ.get("ESTER_VOLITION_SLOT")
    old_net = os.environ.get("ESTER_ALLOW_OUTBOUND_NETWORK")
    os.environ["ESTER_VOLITION_SLOT"] = "A"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "0"
    owner = "tools.garage_templates_smoke"

    try:
        rows = list_templates()
        template_ids = [str(r.get("id") or "") for r in rows if str(r.get("id") or "").strip()]
        template_ids = sorted(template_ids)

        creations: List[Dict[str, Any]] = []
        create_ok = True
        for tid in template_ids:
            rep = create_from_template(
                template_id=tid,
                name=f"smoke.create.{tid.replace('.', '_')}",
                goal=f"Dry creation for {tid}",
                owner=owner,
                dry_run=True,
            )
            plan_path = Path(str(rep.get("plan_path") or "")).resolve()
            path = Path(str(rep.get("path") or "")).resolve()
            rep["path_exists"] = path.exists()
            rep["plan_exists"] = plan_path.exists()
            if (not bool(rep.get("ok"))) or (not rep["path_exists"]) or (not rep["plan_exists"]):
                create_ok = False
            creations.append(rep)

        builder_run = _run_template_once("builder.v1", owner)
        reviewer_run = _run_template_once("reviewer.v1", owner)
        oracle_run = _run_template_once("oracle.v1", owner)
        oracle_safe = _oracle_default_safe(oracle_run)

        ok = (
            len(template_ids) >= 8
            and create_ok
            and bool(builder_run.get("ok"))
            and bool(reviewer_run.get("ok"))
            and bool(oracle_run.get("ok"))
            and oracle_safe
        )

        out = {
            "ok": ok,
            "templates_total": len(template_ids),
            "template_ids": template_ids,
            "creations": creations,
            "run_builder": builder_run,
            "run_reviewer": reviewer_run,
            "run_oracle_default": oracle_run,
            "oracle_default_safe": oracle_safe,
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0 if ok else 2
    finally:
        if old_slot is None:
            os.environ.pop("ESTER_VOLITION_SLOT", None)
        else:
            os.environ["ESTER_VOLITION_SLOT"] = old_slot
        if old_net is None:
            os.environ.pop("ESTER_ALLOW_OUTBOUND_NETWORK", None)
        else:
            os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = old_net


if __name__ == "__main__":
    raise SystemExit(main())

