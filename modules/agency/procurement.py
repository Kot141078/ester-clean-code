# -*- coding: utf-8 -*-
"""modules/agency/procurement.py - kaskadnyy planirovschik “poluchit to, chto nuzhno”:
reuse → free/open-source → exchange s sestrami → zarabotat → kupit.

Mosty:
- Yavnyy: (Search ↔ Inzhest) ischem besplatnye analogi i srazu gotovim URL dlya inzhesta.
- Skrytyy #1: (Memory ↔ RAG) naydennoe popadaet v pamyat i uluchshaet posleduyuschie otvety.
- Skrytyy #2: (Ekonomika ↔ Kontrol) reshenie uchityvaet ledzher i limity, a “kupit” vozmozhno tolko s razresheniem.

Zemnoy abzats:
This is how chek-list mastera: snachala poprobuy tem, chto uzhe est, zatem besplatnye instrumenty, zatem obmen, tolko potom dengi.

# c=a+b"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from modules.agency import ledger as L  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AGCY_AB","A") or "A").upper()
ALLOW_APPLY = bool(int(os.getenv("AGCY_ALLOW_APPLY","0")))
DAILY_CAP = float(os.getenv("AGCY_DAILY_CAP_EUR","50"))
MONTHLY_CAP = float(os.getenv("AGCY_MONTHLY_CAP_EUR","200"))

def plan_need(need: str, budget_eur: float = 0.0) -> Dict[str, Any]:
    need = (need or "").strip()
    if not need:
        return {"ok": False, "error": "need is required"}
    bal = L.balances()
    cash = float(bal.get("cash_eur", 0.0))
    steps: List[Dict[str, Any]] = []

    # 1) reuse / modul iz extensions/enabled
    steps.append({"kind":"reuse.scan", "explain":"check already connected extensions and ready-made functions", "status":"plan"})

    # 2) free/open-source poisk
    steps.append({"kind":"search.free", "explain":"nayti svobodnye alternativy/biblioteki", "status":"plan",
                  "action":{"endpoint":"/thinking/web_context/expand","body":{"q":f"{need} open-source library", "k":5, "autofetch":False}}})

    # 3) obmen s sestrami (LAN/P2P)
    steps.append({"kind":"p2p.ask", "explain":"sprosit u sester-uzlov: est li gotovyy komponent/resurs", "status":"plan"})

    # 4) earn money: prepare safe tasks (draft), do not publish without an operator
    earn = {
        "kind":"earn.draft",
        "explain":"create a list of small tasks for 1–2 hours (docs, tests, minor fixes) that can be completed for income",
        "tasks":[
            {"title":"dobavit avtotesty k video-payplaynu", "est_reward_eur": 15},
            {"title":"write a short guide on connecting SCA/ACC", "est_reward_eur": 10},
        ],
        "status":"plan"
    }
    steps.append(earn)

    # 5) buy (if necessary and have enough caps/balance)
    if budget_eur > 0:
        pill = _pill_armed()
        allow = L.spend_allowed(budget_eur, DAILY_CAP, MONTHLY_CAP, pill)
        steps.append({"kind":"buy.check", "explain":"checking daily/monthly limits and tablet status", "status":"plan", "caps": allow})
        can_buy = allow["ok"] and (cash >= budget_eur) and ALLOW_APPLY and AB=="A"
        steps.append({"kind":"buy.intent", "amount_eur": budget_eur, "allowed_now": bool(can_buy), "status":"plan"})

    return {"ok": True, "need": need, "cash_eur": cash, "steps": steps, "ab": AB, "apply_enabled": ALLOW_APPLY}

def execute(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Safe is complete: do it tolko to, chto ne obraschaetsya k dengam.
    Pokupki vozmozhny, tolko esli ALLOW_APPLY=1 i limity ok (i “tabletka” pri neobkhodimosti)."""
    if AB == "B":
        return {"ok": True, "executed": [], "note": "AGCY_AB=B, only planning allowed"}
    done: List[Dict[str, Any]] = []
    # shag: vyzov veb-poiska/expander’a
    for st in plan.get("steps", []):
        if st.get("kind") == "search.free" and st.get("action"):
            try:
                import requests, os
                base = os.getenv("ESTER_BASE_URL","http://127.0.0.1:8000")
                ep = st["action"]["endpoint"]; body = st["action"]["body"]
                r = requests.post(base + ep, json=body, timeout=12)
                ok = (r.status_code == 200)
                done.append({"kind":"search.free", "status":"ok" if ok else f"err {r.status_code}", "resp": (r.json() if ok else r.text[:400])})
            except Exception as e:
                done.append({"kind":"search.free", "status":"exception", "error": str(e)})
        if st.get("kind") == "buy.intent" and st.get("allowed_now"):
            # fixing “expense” as a reserve (without actual purchase)
            amt = float(st.get("amount_eur",0))
            pill = _pill_armed()
            allow = L.spend_allowed(amt, DAILY_CAP, MONTHLY_CAP, pill)
            if allow["ok"] and ALLOW_APPLY:
                L.add_expense(amt, "EUR", purpose=f"reserve for {plan.get('need','')}", meta={"kind":"reserve"})
                done.append({"kind":"buy.reserve", "amount_eur": amt, "status":"reserved"})
            else:
                done.append({"kind":"buy.reserve", "amount_eur": amt, "status":"denied", "caps": allow})
    return {"ok": True, "executed": done}

def _pill_armed() -> bool:
    try:
        import json, time
        st = json.load(open("data/agency/agency_pill.json","r",encoding="utf-8"))
        return bool(st.get("armed") and int(time.time()) <= int(st.get("until",0)))
    except Exception:
        return False
# c=a+b