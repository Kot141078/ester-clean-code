# -*- coding: utf-8 -*-
"""modules/thinking/consent_manager.py - menedzher soglasiy i politik deystviy Ester.

Stsenarii:
- ask_once: ask polzovatelya i zapomnit razreshenie na domen deystviy (for example, "rpa.*", "install.*", "vm.*").
- session_only: razreshenie deystvitelno do restarta protsessa.
- deny: prohibited.

Khranilische: data/security/consent.json (persist), a takzhe protsessnaya sessiya (in-memory).

MOSTY:
- Yavnyy: (Volya ↔ Bezopasnost) volevoe deystvie gated cherez yavnoe soglasie po domenam.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) yavnye domeny umenshayut neodnoznachnost zaprosa.
- Skrytyy #2: (Psikhologiya ↔ UX) sootvetstvie chelovecheskoy modeli “razreshit odin raz/navsegda”.

ZEMNOY ABZATs:
Lokalnyy oflayn-fayl consent.json; API otdaet, nuzhno li sprosit, i fiksiruet vybor. 
Podderzhka wildcards cherez prefiksy domena (for example, "rpa." pokryvaet "rpa.click", "rpa.open").

# c=a+b"""
from __future__ import annotations
import os, json, time
from typing import Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PROJECT_ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
SEC_DIR = os.path.join(PROJECT_ROOT, "data", "security")
CONSENT_PATH = os.path.join(SEC_DIR, "consent.json")

_session: Dict[str, str] = {}  # domain -> "allow"/"deny"/"ask_once"

def _ensure():
    os.makedirs(SEC_DIR, exist_ok=True)
    if not os.path.exists(CONSENT_PATH):
        with open(CONSENT_PATH, "w", encoding="utf-8") as f:
            json.dump({"rules": {}}, f, ensure_ascii=False, indent=2)

def _load() -> Dict[str, str]:
    _ensure()
    with open(CONSENT_PATH, "r", encoding="utf-8") as f:
        return (json.load(f) or {}).get("rules", {})

def _save(rules: Dict[str, str]) -> None:
    _ensure()
    with open(CONSENT_PATH, "w", encoding="utf-8") as f:
        json.dump({"rules": rules}, f, ensure_ascii=False, indent=2)

def get_effective(domain: str) -> str:
    """Vozvraschaet "allow"/"deny"/"ask" dlya domena.
    Logika poiska: tochnoe sovpadenie → poisk po prefiksu "xxx." (shortening).
    Sessiya pereopredelyaet na vremya protsessa."""
    if domain in _session:
        mode = _session[domain]
        if mode in ("allow", "deny"):
            return mode
        # "ask_once" → until now ne vstretili konkretnogo resheniya, vernem ask
    rules = _load()
    sub = domain
    while True:
        if sub in rules:
            v = rules[sub]
            if v == "allow":
                return "allow"
            if v == "deny":
                return "deny"
            return "ask"
        if "." in sub:
            sub = sub.rsplit(".", 1)[0]
        else:
            break
    # ne naydeno
    if domain in _session and _session[domain] == "ask_once":
        return "ask"
    return "ask"

def set_rule(domain: str, mode: str, persist: bool = True) -> None:
    assert mode in ("allow", "deny", "ask", "ask_once")
    if persist and mode in ("allow", "deny", "ask"):
        rules = _load()
        rules[domain] = mode
        _save(rules)
    else:
        _session[domain] = mode