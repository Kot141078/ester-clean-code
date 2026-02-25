# -*- coding: utf-8 -*-
"""modules/persona_style_ext.py - expanded auditorii i e-mail shablony dlya Ester.

MOSTY:
- (Yavnyy) Naraschivaet bazovyy persona_style: addavlyaet bank/gov/medic/engineer/teacher/investor.
- (Skrytyy #1) Unifikatsiya pisma/messendzhera: odinakovye intent-struktury → vosproizvodimye teksty.
- (Skrytyy #2) Control dliny/registra/terminov: anti-“kantselyarit” i akkuratnaya formalnost.

ZEMNOY ABZATs:
Pozvolyaet Ester pisat pisma raznym tipam poluchateley “kak chelovek” - korrektno i umestno, bez shokiruyuschey robotnosti.

# c=a+b"""
from __future__ import annotations
from typing import Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
try:
    # Basic engine from previous packages
    from modules.persona_style import choose_style as base_choose_style, render_message as base_render_message
except Exception:
    # If the base file is not in the POTHONPATH path, we will create minimal stubs
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
        "traits": ["tochnost formulirovok", "without emotional assessments", "korrektnye ssylki na daty/simptomy/naznacheniya"],
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
        "traits": ["po punktam", "version/task numbers", "minimum value judgments"],
    },
    "teacher": {
        "greeting": "Zdravstvuyte",
        "closing": "Thank you for your attention",
        "signature": "—",
        "register": "neutral",
        "traits": ["druzhelyubno", "korrektno", "bez slozhnykh terminov"],
    },
    "investor": {
        "greeting": "Zdravstvuyte",
        "closing": "S uvazheniem",
        "signature": "—",
        "register": "business-formal",
        "traits": ["clear value", "tsifry/metriki", "kratkiy call-to-action"],
    },
}

# Email layouts (slightly different from short messages)
_EMAIL_TEMPL = {
    "letter": "{greeting},\n\n{body}\n\n{closing}\n{signature}",
    "update": "{greeting},\n\n{body}\n\n{closing}\n{signature}",
    "request": "{greeting},\n\n{body}\n\n{closing}\n{signature}",
    "reminder": "{greeting},\n\nNapominayu: {body}\n\n{closing}\n{signature}",
    "apology": "ZZF0Z,\n\nI'm sorry: ZZF1ZZ\n\nZZF2ZZ\nZFzZZ",
}

def choose_style_ext(audience: str, intent: str) -> Dict:
    a = (audience or "neutral").lower()
    i = (intent or "update").lower()
    st = base_choose_style(a, i)
    prof = dict(st.get("profile", {}))
    if a in _EXTRA:
        prof.update(_EXTRA[a])  # expanding the profile
    tmpl = _EMAIL_TEMPL.get(i, st.get("template"))
    return {"audience": a, "intent": i, "profile": prof, "template": tmpl}

def render_email(audience: str, intent: str, content: str) -> str:
    st = choose_style_ext(audience, intent)
    prof = st["profile"]
    tmpl = st["template"]
    body = (content or "").strip()

    # Soft de-“officialization”
    repl = {
        "osuschestvit": "sdelat",
        "neobkhodimo": "nuzhno",
        "vysheperechislennoe": "opisannoe vyshe",
        "in connection with which": "poetomu",
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

# For short messages you can still use base_render_message
def render_message_ext(audience: str, intent: str, content: str) -> str:
    return base_render_message(audience, intent, content)