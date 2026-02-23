# -*- coding: utf-8 -*-
"""
messaging/styler.py — personalizatsiya teksta soobscheniya na osnove profilya roli.

MOSTY:
- (Yavnyy) render_for_keys(keys, intent, adapt_kind?) → odin tekst, adaptirovannyy pod dominiruyuschiy profil poluchateley.
- (Skrytyy #1) Profile podtyagivaetsya iz roles.store (cherez obratnyy indeks contact_key→agent_id).
- (Skrytyy #2) Myagkaya degradatsiya: esli profili neizvestny — vozvraschaetsya iskhodnyy intent.

ZEMNOY ABZATs:
Chtoby «ne pugat», Ester podstraivaet ton: yuristu — formalno i chetko, studentu — prosche i druzhelyubnee,
koordinatoru — kratkiy brif.

# c=a+b
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
from roles.store import get_agent_by_key, get_profile
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _aggregate_vectors(keys: List[str]) -> Dict[str, float]:
    acc: Dict[str,float] = {}
    n=0
    for k in keys:
        ag = get_agent_by_key(k)
        if not ag: continue
        prof = get_profile(ag)
        if not prof: continue
        for d,v in (prof.get("vector") or {}).items():
            acc[d] = acc.get(d,0.0) + float(v)
        n+=1
    if n>0:
        for d in list(acc.keys()):
            acc[d] = acc[d]/n
    return acc

def _style_params(vec: Dict[str,float], kind: Optional[str]) -> Dict[str,Any]:
    # bazovye parametry
    formality = 0.5; direct = 0.5; empathy = 0.5; brevity = 0.5
    if vec.get("law",0)>0.6: formality = 0.9; direct = 0.7; empathy = 0.4
    if vec.get("edu",0)>0.6 and vec.get("student",0) is None: formality = max(formality,0.7)
    if vec.get("student",0) or vec.get("availability",0)>0.6: formality = min(formality,0.4)
    if vec.get("comm",0)>0.7: direct = 0.7; brevity = 0.7
    if vec.get("creative",0)>0.7: empathy = 0.7
    if kind == "friend": empathy = max(empathy, 0.8); formality = min(formality,0.4)
    if kind == "lawyer": formality = max(formality, 0.9); direct = max(direct,0.8)
    if kind == "student": empathy = max(empathy,0.8); direct = min(direct,0.5); formality = min(formality,0.4)
    return {"formality":formality,"direct":direct,"empathy":empathy,"brevity":brevity}

def _render(intent: str, p: Dict[str,Any]) -> str:
    # prostaya stilizatsiya bez vneshnikh zavisimostey
    t = intent.strip()
    if p["formality"] >= 0.8:
        t = f"Uvedomlenie: {t}"
    if p["direct"] >= 0.8:
        t = t if t.endswith(".") else t + "."
    if p["empathy"] >= 0.7:
        t = "Pozhaluysta, " + t[0].lower() + t[1:]
    if p["brevity"] >= 0.7 and len(t) > 180:
        t = t[:177].rstrip() + "…"
    return t

def render_for_keys(keys: List[str], intent: str, adapt_kind: Optional[str] = None) -> str:
    vec = _aggregate_vectors(keys)
    if not vec:
        # profili neizvestny — otdaem iskhodnyy tekst
        return intent
    p = _style_params(vec, adapt_kind)
    return _render(intent, p)