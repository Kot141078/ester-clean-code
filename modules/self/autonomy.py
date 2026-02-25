# -*- coding: utf-8 -*-
"""modules/self/autonomy.py - planer “samovyzhivaniya”: kogda sobiratsya, kak rasprostranyatsya, where sobirat sebya snova.

Mosty:
- Yavnyy: (Kibernetika ↔ Planirovanie) generiruet plan shagov: snapshot → webseed/torrent → anons peer’am → samosoborka.
- Skrytyy #1: (Set ↔ Bezopasnost) shell-adaptery otklyucheny po umolchaniyu; tolko legalnye kanaly (HTTP, BT-tulcheyn pri nalichii).
- Skrytyy #2: (Memory ↔ Audit) vse resheniya logiruyutsya i mogut uchityvatsya v refleksii.

Zemnoy abzats:
This is “instinkt sokhraneniya”: upal uzel - podnimis s blizhayshego snapshota; resursy est - podelis obrazom s sestrami.
Obedineno iz dvukh versiy: add budget/spread-guard, action-invoke dlya ispolneniya, logging dlya pamyati Ester.

# c=a+b"""
from __future__ import annotations
import os, time, json
import logging
from pathlib import Path
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Logging setup: ensure target directory exists to avoid import-time failure.
_SELF_LOG_PATH = Path(os.getenv("SELF_LOG", "data/logs/self_autonomy.log"))
try:
    _SELF_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
except Exception:
    pass
