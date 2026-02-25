# -*- coding: utf-8 -*-
"""modules/retire/planner.py - Dolgosrochnyy planirovschik (3–15 let).

Name:
- Khranit profil tseley: mesyachnyy tselevoy dokhod (evro), srok, startovyy kapital, dop.vznosy, tolerantnost k risku.
- Stroit traektorii: nakopleniya (podushka), tsikly dokhoda (iz M32 pathways), reinvestirovanie.
- Ezhemesyachnyy tsikl: vybiraet “put k dengam” (M32/M33), sostavlyaet spisok zadach (M28), planiruet “ruchnye” deystviya.
- Otchet: “sdelano/metriki/chto dalshe”, zapis v pamyat (M30), politika/bezopasnost (M29).
- Svyaz s M34: stsenariy “Ester, mne nuzhny dengi” stanovitsya kirpichom v mesyachnom plane.

MOSTY:
- Yavnyy: (Fin. puti M32–M33 ↔ Dolgiy gorizont) - kratkosrochnye stsenarii vkladyvayutsya v mnogo-letniy plan.
- Skrytyy #1: (Infoteoriya ↔ Planning) - tseli svedeny v maloe chislo parametrov, iz kotorykh determiniruyutsya zadachi.
- Skrytyy #2: (Kibernetika ↔ Upravlyaemost) — mesyachnye tsikly, otchetnye tochki i politika pozvolyat ustoychivo idti k tseli.

ZEMNOY ABZATs:
Inzhenerno eto “nadstroyka-orkestrator” nad uzhe suschestvuyuschimi agentsami/pamyatyu: ona raz v mesyats generiruet
realistichnyy nabor zadach pod tsel “X €/m cherez N let”, proveryaet riski i fiksiruet result. Practically
ty poluchaesh ponyatnyy ezhemesyachnyy plan, kotoryy Ester pokazyvaet/delaet i so vremenem podstraivaet.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
import os, json, time, math
from datetime import datetime

from modules.memory import hub as MH          # M30
from modules.finance import pathways as FP    # M32
from modules.finance import score_learn as FL # M33
from modules.money import orchestrator as MO  # M34 (opros/profil/ruki)
from modules.policy import engine as PE       # M29
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ENABLED = os.environ.get("ESTER_RETIRE_ENABLED","1") == "1"
MODE    = os.environ.get("ESTER_RETIRE_MODE","A").upper()
HOR_YEARS = int(os.environ.get("ESTER_RETIRE_HOR_YEARS","10"))
REPORT_DAY = int(os.environ.get("ESTER_RETIRE_REPORT_DAY","1"))
PROFILE_PATH = "data/retire/profile.json"

# --------- profil ---------
_DEFAULT_PROFILE = {
  "target_monthly_eur": 1000.0,
  "horizon_years": HOR_YEARS,
  "start_capital_eur": 0.0,
  "monthly_contrib_eur": 100.0,
  "risk_tolerance": "low",   # low/med/high (vliyaet na vybor kanalov)
  "hands": ["podpisat","otkryt_akkaunt"],  # manual actions that the user is ready to perform
  "notes": "initsializatsiya"
}

def _ensure_profile()->Dict[str,Any]:
    os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
    if not os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH,"w",encoding="utf-8") as f: json.dump(_DEFAULT_PROFILE, f, ensure_ascii=False, indent=2)
    try:
        with open(PROFILE_PATH,"r",encoding="utf-8") as f: return json.load(f)
    except Exception:
        return dict(_DEFAULT_PROFILE)

def save_profile(p:Dict[str,Any])->Dict[str,Any]:
    obj=_ensure_profile(); obj.update(p or {})
    with open(PROFILE_PATH,"w",encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False, indent=2)
    MH.log_result("retire","save_profile","Sokhranen profil", artifacts={"profile":obj})
    return {"ok":True,"profile":obj}

def profile()->Dict[str,Any]:
    return {"ok":True,"profile":_ensure_profile()}

# --------- simple savings/income model ---------
def _monthly_growth(capital:float, contrib:float, reinvest_rate:float)->float:
    # capital: conservative gains “quasi-coupon” from system paths (digital products/services), reinvested share
    return max(0.0, contrib + capital * max(0.0, reinvest_rate))

def simulate(months:int=12)->Dict[str,Any]:
    p=_ensure_profile()
    cap=float(p.get("start_capital_eur",0.0))
    contrib=float(p.get("monthly_contrib_eur",0.0))
    # rough dependence of reinvested “return” on risk
    rmap={"low":0.002,"med":0.006,"high":0.012}
    reinv=rmap.get(p.get("risk_tolerance","low"),0.002)
    tr=[]
    for m in range(1, months+1):
        add=_monthly_growth(cap, contrib, reinv)
        cap += add
        tr.append({"m":m,"capital":round(cap,2),"add":round(add,2)})
    MH.log_plan("retire","simulate","Simulyatsiya nakopleniy", meta={"months":months,"reinv":reinv})
    return {"ok":True,"trajectory":tr,"final_capital":round(cap,2),"assumptions":{"reinvest_rate":reinv}}

# --------- vybor kanalov pod risk ---------
_ALLOWED_BY_RISK = {
  "low":  ["digital_product","freelance","landing_service"],
  "med":  ["digital_product","freelance","landing_service","automation_tool"],
  "high": ["digital_product","freelance","landing_service","automation_tool","content_ads","course"]
}

def _filter_channels_by_risk(ch:str, risk:str)->bool:
    return ch in _ALLOWED_BY_RISK.get(risk,"low")

# --------- mesyachnyy plan ---------
def make_monthly_plan(target_amount:float|None=None, weeks:int=4)->Dict[str,Any]:
    """Generiruem plan mesyatsa: 2–4 fokusa iz M32, zavisyaschie ot riska/vremeni/proshlykh uspekhov (M33),
    materializuem stsenarii v M28 (v rezhime A po umolchaniyu)."""
    p=_ensure_profile()
    risk=p.get("risk_tolerance","low")
    answers = {
      "capital_eur": p.get("start_capital_eur",0.0),
      "time_week_h": 10,  # default score; UI will let you rule
      "skills": "Python, Docs",
      "hands": ", ".join(p.get("hands") or [])
    }
    # Sobiraem strategii (M34→M32/M33)
    pr = MO.build_profile(answers)
    st = MO.gather_strategies(pr["profile"], target_amount or p.get("target_monthly_eur",1000.0), 30)
    items=[]
    for it in st.get("items") or []:
        ch = it.get("roadmap",{}).get("idea",{}).get("channel","digital_product")
        if not _filter_channels_by_risk(ch, risk): 
            continue
        # skoring posle kalibrovki
        sc = it.get("score",{}); score = (sc.get("score") if isinstance(sc,dict) else sc) or {}
        items.append({"text":it.get("text"),"score":score,"roadmap":it.get("roadmap")})
    # vyberem top-3
    items = items[:3]
    MH.log_plan("retire","month_plan","Sformirovan plan mesyatsa", meta={"count":len(items),"risk":risk})
    return {"ok":True,"items":items,"risk":risk}

def run_month(mode:str|None=None)->Dict[str,Any]:
    """We play/execute the monthly plan: for each selected path we create and play the TaskTutor script."""
    plan = make_monthly_plan()
    res=[]
    for it in plan.get("items") or []:
        r = MO.materialize_and_play(it.get("roadmap") or {}, (mode or MODE))
        res.append({"text":it.get("text"),"ok":r.get("ok"),"play":r})
    MH.log_result("retire","month_run","Plan mesyatsa vypolnen", artifacts={"runs":len(res),"mode":mode or MODE})
    return {"ok":all(x.get("ok",True) for x in res),"runs":res}

# --------- "what's done/what's next" report ---------
def monthly_report()->Dict[str,Any]:
    """Pulls out the tail of M30 events and collects a short report on the acquisition circuit."""
    tail = MH.counts()
    summary = {
      "events_total": tail.get("count"),
      "recent": tail.get("tail")
    }
    # minimal report text
    text = f"Report: events of all ZZF0Z, recent ZZF1ZZ. The next step is to generate a plan for the month and run it in ZZF2ZZ mode."
    MH.log_result("retire","report","Report collected", artifacts={"text":text})
    return {"ok":True,"summary":summary,"text":text}

# --------- "date of month" scheduler (pseudo) ---------
def should_run_monthly_report(date:Optional[datetime]=None)->bool:
    d = date or datetime.now()
    return d.day == REPORT_DAY

def probe()->Dict[str,Any]:
    return {"ok":True,"enabled":ENABLED,"mode":MODE,"horizon_years":HOR_YEARS,"report_day":REPORT_DAY}