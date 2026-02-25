# -*- coding: utf-8 -*-
"""modules/finance/pathways.py - Puti k dokhodu: ideya → otsenka → dorozhnaya karta → deystvie → metriki.

Name:
- Prinyat "ideyu zarabotka" i strukturirovat ee kak Goal (tsel: summa, srok, kanal).
- Otsenit ideyu po prostym, no prozrachnym kriteriyam (rynochnost, realizuemost, legalnost, vremya).
- Sgenerirovat dorozhnuyu kartu (roadmap) iz atomarnykh shagov dlya suschestvuyuschikh agentov (Desktop/TaskTutor/Web).
- Orkestrovat zapusk (rezhim A=demo, B=ispolnenie) cherez TaskTutor; vse logirovat v MemoryHub.
- Metriki: tselevaya tsena/kol-vo prodazh/konversiya; status i report.

MOSTY:
- Yavnyy: (Myshlenie/Politiki/Safety ↔ Deystviya) — kazhdaya finansovaya operatsiya prokhodit reshatel riska i pravila.
- Skrytyy #1: (Infoteoriya ↔ Obyasnimost) - skoring razbit na faktory: vidno "pochemu takaya otsenka".
- Skrytyy #2: (Memory ↔ Povtoryaemost) — ves tsikl logiruetsya v M30, stsenarii keshiruyutsya v M28.

ZEMNOY ABZATs:
Inzhenerno eto "finansovyy planirovschik poverkh RPA": na vkhod - ideya s parametrami,
na vykhod - prozrachnyy plan deystviy, kotoryy mozhno proigrat (A) or ispolnit (B) v ramkakh
belykh spiskov i politik. Prakticheski - Ester ne "treydit", a sistemno gotovit i avtomatiziruet
realnye bezopasnye sposoby monetizatsii: tsifrovye tovary, uslugi, integratsii, lendingi.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
import os, time, json
from modules.memory import hub as MH
from modules.policy import engine as PE
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ENABLED = os.environ.get("ESTER_FIN_ENABLED","1") == "1"
MODE    = os.environ.get("ESTER_FIN_MODE","A").upper()     # A | B
BUDGET_H = float(os.environ.get("ESTER_FIN_BUDGET_HOURS","4"))

# ------------------------------- Modeli --------------------------------------

def normalize_idea(text:str, target_amount:float=1000.0, timeframe_days:int=14)->Dict[str,Any]:
    """Rough normalization of the idea: extracting the channel and type of monetization by keywords."""
    t=text.lower()
    channel="digital_product"
    if "frilans" in t or "freelance" in t: channel="freelance"
    elif "etsy" in t or "gumroad" in t or "template" in t or "shablon" in t: channel="digital_product"
    elif "lending" in t or "landing" in t or "stranitsu" in t: channel="landing_service"
    elif "obuchen" in t or "kurs" in t: channel="course"
    elif "youtube" in t or "tiktok" in t: channel="content_ads"
    elif "bot" in t or "automation" in t or "skript" in t: channel="automation_tool"

    idea={
        "raw": text.strip(),
        "channel": channel,
        "target_amount": float(target_amount),
        "timeframe_days": int(timeframe_days)
    }
    return idea

def score_idea(idea:Dict[str,Any])->Dict[str,Any]:
    """Prostaya prozrachnaya metrika (0..100):
      - Legalnost/politiki (pass/fail) — if fail, to score=0.
      - Realizuemost (10..40)
      - Rynochnost (10..30)
      - Vremya do pervykh money (5..20)
      - Risk/dependency (fine -0..20)"""
    channel=idea.get("channel","digital_product")
    # 1) Legality/policies - we only advise (a complete ban will be in Policies when starting the steps)
    legal_ok = channel in ("digital_product","freelance","landing_service","course","content_ads","automation_tool")
    if not legal_ok:
        return {"ok":True,"score":0,"factors":{"legal":0},"advice":"kanal ne podderzhan politikoy"}
    # 2) Realizuemost
    feas = {"digital_product":38,"freelance":32,"landing_service":30,"course":24,"content_ads":18,"automation_tool":28}.get(channel,20)
    # 3) Marketability (very roughly, taking into account competition)
    market = {"digital_product":26,"freelance":22,"landing_service":24,"course":18,"content_ads":16,"automation_tool":20}.get(channel,18)
    # 4) Time until the first money (the sooner, the longer)
    speed = {"digital_product":18,"freelance":16,"landing_service":16,"course":8,"content_ads":10,"automation_tool":12}.get(channel,10)
    # 5) Riski/zavisimosti (shtraf)
    risk_penalty = {"digital_product":2,"freelance":4,"landing_service":5,"course":8,"content_ads":10,"automation_tool":6}.get(channel,6)
    score=max(0, min(100, feas+market+speed - risk_penalty))
    return {"ok":True,"score":score,"factors":{"feas":feas,"market":market,"speed":speed,"risk_penalty":risk_penalty}, "channel":channel}

# ----------------------------- Dorozhnye karty --------------------------------

def roadmap_for(idea:Dict[str,Any])->Dict[str,Any]:
    """Sintez dorozhnoy karty v atomarnye shagi pod suschestvuyuschie agenty/tyutora.
    All steps izlagayutsya kak TaskTutor-stsenariy (M28), no vozvraschayutsya zdes kak JSON."""
    ch=idea.get("channel")
    title=f"Earn {int(idea.get('target_amount',1000))}€ via {ch}"
    steps:List[Dict[str,Any]]=[]
    metrics={
        "price": 9 if ch=="digital_product" else 100,
        "units_needed": max(1, int(idea.get("target_amount",1000) // (9 if ch=="digital_product" else 100))),
        "kpi": {"visitors": 300, "cr": 0.05} if ch in ("digital_product","landing_service") else {"leads": 10}
    }
    if ch=="digital_product":
        steps += [
            {"agent":"desktop","kind":"open_url","meta":{"url":"https://www.canva.com"}},
            {"agent":"desktop","kind":"click_text","meta":{"text":"Create a design"}},
            {"agent":"desktop","kind":"type_text","meta":{"text":"Resume Template modern minimal"}},
            {"agent":"desktop","kind":"screenshot","meta":{}},
            {"agent":"desktop","kind":"open_url","meta":{"url":"https://www.etsy.com"}},
            {"agent":"desktop","kind":"click_text","meta":{"text":"Sell on Etsy"}},
            {"agent":"desktop","kind":"type_text","meta":{"text":"Upload listing: Resume Template (9€)"}},
        ]
    elif ch=="freelance":
        steps += [
            {"agent":"desktop","kind":"open_url","meta":{"url":"https://www.upwork.com"}},
            {"agent":"desktop","kind":"click_text","meta":{"text":"Sign up"}},
            {"agent":"desktop","kind":"type_text","meta":{"text":"Profile: Python automations / RPA"}},
            {"agent":"desktop","kind":"open_url","meta":{"url":"https://www.linkedin.com"}},
            {"agent":"desktop","kind":"type_text","meta":{"text":"Post: offering micro-automations 99€"}},
        ]
    elif ch=="landing_service":
        steps += [
            {"agent":"desktop","kind":"open_url","meta":{"url":"https://pages.github.com"}},
            {"agent":"desktop","kind":"click_text","meta":{"text":"Get started"}},
            {"agent":"desktop","kind":"type_text","meta":{"text":"Create landing with Stripe link"}},
        ]
    elif ch=="automation_tool":
        steps += [
            {"agent":"desktop","kind":"open_url","meta":{"url":"https://github.com/new"}},
            {"agent":"desktop","kind":"type_text","meta":{"text":"Repo: tiny-email-wizard"}},
            {"agent":"desktop","kind":"open_url","meta":{"url":"https://gumroad.com"}},
            {"agent":"desktop","kind":"type_text","meta":{"text":"Create product 19€"}},
        ]
    else:
        steps += [{"agent":"desktop","kind":"open_url","meta":{"url":"https://example.org"}},]

    roadmap={"title":title,"idea":idea,"mode":MODE,"budget_hours":BUDGET_H,"steps":steps,"metrics":metrics}
    return {"ok":True,"roadmap":roadmap}

# ----------------------------- Integratsii ------------------------------------

def _policy_decide(agent:str, kind:str, meta:Dict[str,Any])->Dict[str,Any]:
    # Compose from Police (M29). We do not count safeties-verdict at this level (this will happen when dry_run).
    ctx={"mode": MODE, "real_enabled": os.environ.get("ESTER_DD_ENABLED","0")=="1", "requires_admin": False, "steps": 1}
    return PE.evaluate(agent, kind, meta, subject="user:default", safety_decision="allow", ctx=ctx)

def materialize_in_tutor(roadmap:Dict[str,Any])->Dict[str,Any]:
    """Create/update TaskTutor script from the map."""
    try:
        from modules.agents import task_tutor as TT
        title = roadmap.get("title","Financial Path")
        intent = roadmap.get("idea",{}).get("raw","")
        res = TT.create_from_intent(title, intent)
        if not res.get("ok"): return {"ok":False,"error":"tutor_create_fail"}
        scn=res["scenario"]
        # Let's rewrite the steps with the generated roadmap
        scn["steps"] = roadmap.get("steps",[])
        TT.save(scn)
        MH.log_plan("tutor","financial_path","Created scenario for financial path", scenario_id=scn["id"], user_id="user:default")
        return {"ok":True,"scenario_id":scn["id"]}
    except Exception as e:
        return {"ok":False,"error":f"tutor_error:{e}"}

def play_tutor(scenario_id:str, mode:str|None=None)->Dict[str,Any]:
    try:
        from modules.agents import task_tutor as TT
        r = TT.play(scenario_id, mode or MODE)
        MH.log_action("tutor","play","Running a Financial Path Script", {"decision": r.get("ok")}, scenario_id=scenario_id, user_id="user:default")
        return r
    except Exception as e:
        return {"ok":False,"error":f"tutor_play_error:{e}"}

# ----------------------------- Vneshniy API -----------------------------------

def probe()->Dict[str,Any]:
    return {"ok":True,"enabled":ENABLED,"mode":MODE,"budget_hours":BUDGET_H}

def evaluate(text:str, target_amount:float=1000.0, timeframe_days:int=14)->Dict[str,Any]:
    if not ENABLED: return {"ok":False,"error":"disabled"}
    idea=normalize_idea(text, target_amount, timeframe_days)
    sc=score_idea(idea)
    MH.log_plan("finance","score","Otsenka idei", text=f"{text}", user_id="user:default", meta={"score":sc})
    return {"ok":True,"idea":idea,"score":sc}

def make_roadmap(text:str, target_amount:float=1000.0, timeframe_days:int=14)->Dict[str,Any]:
    if not ENABLED: return {"ok":False,"error":"disabled"}
    idea=normalize_idea(text, target_amount, timeframe_days)
    rm=roadmap_for(idea)
    MH.log_plan("finance","roadmap","Postroena dorozhnaya karta", user_id="user:default", meta={"channel":idea.get("channel")})
    return {"ok":True, **rm}

def create_and_play(text:str, mode:str|None=None)->Dict[str,Any]:
    """Uskorennaya dorozhka: idea → karta → stsenariy → play(A/B)"""
    m=make_roadmap(text)
    if not m.get("ok"): return m
    scn=materialize_in_tutor(m["roadmap"])
    if not scn.get("ok"): return scn
    if (mode or MODE)=="A":
        return play_tutor(scn["scenario_id"], "A")
    # Before B, check at least one policy to launch the first step
    steps = m["roadmap"].get("steps") or []
    if steps:
        d=_policy_decide(steps[0].get("agent","desktop"), steps[0].get("kind","open_app"), steps[0].get("meta") or {})
        if d.get("decision")=="deny":
            return {"ok":False,"error":"policy_denied","rule":d.get("matched_rule")}
    return play_tutor(scn["scenario_id"], mode or "B")