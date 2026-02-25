# -*- coding: utf-8 -*-
"""modules/thinking/cascade_planner.py — kaskadnoe prakticheskoe myshlenie:
tsel → razbor → strategii (build/buy/earn/spread) → deystviya → byudzhety i zadaniya.

Mosty:
- Yavnyy: (Myshlenie ↔ Operatsii) vydaem ispolnimye shagi i zadaniya (cheloveku i Ester).
- Skrytyy #1: (Infoteoriya ↔ Ekonomika) uchityvaem koshelek/porogi/odobreniya.
- Skrytyy #2: (Search ↔ Zakupki) dlya BUY shagov mozhno podskazat postavschikov (cherez web_search).

Zemnoy abzats:
Po-zemnomu: “what nuzhno → kupit/sdelat/zarabotat/rasprostranit → who what to do → skolko deneg i kogda spisat.”

# c=a+b"""
from __future__ import annotations
import os, re, time
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

CASCADE_AB = (os.getenv("CASCADE_AB","A") or "A").upper()

def _infer_need(goal: str) -> Dict[str, Any]:
    g = goal.lower()
    need_video = any(k in g for k in ("video","camera","kamera","youtube","rolik"))
    need_gpu   = "gpu" in g or "videokarta" in g
    need_data  = any(k in g for k in ("dataset","dataset","dannye"))
    need_staff = any(k in g for k in ("nanyat","assistent","operator","moderator"))
    return {"video":need_video, "gpu":need_gpu, "data":need_data, "staff":need_staff}

def _strategy(goal: str, hints: Dict[str, Any]) -> List[str]:
    S: List[str] = []
    # pravilo: esli nuzhny vneshnie resursy → BUY; esli est vremya/kod → BUILD; esli ne khvataet sredstv → EARN; dlya rashshirniya moschnostey seti → SPREAD
    if any(hints.values()): S.append("BUY")
    S.append("BUILD")
    if "gpu" in goal.lower() or "rasshirit" in goal.lower(): S.append("SPREAD")
    S.append("EARN")
    # unikalnost/poryadok
    out=[]; [out.append(x) for x in S if x not in out]
    return out

def _suggest_suppliers(q: str, k: int = 3) -> List[Dict[str,str]]:
    try:
        from modules.web_search import search_web  # type: ignore
        hits = search_web(q, topk=k) or []
        return hits
    except Exception:
        return []

def make_plan(goal: str, budget: float | None = None) -> Dict[str, Any]:
    if not goal.strip():
        return {"ok": False, "error": "goal required"}
    hints = _infer_need(goal)
    strat = _strategy(goal, hints)
    steps: List[Dict[str, Any]] = []
    assignments: List[Dict[str, Any]] = []

    # BUY
    if "BUY" in strat:
        # grubye evristiki
        items: List[Dict[str,Any]] = []
        if hints["video"]:
            items.append({"name":"USB camera 1080p", "qty":1, "budget":120, "tags":["video","sensor"]})
        if hints["gpu"]:
            items.append({"name":"GPU 12GB VRAM (used OK)", "qty":1, "budget":400, "tags":["compute","gpu"]})
        if hints["data"]:
            items.append({"name":"dataset: domain-specific", "qty":1, "budget":0, "tags":["data","free-first"]})
        if items:
            suppliers = _suggest_suppliers("buy " + ", ".join(i["name"] for i in items), k=3)
            steps.append({"kind":"ops.shopping.plan", "items": items, "suppliers": suppliers})

    # BUILD
    if "BUILD" in strat:
        steps.append({"kind":"self.codegen", "idea":"create/improve a module for a task", "guard":"SELF_CODE_ALLOW_APPLY gate"})

    # SPREAD (legalno)
    if "SPREAD" in strat:
        steps.append({"kind":"network.spread", "note":"distribute legal components among sisters (P2P), update index/catalog"})

    # EARN (bezopasnye mikro-podrabotki)
    if "EARN" in strat:
        steps.append({"kind":"earn.micro", "note":"prepare instructions for microtasks/grants (without personal income and secrets), calculate income"})

    # Assignments to the “person” (Dad): only if purchases are clearly formed
    for st in steps:
        if st.get("kind") == "ops.shopping.plan":
            for it in st.get("items") or []:
                assignments.append({"who":"papa","type":"buy","title":f"Kupit: {it['name']} x{it['qty']}", "budget":it.get("budget",0), "meta":{"tags":it.get("tags",[])}})

    plan = {"ok": True, "goal": goal, "strategies": strat, "steps": steps, "assignments": assignments, "ts": int(time.time())}
    return plan

def execute(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Execution TOLKO “bezopasnye vnutrennie” steps:
    - self.codegen → sozdaem chernovik skeleta
    - ops.shopping.plan → sozdaem zadaniya i, pri zhelanii, rezervy (ne spisyvaem)
    Denezhnye operatsii ne provodim (oni idut cherez /economy ruchkami/odobreniem)."""
    if CASCADE_AB == "B":
        return {"ok": True, "executed": [], "note":"A/B=B: dry-only"}
    exec_log: List[Dict[str, Any]] = []

    # 1) self.codegen → chernovik
    for st in (plan.get("steps") or []):
        if st.get("kind") == "self.codegen":
            try:
                from modules.self.code_sandbox import draft as _draft  # type: ignore
                code = (
                    "from flask import Blueprint\n"
                    "bp = Blueprint('auto_mod', __name__)\n"
                    "def register(app):\n"
                    "    app.register_blueprint(bp)\n"
                    "@bp.route('/auto_mod/ping')\n"
                    "def ping():\n"
                    "    return 'ok'\n"
                )
                rep = _draft("auto_mod", code)
                exec_log.append({"step":"self.codegen", "result": rep})
            except Exception as e:
                exec_log.append({"step":"self.codegen", "error": str(e)})
    # 2) ops.shopping.plan → zadaniya
    for st in (plan.get("steps") or []):
        if st.get("kind") == "ops.shopping.plan":
            try:
                from modules.ops.shopping_list import add_assignments  # type: ignore
                rep = add_assignments(st.get("items") or [], assign_to="papa")
                exec_log.append({"step":"ops.shopping.assign", "result": rep})
            except Exception as e:
                exec_log.append({"step":"ops.shopping.assign", "error": str(e)})

    return {"ok": True, "executed": exec_log}