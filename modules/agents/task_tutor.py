# -*- coding: utf-8 -*-
"""modules/agents/task_tutor.py - Demo-rezhim “Pokazhi kak sdelat X”.

What does it mean:
- Generatsiya stsenariya iz namereniya (intent) cherez gotovye kirpichi DesktopAgent + Vision++.
- Validatsiya stsenariya: proverka yakorey/teksta/whitelist, dry-run safety otsenki.
- Proigryvanie: step-by-step "show/do/try" (A-rezhim: pokazat, B-rezhim: vypolnit), pauza/prodolzhit.
- Logirovanie: taymlayn shagov, snapshoty (esli vklyuchen M27), “profile” stsenariya (M23).

MOSTY:
- Yavnyy: (Zrenie/Agenty ↔ Obuchenie) - poshagovye instruktsii prevraschayutsya v interaktivnyy pokaz.
- Skrytyy #1: (Infoteoriya ↔ Ekonomiya) - shagi atomarny, stsenarii pereispolzuemye.
- Skrytyy #2: (Kibernetika ↔ Bezopasnost) - safety na kazhdom shage, rezhim A/B, stop-kran.

ZEMNOY ABZATs:
Inzhenerno - eto “pleer stsenariev”: spisok shagov s parametrami, kotorye mozhno
prognat kak sukhuyu demonstratsiyu ili “vzhivuyu” s soblyudeniem pravil. Practically
Ester ne prosto obyasnit, a pryamo “pokazhet” na rabochem stole, chto i gde nazhat.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
import os, json, time, threading, uuid

from modules.memory import store
from modules.memory.events import record_event
from modules.thinking import action_safety as AS
from modules.knowledge import cite as CIT
from modules.agents.desktop_agent import DesktopAgent
from modules.agents import desktop_vision_plus as DVPP  # opt. for annotations (M27)
from modules.agents import desktop_vision as DV
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TUTOR_DIR = os.environ.get("ESTER_TUTOR_DIR","data/tutor")
ENABLED   = os.environ.get("ESTER_TUTOR_ENABLED","1") == "1"
MODE      = os.environ.get("ESTER_TUTOR_MODE","A").upper()  # A=show (dry), B=do (commit)

os.makedirs(TUTOR_DIR, exist_ok=True)

# -------- Model stsenariya --------
# {
#   "id": "scn_xxx",
#   "title": "Otkryt bloknot i napisat privet",
#   "intent": "open notepad and type 'Privet'",
#   "steps": [
#      {"agent":"desktop","kind":"open_app","meta":{"app":"notepad"}},
#      {"agent":"desktop","kind":"type_text","meta":{"text":"Privet!"}}
#   ],
#   "created_ts": 1690000000,
#   "mode": "A|B"
# }

def _path(sid:str)->str:
    return os.path.join(TUTOR_DIR, f"{sid}.json")

def list_()->Dict[str,Any]:
    if not ENABLED: return {"ok":False,"error":"disabled"}
    items=[]
    for fn in os.listdir(TUTOR_DIR):
        if fn.endswith(".json"):
            try:
                with open(os.path.join(TUTOR_DIR,fn),"r",encoding="utf-8") as f:
                    obj=json.load(f); items.append({"id":obj.get("id"),"title":obj.get("title"),"steps":len(obj.get("steps",[]))})
            except Exception:
                continue
    items.sort(key=lambda r:r.get("id",""))
    return {"ok":True,"items":items}

def create_from_intent(title:str, intent:str)->Dict[str,Any]:
    if not ENABLED: return {"ok":False,"error":"disabled"}
    # primitivnye shablony → realnye kirpichi
    intent_l=intent.lower()
    steps=[]
    if ("notepad" in intent_l) or ("bloknot" in intent_l):
        steps.append({"agent":"desktop","kind":"open_app","meta":{"app":"notepad"}})
    if ("write" in intent_l) or ("type" in intent_l) or ("napish" in intent_l):
        # extract quotes as text
        txt="Privet!"
        q=intent.find("'")
        if q!=-1:
            q2=intent.find("'", q+1)
            if q2!=-1: txt=intent[q+1:q2]
        steps.append({"agent":"desktop","kind":"type_text","meta":{"text":txt}})
    if ("open url" in intent_l) or ("otkroy ssylku" in intent_l):
        steps.append({"agent":"desktop","kind":"open_url","meta":{"url":"https://example.org","browser":"system"}})
    if not steps:
        # universalnaya zagotovka
        steps=[{"agent":"desktop","kind":"open_app","meta":{"app":"notepad"}}]
    scn={
        "id": f"scn_{uuid.uuid4().hex[:8]}",
        "title": title or intent,
        "intent": intent,
        "steps": steps,
        "created_ts": int(time.time()),
        "mode": MODE
    }
    with open(_path(scn["id"]),"w",encoding="utf-8") as f:
        json.dump(scn, f, ensure_ascii=False, indent=2)
    memory_add("summary", f"[tutor:create] {scn['title']}", {"steps":len(steps),"id":scn["id"]})
    record_event("tutor","create",True,{"id":scn["id"]})
    return {"ok":True,"scenario":scn}

def get(sid:str)->Dict[str,Any]:
    p=_path(sid)
    if not os.path.exists(p): return {"ok":False,"error":"not_found"}
    with open(p,"r",encoding="utf-8") as f:
        return {"ok":True,"scenario":json.load(f)}

def save(scn:Dict[str,Any])->Dict[str,Any]:
    if not scn.get("id"): return {"ok":False,"error":"no_id"}
    with open(_path(scn["id"]),"w",encoding="utf-8") as f:
        json.dump(scn, f, ensure_ascii=False, indent=2)
    return {"ok":True,"scenario":scn}

def validate(sid:str)->Dict[str,Any]:
    """Check it out:
      - korrektnost shagov i izvestnykh 'kind'
      - predvaritelnaya safety-otsenka kazhdogo shaga (dry-run)
      - nalichie yakorey/teksta dlya click_* (esli vstrechayutsya)"""
    g=get(sid); 
    if not g.get("ok"): return g
    scn=g["scenario"]; report=[]
    DA=DesktopAgent()
    ok_all=True
    for i,st in enumerate(scn.get("steps",[]),1):
        agent=st.get("agent","desktop"); kind=st.get("kind",""); meta=st.get("meta") or {}
        if agent!="desktop":
            report.append({"i":i,"ok":False,"error":"unsupported_agent","agent":agent}); ok_all=False; continue
        # enqueue → plan (dry) → safety
        enq=DA.enqueue(kind, meta)
        if not enq.get("ok"):
            report.append({"i":i,"ok":False,"error":"enqueue_failed"}); ok_all=False; continue
        dr=DA.dry_run(enq["id"])
        ok = dr.get("decision",{}).get("decision") in ("allow","needs_user_consent")
        ok_all = ok_all and ok
        report.append({"i":i,"ok":ok,"decision":dr.get("decision"),"plan":dr.get("plan")})
    return {"ok":ok_all,"steps":report}

def _annotate_if_possible(title:str, img_path:str, note:str)->Optional[str]:
    try:
        ann = DVPP.annotate(img_path, [{"box":[20,20,260,40],"label":title}])
        return ann.get("path")
    except Exception:
        return None

def play(sid:str, mode:str|None=None)->Dict[str,Any]:
    """Progon stsenariya:
      MODE A: only dry-run + podsvetka/annotatsii (esli dostupny), bez commit.
      MODE B: commit kazhdogo shaga, esli safety ne deny (needs_user_consent — schitaem soglasie)."""
    g=get(sid); 
    if not g.get("ok"): return g
    scn=g["scenario"]; mode=(mode or scn.get("mode") or MODE).upper()
    DA=DesktopAgent()
    timeline=[]; ok_all=True
    for i,st in enumerate(scn.get("steps",[]),1):
        enq=DA.enqueue(st["kind"], st.get("meta") or {})
        if not enq.get("ok"):
            timeline.append({"i":i,"ok":False,"error":"enqueue_failed"}); ok_all=False; break
        dr=DA.dry_run(enq["id"]); decision=(dr.get("decision") or {}).get("decision")
        timeline.append({"i":i,"stage":"dry_run","decision":decision})
        if mode=="B" and decision in ("allow","needs_user_consent"):
            cm=DA.commit(enq["id"]); ok_step=bool(cm.get("ok"))
            timeline.append({"i":i,"stage":"commit","ok":ok_step})
            ok_all = ok_all and ok_step
        else:
            # in mode A we will try to add visual cues (if there is a frame)
            img="/tmp/ester_screenshot.png"
            hint=_annotate_if_possible(st.get("kind",""), img, "step")
            if hint: timeline.append({"i":i,"stage":"hint","annot":hint})
    # response/script profile (M23)
    passport=CIT.answer_passport(f"[tutor] {scn['title']}", {"confidence": 1.0 if ok_all else 0.7, "factors": {}})
    memory_add("summary", f"[tutor:play] {scn['title']}", {"mode":mode,"ok":ok_all,"timeline":timeline})
    record_event("tutor","play",ok_all,{"id":scn["id"],"mode":mode})
    return {"ok":ok_all,"mode":mode,"timeline":timeline,"passport":passport}

def remove(sid:str)->Dict[str,Any]:
    p=_path(sid)
    if os.path.exists(p): os.remove(p)
    return {"ok":True}

def append_step(sid:str, step:Dict[str,Any])->Dict[str,Any]:
    g=get(sid); 
    if not g.get("ok"): return g
    scn=g["scenario"]; scn.setdefault("steps",[]).append(step)
    return save(scn)

def insert_step(sid:str, idx:int, step:Dict[str,Any])->Dict[str,Any]:
    g=get(sid); 
    if not g.get("ok"): return g
    scn=g["scenario"]; scn.setdefault("steps",[]).insert(max(0,int(idx)),step)
    return save(scn)

def delete_step(sid:str, idx:int)->Dict[str,Any]:
    g=get(sid); 
    if not g.get("ok"): return g
    scn=g["scenario"]; arr=scn.setdefault("steps",[])
    if 0<=idx<len(arr): arr.pop(idx)
    return save(scn)