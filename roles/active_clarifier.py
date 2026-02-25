# -*- coding: utf-8 -*-
"""roles/active_clarifier.py — generator vezhlivykh utochneniy pri vysokoy neopredelennosti.

MOSTY:
- (Yavnyy) suggest(agent_id, channel, topic?) → korotkiy, ne navyazchivyy vopros pod vybrannyy kanal.
- (Skrytyy #1) Osnovano na profile i tekuschikh yarlykakh, bez LLM - bezopasno i obyasnimo.
- (Skrytyy #2) Mozhet podklyuchatsya v nudges/botov kak istochnik “obuchayuschikh” pingov.

ZEMNOY ABZATs:
Esli Ester chego-to ne znaet o cheloveke - ask odin raz, kratko i po delu, a potom zapomnit.

# c=a+b"""
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
        return f"It’s better to help ZZF0ZKhtuba, please tell me: ZZF1ZZ?"
    if "pilot" in labels:
        return f"ZZF0ZZI Sometimes quick trips are needed. Can you tell me when you are usually available at night?"
    if "lawyer" in labels:
        return f"ZЗФ0ЗЗЗЗЗЗУ please, your preferred style of communication: short abstracts or detailed letters?"
    if "student" in labels:
        return f"ZZF0Z Please tell me which hours are most convenient for you for tasks and messages?"
    # defoltno — pro dostupnost
    return f"ZZF0ZKhtubs not to be distracted, please tell me at what hours it is more convenient for you to receive messages?"