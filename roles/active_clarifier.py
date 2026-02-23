# -*- coding: utf-8 -*-
"""
roles/active_clarifier.py — generator vezhlivykh utochneniy pri vysokoy neopredelennosti.

MOSTY:
- (Yavnyy) suggest(agent_id, channel, topic?) → korotkiy, ne navyazchivyy vopros pod vybrannyy kanal.
- (Skrytyy #1) Osnovano na profile i tekuschikh yarlykakh, bez LLM — bezopasno i obyasnimo.
- (Skrytyy #2) Mozhet podklyuchatsya v nudges/botov kak istochnik «obuchayuschikh» pingov.

ZEMNOY ABZATs:
Esli Ester chego-to ne znaet o cheloveke — sprosit odin raz, kratko i po delu, a potom zapomnit.

# c=a+b
"""
from __future__ import annotations

from typing import Optional
from roles.store import get_profile
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def suggest(agent_id: str, channel: str = "telegram", topic: Optional[str] = None) -> str:
    prof = get_profile(agent_id) or {"labels":[], "vector":{}}
    labels = prof.get("labels") or []
    # prostye tonalnye varianty po kanalu
    pre = "Privet! " if channel in ("telegram","whatsapp","sms") else "Dobryy den. "
    if topic:
        return f"{pre}Chtoby luchshe pomogat, podskazhite, pozhaluysta: {topic}?"
    if "pilot" in labels:
        return f"{pre}Inogda nuzhny bystrye vyezdy. Skazhete, kogda vy obychno dostupny v nochnoe vremya?"
    if "lawyer" in labels:
        return f"{pre}Utochnite, pozhaluysta, predpochitaemyy stil obscheniya: kratkie tezisy ili podrobnye pisma?"
    if "student" in labels:
        return f"{pre}Skazhite, pozhaluysta, kakie chasy vam udobnee dlya zadach i soobscheniy?"
    # defoltno — pro dostupnost
    return f"{pre}Chtoby ne otvlekat, podskazhite, pozhaluysta, v kakie chasy vam udobnee poluchat soobscheniya?"