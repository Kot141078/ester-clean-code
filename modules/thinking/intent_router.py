# -*- coding: utf-8 -*-
"""
modules/thinking/intent_router.py — prostaya interpretatsiya namereniy (NL → deystviya) dlya Ester.

Podkhod:
- Nabor pravil/shablonov (ru/en) → map k atomarnym shagam RPA i makrosam.
- Proverka soglasiya po domenu ("rpa.*", "install.*").
- Proverka nalichiya prilozheniya; esli otsutstvuet — vozvrat "need_install" s planom.

MOSTY:
- Yavnyy: (Rech ↔ Volya) tekst zaprosa konvertiruetsya v «volevoy plan»: shagi RPA/makrosy.
- Skrytyy #1: (Bayes ↔ Infoteoriya) determinirovannye shablony + malenkiy slovar umenshayut dvusmyslennost.
- Skrytyy #2: (Kibernetika ↔ Kontrol) rezultat vsegda v odnom formate: plan → execute → audit.

ZEMNOY ABZATs:
Lokalno, oflayn, bez vneshnego NLP. Rasshiryaetsya pravilami. V sluchae otsutstviya prilozheniya — zaprashivaet ustanovku.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import re

from modules.thinking.consent_manager import get_effective
from modules.ops.app_capabilities import is_installed, install_plan
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Otvet planirovschika intentov
# {ok, actions:[{"type":"macro"|"rpa","name":..., "args":{...}}]}
def parse(text: str) -> Dict[str, Any]:
    q = (text or "").strip().lower()
    actions: List[Dict[str, Any]] = []

    # --- Pravila (prostye evristiki) ---
    # 1) "pokazhi kak polzovatsya <proga>" → otkryt progu i napechatat podskazku
    m = re.search(r"pokazhi.*polzovatsya\s+([a-za-ya0-9\-_\.]+)", q)
    if m:
        app = m.group(1)
        target = map_app_name(app)
        if not ensure_app(target):
            return need_install_resp(target)
        actions.append({"type": "macro", "name": "open_portal_and_type", "args": {"app": target, "text": "Demonstratsiya: shag 1..."}})
        return {"ok": True, "domain": "rpa.demo", "actions": actions}

    # 2) "otkroy <proga>", "zapusti <proga>"
    m = re.search(r"(otkroy|zapusti)\s+([a-za-ya0-9\-_\.]+)", q)
    if m:
        app = map_app_name(m.group(2))
        if not ensure_app(app):
            return need_install_resp(app)
        actions.append({"type": "rpa", "name": "open", "args": {"app": app}})
        return {"ok": True, "domain": "rpa.open", "actions": actions}

    # 3) "sygraem", "davay sygraem" → kooperativnyy rezhim (ozhidaem ukazanie peer)
    if "sygra" in q or "igra" in q:
        return {"ok": True, "domain": "rpa.coop", "actions": [{
            "type": "info",
            "name": "coop_request",
            "args": {"hint": "Ukazhi IP/khost naparnika i nazvanie okna/igry. Esli net igry — skazhi otkuda stavit."}
        }]}

    # 4) "ustanovi <proga>" → zapros istochnika
    m = re.search(r"ustanovi\s+([a-za-ya0-9\-_\.]+)", q)
    if m:
        app = map_app_name(m.group(1))
        return need_install_resp(app)

    # Follbek — prosto podskazka
    return {"ok": True, "domain": "rpa.help", "actions": [{"type":"info","name":"noop","args":{"hint":"Skazhi: «pokazhi kak polzovatsya notepad»"}}]}

def map_app_name(x: str) -> str:
    x = x.lower()
    aliases = {
        "bloknot": "notepad",
        "notpad": "notepad",
        "terminal": "xterm",
        "chrome": "chrome",
        "khrom": "chrome",
        "pauershell": "powershell"
    }
    return aliases.get(x, x)

def ensure_app(app: str) -> bool:
    return is_installed(app)

def need_install_resp(app: str) -> Dict[str, Any]:
    plan = install_plan(app)
    return {"ok": False, "need_install": True, "app": app, "plan": plan, "domain": "install."+app}

def domain_needs_consent(domain: str) -> bool:
    return get_effective(domain) != "allow"