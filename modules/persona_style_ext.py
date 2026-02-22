# -*- coding: utf-8 -*-
"""
modules/persona_style_ext.py — rasshirennye auditorii i e-mail shablony dlya Ester.

MOSTY:
- (Yavnyy) Naraschivaet bazovyy persona_style: dobavlyaet bank/gov/medic/engineer/teacher/investor.
- (Skrytyy #1) Unifikatsiya pisma/messendzhera: odinakovye intent-struktury → vosproizvodimye teksty.
- (Skrytyy #2) Kontrol dliny/registra/terminov: anti-«kantselyarit» i akkuratnaya formalnost.

ZEMNOY ABZATs:
Pozvolyaet Ester pisat pisma raznym tipam poluchateley «kak chelovek» — korrektno i umestno, bez shokiruyuschey robotnosti.

# c=a+b
"""
from __future__ import annotations
from typing import Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
try:
    # Bazovyy dvizhok iz predyduschikh paketov
    from modules.persona_style import choose_style as base_choose_style, render_message as base_render_message
except Exception:
    # Esli bazovogo fayla net v puti PYTHONPATH — sozdadim minimalnye zaglushki
    def base_choose_style(audience: str, intent: str) -> Dict:
        return {"audience": audience, "intent": intent, "profile": {"greeting": "Zdravstvuyte","closing":"S uvazheniem","signature":"—","register":"neutral","traits":[]}, "template": "{greeting}, {body} {closing}."}
    def base_render_message(audience: str, intent: str, content: str) -> str:
        st = base_choose_style(audience,intent)
        return f"{st['profile']['greeting']}, {content} {st['profile']['closing']}."

# Dopolnitelnye profili (ton i terminy)
_EXTRA = {
    "medic": {
        "greeting": "Dobryy den",
        "closing": "S uvazheniem",
        "signature": "—",
        "register": "formal",
        "traits": ["tochnost formulirovok", "bez emotsionalnykh otsenok", "korrektnye ssylki na daty/simptomy/naznacheniya"],
    },
    "bank": {
        "greeting": "Zdravstvuyte",
        "closing": "S uvazheniem",
        "signature": "—",
        "register": "formal",
        "traits": ["nomera schetov/dogovorov", "tochnye daty", "bez zhargonov"],
    },
    "gov": {
        "greeting": "Uvazhaemye gospoda",
        "closing": "S uvazheniem",
        "signature": "—",
        "register": "formal",
        "traits": ["delovoy stil", "ssylki na nomer dela/zayavleniya", "vezhlivye formuly"],
    },
    "engineer": {
        "greeting": "Zdravstvuyte",
        "closing": "Spasibo",
        "signature": "—",
        "register": "neutral-formal",
        "traits": ["po punktam", "versii/nomera zadach", "minimum otsenochnykh suzhdeniy"],
    },
    "teacher": {
        "greeting": "Zdravstvuyte",
        "closing": "Spasibo za vnimanie",
        "signature": "—",
        "register": "neutral",
        "traits": ["druzhelyubno", "korrektno", "bez slozhnykh terminov"],
    },
    "investor": {
        "greeting": "Zdravstvuyte",
        "closing": "S uvazheniem",
        "signature": "—",
        "register": "business-formal",
        "traits": ["chetkaya tsennost", "tsifry/metriki", "kratkiy call-to-action"],
    },
}

# E-mail makety (slegka otlichayutsya ot korotkikh soobscheniy)
_EMAIL_TEMPL = {
    "letter": "{greeting},\n\n{body}\n\n{closing}\n{signature}",
    "update": "{greeting},\n\n{body}\n\n{closing}\n{signature}",
    "request": "{greeting},\n\n{body}\n\n{closing}\n{signature}",
    "reminder": "{greeting},\n\nNapominayu: {body}\n\n{closing}\n{signature}",
    "apology": "{greeting},\n\nProshu proscheniya: {body}\n\n{closing}\n{signature}",
}

def choose_style_ext(audience: str, intent: str) -> Dict:
    a = (audience or "neutral").lower()
    i = (intent or "update").lower()
    st = base_choose_style(a, i)
    prof = dict(st.get("profile", {}))
    if a in _EXTRA:
        prof.update(_EXTRA[a])  # rasshiryaem profil
    tmpl = _EMAIL_TEMPL.get(i, st.get("template"))
    return {"audience": a, "intent": i, "profile": prof, "template": tmpl}

def render_email(audience: str, intent: str, content: str) -> str:
    st = choose_style_ext(audience, intent)
    prof = st["profile"]
    tmpl = st["template"]
    body = (content or "").strip()

    # Myagkaya de-«kantselyarizatsiya»
    repl = {
        "osuschestvit": "sdelat",
        "neobkhodimo": "nuzhno",
        "vysheperechislennoe": "opisannoe vyshe",
        "v svyazi s chem": "poetomu",
    }
    for k,v in repl.items():
        body = body.replace(k, v)

    msg = tmpl.format(
        greeting=prof.get("greeting","Zdravstvuyte"),
        body=body,
        closing=prof.get("closing","S uvazheniem"),
        signature=prof.get("signature","—"),
    )
    return "\n".join([ln.rstrip() for ln in msg.splitlines()]).strip()

# Dlya korotkikh soobscheniy mozhno po-prezhnemu ispolzovat base_render_message
def render_message_ext(audience: str, intent: str, content: str) -> str:
    return base_render_message(audience, intent, content)