# -*- coding: utf-8 -*-
"""
modules/thinking/coach.py — kouch-sloy dlya myslitelnykh i deyatelnostnykh tsiklov.

Funktsii:
  diagnose(window=200) -> dict     # gde zastrevaem: think/plan/safety/act/reflect
  suggest_micro_goals(k=5) -> dict # spisok korotkikh shagov, ukladyvayuschikhsya v byudzhet
  commit_micro_goal(text) -> dict  # zafiksirovat mikro-tsel i postavit ee v missii (low)
  retro(window=400) -> dict        # retrospektiva: chto srabotalo/ne srabotalo
  status() -> dict                 # sostoyanie koucha

MOSTY:
- Yavnyy: (Mysl ↔ Meta-myshlenie) — diagnostika, podskazka, retro.
- Skrytyy #1: (Infoteoriya ↔ Ekonomiya) — mikro-tseli minimiziruyut entropiyu/stoimost perekhoda.
- Skrytyy #2: (Kibernetika ↔ Obuchenie) — petlya uluchsheniy po metrikam uspekhov kaskadov.

ZEMNOY ABZATs:
Inzhenerno — eto nadstroyka-«navigator»: smotrit na logi, ukazyvaet uzkoe mesto,
predlagaet malenkiy sleduyuschiy shag i posle — chestno razbiraet rezultat.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import os, json, time, re
from collections import Counter, defaultdict

from modules.memory import store
from modules.memory.events import record_event
from modules.thinking import action_safety as AS
from modules.thinking import selfdrive as SD
from modules.thinking import missions as MS
from modules.thinking import pipelines as TP
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_STATE = {
    "sessions": 0,
    "last_diag": None,
    "last_suggestions": [],
    "last_retro": None
}

def _recent_records(limit:int=400)->List[Dict[str,Any]]:
    items = sorted(store._MEM.values(), key=lambda r:r.get("ts",0), reverse=True)
    return items[:limit]

def _stage_from_text(t:str)->str:
    t=t.lower()
    if "cascade" in t or "pipeline" in t: return "act"
    if "selfdrive" in t and "reflect" in t: return "reflect"
    if "safety:" in t: return "safety"
    if "plan" in t: return "plan"
    if "think" in t: return "think"
    return "other"

def _success_from_event(r:Dict[str,Any])->int:
    txt=(r.get("text") or "").lower()
    if "error" in txt or "fail" in txt or "denied" in txt: return 0
    return 1

def diagnose(window:int=200)->Dict[str,Any]:
    """
    Nakhodit «uzkie mesta» po chastote neudach/stopov na stadiyakh petli.
    """
    recs=_recent_records(window)
    by_stage=Counter()
    fail_stage=Counter()
    for r in recs:
        st=_stage_from_text(r.get("text",""))
        by_stage[st]+=1
        if _success_from_event(r)==0:
            fail_stage[st]+=1
    # normalize
    diag=[]
    for st,count in by_stage.items():
        f=fail_stage.get(st,0)
        rate = f/(count or 1)
        diag.append({"stage":st,"events":count,"fail":f,"fail_rate":round(rate,2)})
    diag.sort(key=lambda x:x["fail_rate"], reverse=True)
    out={"ok":True,"diagnosis":diag[:5]}
    _STATE["last_diag"]=out
    _STATE["sessions"]+=1
    record_event("coach","diagnose",True,{"top":diag[:2]})
    return out

def _load_playbooks()->List[Dict[str,Any]]:
    p = os.environ.get("ESTER_COACH_PLAYBOOKS","rules/coach_playbooks.json")
    if os.path.exists(p):
        try:
            with open(p,"r",encoding="utf-8") as f:
                obj=json.load(f)
                if isinstance(obj,list): return obj
        except Exception:
            pass
    # defoltnyy nabor (bez fayla)
    return [
        {"when":"safety", "tips":[
            "Snizit masshtab shaga (umenshit scale).",
            "Razdelit deystvie na podshagi bez prav admina.",
            "Snachala zapusti simulyatsiyu na sandbox-datasete."
        ]},
        {"when":"plan", "tips":[
            "Utochni tsel odnim predlozheniem: chto kriteriy gotovnosti?",
            "Sravni 2–3 alternativy cherez decision_plan.",
            "Sformiruy opornye terminy (analyze_text) i prover kontekst."
        ]},
        {"when":"act", "tips":[
            "Sdelay «sukhoy progon» bez izmeneniy (dry-run).",
            "Ogranich shagi do 2–3, prover effekty i otkat.",
            "Logiruy kazhdoe deystvie v timeline dlya retro."
        ]},
        {"when":"reflect", "tips":[
            "Zapishi po punktu: chto srabotalo / ne srabotalo / chemu nauchilis.",
            "Vydeli odnu metriku na sleduyuschiy tsikl (naprimer, p_success↑)."
        ]},
        {"when":"think", "tips":[
            "Sformuliruy zadachu kak vopros i kak tsel.",
            "Prover, net li gotovykh shablonov v pipelines."
        ]}
    ]

def suggest_micro_goals(k:int=5)->Dict[str,Any]:
    diag = (_STATE.get("last_diag") or diagnose()).get("diagnosis", [])
    focus = diag[0]["stage"] if diag else "plan"
    # bazovye mikro-tseli, bezopasnye po byudzhetu
    candidates = {
        "plan": [
            "Sformulirovat kriteriy gotovnosti (Definition of Done).",
            "Sobrat 3 alternativy i otsenit cherez decision_plan.",
            "Izvlech klyuchevye terminy zadachi (analyze_text)."
        ],
        "safety": [
            "Snizit scale v metadannykh deystviya do 0.5.",
            "Razbit deystvie na podshagi bez prav administratora.",
            "Prognat simulate(trials=100) i zapisat p_success."
        ],
        "act": [
            "Sdelat dry-run kaskada bez izmeneniy sistemy.",
            "Ogranichit kaskad do 2 shagov i zafiksirovat rezultat.",
            "Dobavit zapis otkata pered deystviem."
        ],
        "reflect":[
            "Opisat 3 vyvoda i odnu gipotezu dlya proverki zavtra.",
            "Save svodku [selfdrive] s klyuchevymi terminami."
        ],
        "think":[
            "Pereformulirovat tsel v odnu stroku.",
            "Sverit formulirovku s predyduschimi tselyami (poisk po pamyati)."
        ],
        "other":[
            "Obnovit QA pamyati i pereschitat embeddingi (M12)."
        ]
    }
    tips=[]
    for x in candidates.get(focus, candidates["plan"]):
        tips.append({"goal": x, "focus": focus})
    tips = tips[:max(1,int(k))]
    # pleybuki
    pbs=_load_playbooks()
    pb_tips=[t for pb in pbs if pb.get("when")==focus for t in pb.get("tips",[])]
    out={"ok":True,"focus":focus,"micro_goals":tips,"playbook_tips":pb_tips[:5]}
    _STATE["last_suggestions"]=out
    record_event("coach","suggest",True,{"focus":focus,"n":len(tips)})
    return out

def commit_micro_goal(text:str)->Dict[str,Any]:
    # sozdaem low-priority missiyu bez raspisaniya
    r=MS.create(goal=text, priority="low", schedule="", template="pipeline",
                params={"name":"analyze_text","text":text})
    memory_add("goal", f"micro-goal: {text}", {"mission_id": r["mission"]["id"]})
    record_event("coach","commit_micro_goal",True,{"goal":text})
    return {"ok":True,"mission":r["mission"]}

def retro(window:int=400)->Dict[str,Any]:
    """
    Prostoy retro-analiz: gde chasche uspekhi, gde provaly, p_success (po simulyatsiyam),
    kakie tipy zapisey preobladayut do/posle «act».
    """
    recs=_recent_records(window)
    by_stage=Counter()
    succ=Counter()
    for r in recs:
        st=_stage_from_text(r.get("text",""))
        by_stage[st]+=1
        if _success_from_event(r)==1:
            succ[st]+=1
    report=[]
    for st in ["think","plan","safety","act","reflect","other"]:
        n=by_stage.get(st,0); s=succ.get(st,0); rate=round((s/(n or 1)),2)
        report.append({"stage":st,"events":n,"success_rate":rate})
    # prostye vyvody
    bottleneck=min(report, key=lambda x:x["success_rate"]) if report else {"stage":"plan"}
    strong=max(report, key=lambda x:x["success_rate"]) if report else {"stage":"reflect"}
    summary=f"Uzkoe mesto: {bottleneck['stage']}; silnaya storona: {strong['stage']}."
    out={"ok":True,"summary":summary,"report":report}
    _STATE["last_retro"]=out
    record_event("coach","retro",True,{"bottleneck":bottleneck.get("stage")})
    # sokhranit v pamyat
    memory_add("summary", f"[coach:retro] {summary}", {"report":report})
    return out

def status()->Dict[str,Any]:
    return {"ok":True, **_STATE}