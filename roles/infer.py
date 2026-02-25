# -*- coding: utf-8 -*-
"""roles/infer.py - izvlechenie priznakov iz vzaimodeystviy i obnovlenie profiley (EMA), plyus A/B-most k LLM.

MOSTY:
- (Yavnyy) infer_features(text) → {dims, labels, trace}; update_vector(prev, obs, alpha) → newyy vector.
- (Skrytyy #1) Rezhimy: A=evristiki, B=LLM_PROVIDER; esli B nedostupen - avto-otkat na A (bystryy avtokatbek).
- (Skrytyy #2) label_by_ontology(vector) sopostavlyaet vektor s roles/ontology, vydaet top-yarlyki.

ZEMNOY ABZATs:
Ester "listen" to, chto lyudi i mashiny uzhe govoryat/delayut, akkuratno obnovlyaet predstavlenie o cheloveke
i, ne navyazyvaya yarlykov, vyvodit rabochie predskazaniya - chtoby luchshe sobirat komandy.

# c=a+b"""
from __future__ import annotations

import os, re, importlib
from typing import Dict, Any, List, Tuple

from roles.ontology import get_ontology
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_DIMS = [d.strip() for d in (os.getenv("ROLE_TOP_DIMS") or
          "experience,reaction,calm,coop,lead,law,tech,med,edu,craft,comm,creative,stamina,availability").split(",")]

# --- Heuristic dictionaries (ru/en, easy to expand) ---
_LEX = {
    "reaction":  [r"\bbystr(o|yy|ee)\b", r"\bskor(o|ost)\b", r"\breact|fast|quick\b"],
    "experience":[r"\bstazh\b", r"\bopytn(yy|aya)\b", r"\bsenior\b", r"\bveteran\b"],
    "calm":      [r"\bspoko(en|yno)\b", r"\bbez paniki\b", r"\bcalm|steady\b"],
    "coop":      [r"\bkomandn(yy|aya)\b", r"\bvmeste\b", r"\bteam( ?player)?\b"],
    "lead":      [r"\brukovod(il|stvo)\b", r"\blid\b", r"\blead(ing)?\b"],
    "law":       [r"\bzakon\b", r"\bdogovor\b", r"\bpravo\b", r"\blaw|contract\b"],
    "tech":      [r"\binzhener\b", r"\bsborka\b", r"\bproshivk(a|i)\b", r"\bengineer|firmware|debug\b"],
    "med":       [r"\bmedits\b|\bvrach\b|\bfirst aid\b"],
    "edu":       [r"\bprepoda(v|yu)\b|\bobuch(ayu|enie)\b|\buchus\b|\bstudy|teach\b"],
    "craft":     [r"\bremont\b|\bpayk(a|i)\b|\bstanok\b|\blathe|solder\b"],
    "comm":      [r"\bsvyaz(|atsya)\b|\bobscha(yu|em)\b|\bbrief\b|\breport\b"],
    "creative":  [r"\bide(ya|i)\b|\bdizayn\b|\brisuyu\b|\bcreative|design\b"],
    "stamina":   [r"\bsmen(a|y)\b|\bnoch(|ami)\b|\bdolgo\b|\b12h\b"],
    "availability":[r"\bseychas\b|\bonlayn\b|\bdostupen\b|\b24/7\b|\bsvoboden\b"],
    # transport/pilot:
    "pilot":     [r"\bpilot\b|\bdron\b|\bmavik\b|\bfpv\b|\buav|uas\b"],
    "driver":    [r"\bvoditel\b|\bgruz\b|\bpikap\b|\bpickup|driver\b"],
    "courier":   [r"\bdostav\b|\bkurer\b|\bpoezdka\b|\bdeliv(ery|er)\b"],
    "lawyer":    [r"\badvokat\b|\byurist\b|\blawyer\b"],
    "doctor":    [r"\bvrach\b|\bmedik\b|\bdoctor|paramedic\b"],
    "teacher":   [r"\buchitel\b|\bnastavnik\b|\bteacher|mentor\b"],
    "student":   [r"\bstudent\b|\buchenik\b|\bstudent\b"],
    "coordinator":[r"\bkoordinator\b|\bdispetcher\b|\bdispatcher|coordinator\b"],
    "negotiator":[r"\bperegovor\b|\bmediator\b|\bnegotiat(e|or)\b"],
}

