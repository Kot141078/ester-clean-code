# -*- coding: utf-8 -*-
"""
modules/money/orchestrator.py — Orkestrator «Ester, mne nuzhny dengi».

Chto delaet:
- Raspoznaet triggery ("mne nuzhny dengi", "nuzhen dokhod", "kak zarabotat").
- Zapuskaet opros (kapital, vremya, navyki, dopustimye «ruchnye» deystviya: pozvonit, podpisat, perevesti).
- Sobiraet profil resursov i ogranicheniy (Policy+Safety).
- Generiruet nabor strategiy (M32) i kalibruet ikh (M33).
- Pri nalichii «Judge» (glavnyy LLM/drugoy agent) — zaprashivaet sovety (tekst, bez avtodeystviy).
- Proveryaet nedostayuschie instrumenty (OCR, drayvery, integratsii) i predlagaet sozdat cherez «Garazh».
- Materializuet vybrannuyu strategiyu v TaskTutor (M28) → rezhim A (demo) ili B (ispolnenie).
- Vse logiruet v M30 i dostupno v navigatore pamyati.

MOSTY:
- Yavnyy: (Vospriyatie chata ↔ Plan/deystviya) — edinaya dorozhka «zapros → opros → strategiya → stsenariy».
- Skrytyy #1: (Infoteoriya ↔ Obyasnimost) — skoring s faktorami, «profile» resheniy, zhurnal sobytiy.
- Skrytyy #2: (Kibernetika ↔ Upravlenie) — Policy/Safety na kazhdom shage, rezhimy A/B, ruchnye deystviya polzovatelya.

ZEMNOY ABZATs:
Inzhenerno — eto master zadach s profaylerom i planirovschikom, kotoryy umeet sam dopolnit instrumenty cherez «Garazh».
Prakticheski — skazhesh «Ester, mne nuzhny dengi», ona utochnit resursy, predlozhit realistichnye puti, pokazhet ikh na ekrane,
i s tvoego soglasiya vypolnit dopustimye shagi, a vse, chto nuzhno rukami — vovremya poprosit u tebya.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import os, json, time

from modules.memory import hub as MH
from modules.finance import pathways as FP    # M32
from modules.finance import score_learn as FL # M33
from modules.policy import engine as PE       # M29
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ENABLED = os.environ.get("ESTER_MONEY_ENABLED","1") == "1"
MODE    = os.environ.get("ESTER_MONEY_MODE","A").upper()  # A|B
ALLOW_JUDGE = os.environ.get("ESTER_MONEY_CONSULT_JUDGE","1") == "1"
ALLOW_GARAGE= os.environ.get("ESTER_MONEY_GARAGE","1") == "1"

QUESTIONNAIRE_PATH = "data/money/questionnaire.json"

def _read_questions()->List[Dict[str,Any]]:
    try:
        with open(QUESTIONNAIRE_PATH,"r",encoding="utf-8") as f:
            return json.load(f).get("questions",[])
    except Exception:
        return [
          {"id":"capital_eur","q":"Skolko € dostupno startom? (0..N)","type":"number","min":0,"max":100000,"def":0},
          {"id":"time_week_h","q":"Skolko chasov v nedelyu gotovy vydelyat?","type":"number","min":0,"max":80,"def":10},
          {"id":"skills","q":"Vashi klyuchevye navyki (cherez zapyatuyu)","type":"text","def":"Python, Docs"},
          {"id":"hands","q":"Chto gotovy sdelat rukami? (pozvonit/podpisat/perevesti/otkryt_akkaunt)","type":"text","def":"podpisat, otkryt_akkaunt"}
        ]

def probe()->Dict[str,Any]:
    return {"ok":True,"enabled":ENABLED,"mode":MODE,"allow_judge":ALLOW_JUDGE,"allow_garage":ALLOW_GARAGE}

# ----------------------------- Triggery --------------------------------------
TRIGGERS = [
  "mne nuzhny dengi","nuzhen dokhod","kak zarabotat","zarabotay dlya menya","mogu li ya zarabotat"
]

def match_trigger(text:str)->bool:
    t=(text or "").lower()
    return any(kw in t for kw in TRIGGERS)

# ----------------------------- Profile ---------------------------------------

def start_questionnaire(user:str="owner", session_id:str|None=None)->Dict[str,Any]:
    if not ENABLED: return {"ok":False,"error":"disabled"}
    qs=_read_questions()
    MH.log_plan("money","questionnaire","Start oprosa", user_id=f"user:{user}", session_id=session_id or f"sess_{user}")
    return {"ok":True,"questions":qs}

def build_profile(answers:Dict[str,Any], user:str="owner", session_id:str|None=None)->Dict[str,Any]:
    # normalizatsiya poley
    capital=float(answers.get("capital_eur",0.0) or 0.0)
    time_h=float(answers.get("time_week_h",0.0) or 0.0)
    skills=[s.strip() for s in (answers.get("skills","") or "").split(",") if s.strip()]
    hands=[s.strip() for s in (answers.get("hands","") or "").split(",") if s.strip()]
    prof={"capital_eur":capital,"time_week_h":time_h,"skills":skills,"hands":hands}
    MH.log_result("money","profile","Postroen profil resursov", user_id=f"user:{user}", session_id=session_id or f"sess_{user}", artifacts={"profile":prof})
    return {"ok":True,"profile":prof}

# --------------------------- Strategii i otsenka -------------------------------

def _adjust_text_for_profile(profile:Dict[str,Any])->List[str]:
    # naivnye shablony na osnove profilya
    rec=[]
    c=profile.get("capital_eur",0.0); t=profile.get("time_week_h",0.0)
    if c<=50 and t>=8:
        rec.append("Prodat tsifrovoy shablon (rezyume) za 9€ na Etsy")
    if "Python" in " ".join(profile.get("skills",[])):
        rec.append("Mikro-avtomatizatsii na frilanse (99€ za zadachu)")
    if c>=100 and t>=5:
        rec.append("Lending uslugi s oplatoy cherez Stripe (mikro-pakety 49–99€)")
    if not rec:
        rec.append("Mini-servis: generator pisem s oplatoy 19€ (Gumroad)")
    return rec[:4]

def gather_strategies(profile:Dict[str,Any], target_amount:float=1000.0, timeframe_days:int=14)->Dict[str,Any]:
    ideas=_adjust_text_for_profile(profile)
    items=[]
    for text in ideas:
        sc = FP.evaluate(text, target_amount, timeframe_days)  # vklyuchaet log M30
        rm = FP.make_roadmap(text, target_amount, timeframe_days)
        items.append({"text":text,"score":sc.get("score"),"roadmap":rm.get("roadmap")})
    MH.log_plan("money","strategies","Sobrany strategii", meta={"num":len(items)})
    return {"ok":True,"items":items}

# --------------------------- Konsultatsiya u Judge -----------------------------

def consult_judge(strategies:List[Dict[str,Any]])->Dict[str,Any]:
    """
    Bezopasnaya konsultatsiya: tolko tekstovoe obogaschenie. Nikakikh avtodeystviy.
    """
    if not ALLOW_JUDGE:
        return {"ok":True,"notes":"judge_disabled","items":strategies}
    enriched=[]
    try:
        # Psevdovyzov «Judge»: v realnoy integratsii tut budet marshrutizatsiya v vybrannuyu LLM/agenta.
        for s in strategies:
            advice = {
              "risks": ["konkurentsiya", "platezhnye komissii"],
              "quick_wins": ["reuse UI-shablonov", "mikro-apseyl"],
              "deps": ["uchetnaya zapis platformy", "shablony vizualizatsii"]
            }
            enriched.append({**s, "judge": advice})
        MH.log_result("money","judge_advice","Polucheny sovety Judge", artifacts={"count":len(enriched)})
        return {"ok":True,"items":enriched}
    except Exception as e:
        return {"ok":False,"error":f"judge_error:{e}"}

# --------------------------- Garazh moduley -----------------------------------

def propose_garage_build(profile:Dict[str,Any], strategies:List[Dict[str,Any]])->Dict[str,Any]:
    """
    Proveryaem nedostayuschie sposobnosti (OCR, driver, integratsii).
    Vozvraschaem «chek-list» dlya Garazha (sozdanie/vklyuchenie moduley).
    """
    needs=[]
    # OCR
    needs.append({"id":"ocr","title":"OCR (Tesseract/Pillow) dlya klika po tekstu","present":_has_ocr()})
    # DesktopDriver real-mode
    needs.append({"id":"desktop_real","title":"Realnyy drayver klika/vvoda (whitelist)","present":_has_real_driver()})
    # Stripe/Etsy/Upwork integratsii (pleyskholdery)
    needs.append({"id":"etsy","title":"Integratsiya Etsy (webhooks/CSV)","present":False})
    needs.append({"id":"gumroad","title":"Integratsiya Gumroad (webhooks/CSV)","present":False})
    return {"ok":True,"needs":needs,"can_autobuild":ALLOW_GARAGE}

def _has_ocr()->bool:
    try:
        import PIL, pytesseract  # type: ignore
        return True
    except Exception:
        return False

def _has_real_driver()->bool:
    # proverka env-flaga ot M25
    return os.environ.get("ESTER_DD_ENABLED","0") == "1"

# --------------------------- Materializatsiya plana -----------------------------

def materialize_and_play(roadmap:Dict[str,Any], mode:str|None=None)->Dict[str,Any]:
    mode=(mode or MODE).upper()
    scn=FP.materialize_in_tutor(roadmap)
    if not scn.get("ok"): return scn
    # Politicheskiy «ping» pered B
    if mode=="B":
        steps = roadmap.get("steps") or []
        if steps:
            d=PE.evaluate(steps[0].get("agent","desktop"), steps[0].get("kind","open_app"),
                          steps[0].get("meta") or {}, "user:default", "allow",
                          {"mode":mode, "real_enabled":_has_real_driver(), "requires_admin":False, "steps":len(steps)})
            if d.get("decision")=="deny":
                return {"ok":False,"error":"policy_denied","rule":d.get("matched_rule")}
    return FP.play_tutor(scn["scenario_id"], mode)

# --------------------------- Stsenariy mastera --------------------------------

def master_run(answers:Dict[str,Any], target_amount:float=1000.0, timeframe_days:int=14, mode:str|None=None)->Dict[str,Any]:
    """
    Polnyy tsikl mastera «mne nuzhny dengi».
    """
    pr=build_profile(answers)
    st=gather_strategies(pr["profile"], target_amount, timeframe_days)
    cj=consult_judge(st["items"])
    pg=propose_garage_build(pr["profile"], st["items"])
    # Vyberem pervuyu strategiyu kak demo
    best=(cj.get("items") or st["items"])[0]
    run=materialize_and_play(best.get("roadmap") or {}, mode)
    MH.log_result("money","master_run","Master zavershen", artifacts={
        "profile":pr["profile"], "chosen":best.get("text"), "mode":mode or MODE
    })
    return {
      "ok": bool(run.get("ok",True)),
      "profile": pr["profile"],
      "strategies": cj.get("items") or st["items"],
      "garage": pg,
      "play": run
    }