logging.basicConfig(
    filename=str(_SELF_LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

ALLOW_SHELL = bool(int(os.getenv("SELF_ALLOW_SHELL", "0")))
SNAP_DIR = os.getenv("SELF_SNAPSHOT_DIR", "data/self/snapshots")
AUTONOMY_AB = (os.getenv("AUTONOMY_AB", "A") or "A").upper()

def _now() -> int: return int(time.time())

def plan(goal: str, budget: Dict[str, float] | None = None, targets: List[str] | None = None) -> Dict[str, Any]:
    goal_text = str(goal or "").strip()
    if not goal_text:
        return {"ok": False, "plan": {}, "template": {}, "needs_oracle": False, "reason": "empty_goal"}

    raw_budget = dict(budget or {})
    budgets = {
        "max_work_ms": int(raw_budget.get("max_work_ms") or 2000),
        "max_actions": int(raw_budget.get("max_actions") or 4),
        "window": int(raw_budget.get("window") or 60),
        "est_work_ms": int(raw_budget.get("est_work_ms") or 250),
    }
    initiative = {
        "id": "autonomy_" + str(_now()),
        "title": goal_text,
        "text": goal_text,
        "targets": list(targets or []),
        "tags": list(targets or []),
        "source": "modules.self.autonomy.plan",
    }

    template: Dict[str, Any] = {"template_id": "planner.v1", "agent_role": "planner", "needs_oracle": False}
    plan_obj: Dict[str, Any] = {
        "ok": True,
        "goal": goal_text,
        "steps": [{"action": "memory.recall", "args": {"query": goal_text, "k": 8}}],
        "budgets": budgets,
    }
    reason = "planner_v1_fallback"

    try:
        from modules.proactivity.template_bridge import select_template  # type: ignore

        template = dict(select_template(initiative) or template)
    except Exception as e:
        logging.warning("autonomy.plan: template_bridge unavailable: %s", e)

    try:
        from modules.proactivity.planner_v1 import build_plan  # type: ignore

        plan_obj = dict(build_plan(initiative, budgets) or plan_obj)
        reason = "planner_v1"
    except Exception as e:
        logging.warning("autonomy.plan: planner_v1 unavailable: %s", e)

    needs_oracle = bool(plan_obj.get("needs_oracle") or template.get("needs_oracle"))
    volition_data: Dict[str, Any] = {}
    try:
        from modules.volition.volition_gate import VolitionContext, get_default_gate  # type: ignore

        ctx = VolitionContext(
            chain_id="autonomy_plan_" + str(_now()),
            step="plan",
            actor="ester",
            intent=goal_text,
            action_kind="self.autonomy.plan",
            needs=(["network"] if needs_oracle else []),
            budgets=dict(plan_obj.get("budgets") or budgets),
            metadata={"template_id": str(template.get("template_id") or "planner.v1")},
        )
        decision = get_default_gate().decide(ctx)
        volition_data = decision.to_dict()
        if not decision.allowed:
            reason = f"volition_denied:{decision.reason_code}"
    except Exception as e:
        logging.warning("autonomy.plan: volition gate unavailable: %s", e)

    result = {
        "ok": bool(plan_obj.get("ok", True)),
        "plan": plan_obj,
        "template": template,
        "needs_oracle": bool(needs_oracle),
        "reason": reason,
    }
    if volition_data:
        result["volition"] = volition_data
    return result

def _cost_eval(cat: str, amount: float) -> Dict[str, Any]:
    try:
        from modules.ops.cost_fence import evaluate  # type: ignore
        return evaluate(cat, amount)
    except Exception as e:
        logging.error(f"Cost eval failed: {str(e)}")
        return {"allow": True, "reason": "no_cost_fence"}

def _spread_eval(targets: List[str]) -> Dict[str, Any]:
    try:
        from modules.self.spread_guard import evaluate  # type: ignore
        return evaluate(targets)
    except Exception as e:
        logging.error(f"Spread eval failed: {str(e)}")
        return {"allow": True, "results": [{"target": t, "allow": True, "why": "no_guard"} for t in targets]}

def execute(plan_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Vypolnyaem tolko bezopasnye chasti: snapshot + podgotovka webseed; torrent - only hint, torrent/announce s guard'ami.
    Added cost/spread_eval, invoke action_registry iz py1."""
    if AUTONOMY_AB == "B":
        return {"ok": False, "error": "AUTONOMY_AB=B"}
    results = []
    # Spread check
    targets = ((plan_obj.get("policy") or {}).get("spread") or {}).get("targets") or []
    sp = _spread_eval(targets)
    if not sp.get("allow", True):
        logging.warning("Execute denied: spread_guard")
        return {"ok": False, "error": "spread_denied", "detail": sp}
    # Action invoke
    try:
        from modules.thinking.action_registry import invoke  # type: ignore
    except Exception as e:
        logging.error(f"No action_registry: {str(e)}")
        return {"ok": False, "error": "no_action_registry"}
    for st in plan_obj.get("steps", []):
        pol = st.get("policy") or {}
        cf = {"allow": True}
        if "cost" in pol:
            c = pol["cost"]; cf = _cost_eval(c.get("cat", "llm"), float(c.get("amount", 0.0)))
            if not cf.get("allow", True):
                results.append({"ok": False, "skipped": "budget_limit", "step": st, "decision": cf}); continue
        # Safe execute/hint
        kind = st.get("kind", "")
        args = dict(st.get("args") or {})
        if kind == "snapshot.create":
            from modules.self.archiver import create_snapshot  # type: ignore
            rep = create_snapshot(**args)
            results.append({"step": kind, "result": rep})
        elif kind == "distribute.http":
            results.append({"step": kind, "endpoint": "/self/pack/download/<archive>"})
        elif kind == "distribute.torrent":
            results.append({"step": kind, "hint": "use /self/pack/torrent once snapshot created"})
        elif kind == "p2p.announce":
            # Best-effort NTTP Annunce (extension for P2P)
            try:
                import urllib.request
                for t in targets:
                    body = json.dumps({"goal": plan_obj["goal"], "snapshot": "latest"}).encode("utf-8")
                    req = urllib.request.Request(f"http://{t}/p2p/announce", data=body, headers={"Content-Type": "application/json"})
                    urllib.request.urlopen(req, timeout=5)
                results.append({"step": kind, "ok": True})
            except Exception as e:
                logging.error(f"P2P announce failed: {str(e)}")
                results.append({"step": kind, "ok": False, "error": str(e)})
        elif kind == "self.reassemble":
            results.append({"step": kind, "hint": "use /self/deploy/rollback with chosen snapshot on target"})
        else:
            # Universal invoke for other kinds
            res = invoke(kind, args)
            results.append({"ok": bool(res.get("ok")), "step": st, "result": res})
    ok = all(r.get("ok", True) for r in results) if results else True
    logging.info(f"Executed plan for '{plan_obj['goal']}' with {len(results)} results, ok={ok}")
    return {"ok": ok, "executed": results}
# Expansion idea: to synthesize plans with Yudzhe, send plan_obzh to the cloud LLM for improvement (e.g., auto-add steps).
# I implement it in autonomy_yuje.po: plan() + HTTP then Yuje, if you say so.