def _try_llm(text: str) -> Dict[str, Any] | None:
    if (os.getenv("ROLE_INFER_MODE","A").upper() != "B"):
        return None
    spec = os.getenv("ROLE_LLM_PROVIDER","").strip()
    if not spec: return None
    try:
        mod_name, func_name = spec.split(":",1)
        fn = getattr(importlib.import_module(mod_name), func_name)
        return fn(text)
    except Exception:
        return None  # avtokatbek

def _score_by_patterns(text: str) -> Dict[str, float]:
    text_l = text.lower()
    scores: Dict[str, float] = {d:0.0 for d in _DIMS}
    # basic shifts by keywords
    for dim, pats in _LEX.items():
        for p in pats:
            if re.search(p, text_l):
                if dim in scores:
                    scores[dim] += 0.2
                # domenye yarlyki → proektsii na bazovye osi
                if dim == "pilot":
                    scores["reaction"] += 0.15; scores["tech"] += 0.1
                if dim == "courier":
                    scores["availability"] += 0.15; scores["stamina"] += 0.1
                if dim == "lawyer":
                    scores["law"] += 0.25; scores["comm"] += 0.1
                if dim == "doctor":
                    scores["med"] += 0.25; scores["calm"] += 0.1
                if dim == "teacher":
                    scores["edu"] += 0.2; scores["comm"] += 0.1
                if dim == "student":
                    scores["edu"] += 0.15; scores["availability"] += 0.1
                if dim == "coordinator":
                    scores["lead"] += 0.15; scores["comm"] += 0.15; scores["coop"] += 0.1
                if dim == "negotiator":
                    scores["comm"] += 0.2; scores["calm"] += 0.1
                if dim == "driver":
                    scores["reaction"] += 0.1; scores["stamina"] += 0.1
    # normirovka [0..1]
    for k,v in scores.items():
        scores[k] = max(0.0, min(1.0, v))
    return scores

def infer_features(text: str) -> Dict[str, Any]:
    """
    Vozvraschaet {"dims":{...}, "labels":[...], "trace":[...]}
    """
    res = _try_llm(text)
    if res and isinstance(res, dict) and "dims" in res:
        return res  # rezhim B
    # rezhim A
    dims = _score_by_patterns(text)
    labels: List[str] = []
    # heuristic label for explicit domain
    for name in ("lawyer","doctor","teacher","student","pilot","courier","coordinator","negotiator","driver"):
        if any(re.search(p, text.lower()) for p in _LEX.get(name,[])):
            labels.append(name)
    trace = [f"heuristic:{k}={v:.2f}" for k,v in dims.items() if v>0]
    return {"dims": dims, "labels": labels, "trace": trace}

def update_vector(prev: Dict[str,float], obs: Dict[str,float], alpha: float) -> Dict[str,float]:
    out = {}
    for d in set(list(prev.keys())+list(obs.keys())):
        p = float(prev.get(d, 0.0)); o = float(obs.get(d, 0.0))
        out[d] = max(0.0, min(1.0, (1-alpha)*p + alpha*o))
    return out

def label_by_ontology(vector: Dict[str,float], top_k: int = 3) -> List[str]:
    ont = get_ontology()
    roles = ont.get("roles",{})
    scores: List[Tuple[str,float]] = []
    for rid, cfg in roles.items():
        hints = cfg.get("hints",{}) or {}
        # cosine is valid here conditionally: we take a scalar and normalize it to #hintz
        s = 0.0
        for k, w in hints.items():
            s += float(vector.get(k,0.0))*float(w)
        if hints:
            s /= max(1.0, sum(float(w) for w in hints.values()))
        scores.append((rid, s))
    scores.sort(key=lambda x:x[1], reverse=True)
    return [r for r,_ in scores[:max(1, top_k)]]