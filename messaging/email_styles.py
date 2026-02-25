# -*- coding: utf-8 -*-
"""messaging/email_styles.py - mepping profilya poluchatelya v stil pisma (ton, forma, struktura).

MOSTY:
- (Yavnyy) pick_style(vec, labels, kind_hint, signature_opt) → dict s polyami {formality, direct, empathy, brevity, subject_prefix, greeting, signoff}.
- (Skrytyy #1) Agregator po klyucham iz roles.store uzhe est v messaging.styler - zdes povtor logiki ne nuzhen; modul prinimaet gotovyy vektor/yarlyki.
- (Skrytyy #2) Parametry stilya ispolzuyutsya kak v evristicheskom generatore, tak i v LLM-rezhime B (edinyy plan).

ZEMNOY ABZATs:
Yuristu - chetko i formalno, studentu - prosche i druzhelyubnee, drugu - korotko i teplo. Vybor tona - funktsiya profilya, a ne “magiya”.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _base_style() -> Dict[str, Any]:
    return dict(formality=0.6, direct=0.6, empathy=0.5, brevity=0.5,
                subject_prefix="", greeting="Zdravstvuyte", signoff="S uvazheniem")

def pick_style(vec: Dict[str,float] | None, labels: list[str] | None, kind_hint: Optional[str], signature_opt: str = "soft") -> Dict[str, Any]:
    v = vec or {}
    labs = set(labels or [])
    s = _base_style()

    # Shift parameters along labels/axes
    if "lawyer" in labs or v.get("law",0) > 0.7:
        s["formality"]=0.95; s["direct"]=0.85; s["empathy"]=0.4; s["subject_prefix"]="Zapros: "; s["greeting"]="Uvazhaemye kollegi"; s["signoff"]="S uvazheniem"
    if "teacher" in labs or v.get("edu",0) > 0.7:
        s["formality"]=max(s["formality"],0.8); s["greeting"]="Dobryy den"; s["signoff"]="S uvazheniem"
    if "student" in labs or v.get("edu",0) > 0.6 and v.get("availability",0)>0.6:
        s["formality"]=min(s["formality"],0.4); s["empathy"]=max(s["empathy"],0.8); s["greeting"]="Privet"; s["signoff"]="Spasibo"
    if "coordinator" in labs or v.get("comm",0)>0.75:
        s["direct"]=0.85; s["brevity"]=0.8; s["subject_prefix"]="Brif: "; s["greeting"]="Kollegi"
    if "doctor" in labs or v.get("med",0)>0.7:
        s["formality"]=0.85; s["empathy"]=0.7; s["greeting"]="Dobryy den"; s["signoff"]="S uvazheniem"
    if v.get("creative",0)>0.75:
        s["empathy"]=max(s["empathy"],0.7)

    # Khint imeet prioritet
    if kind_hint:
        k = kind_hint.lower()
        if k == "lawyer":
            s.update(formality=0.95, direct=0.9, empathy=0.4, subject_prefix="Zapros: ", greeting="Uvazhaemye kollegi", signoff="S uvazheniem")
        elif k == "student":
            s.update(formality=0.35, direct=0.5, empathy=0.85, subject_prefix="", greeting="Privet", signoff="Spasibo")
        elif k == "friend":
            s.update(formality=0.3, direct=0.6, empathy=0.9, subject_prefix="", greeting="Privet", signoff="Obnimayu")
        elif k == "business":
            s.update(formality=0.85, direct=0.8, empathy=0.5, subject_prefix="Vopros: ", greeting="Dobryy den", signoff="S uvazheniem")

    # Podpis
    if signature_opt == "none":
        s["signoff"] = ""
    elif signature_opt == "formal":
        s["signoff"] = "S uvazheniem"
    else:  # soft
        s["signoff"] = s.get("signoff","Spasibo")

    return s