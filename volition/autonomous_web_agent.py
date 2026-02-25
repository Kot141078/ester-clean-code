# -*- coding: utf-8 -*-
"""volition/autonomous_web_agent.py - evristicheskiy agent, kotoryy reshaet: nuzhen li internet.

YaVNYY MOST: c = a + b
  a - kontekst/vopros polzovatelya,
  b - protsedura "reshi i poischi" (evristiki + sanitayzing + limity),
  c - rezultat poiska (korotkaya vyzhimka), kotoryy mozhno podmeshat v reasoning.

SKRYTYE MOSTY:
  - Ashby: evristiki dayut "raznoobrazie" triggerov, no my derzhim tormoza (limity/sanitayzing),
    chtoby raznoobrazie ne prevraschalos v khaos.
  - Cover&Thomas: szhatie (extract_query) i korotkaya vydacha - eto kontrol kanala.
  - Dhammapada (praktika): "ne govorit lishnego" - agent otdaet tolko vyzhimku, bez boltovni.

ZEMNOY ABZATs (inzheneriya/anatomiya):
  Agent - kak nadpochechniki: vklyuchaetsya tolko na trigger (stress/defitsit informatsii) i bystro
  uspokaivaetsya. Esli on rabotaet vsegda - budet khronicheskiy kortizol (nagruzka/shum)."""
from __future__ import annotations

import os
import re
from typing import Optional

from bridges.internet_access import InternetAccess
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class AutonomousWebAgent:
    def __init__(self) -> None:
        self.internet = InternetAccess()
        default = "nayti,poischi,poischite,gugl,poisk,informatsiya,proverit,prover,obnovit,kurs,tsena,segodnya,seychas"
        raw = os.getenv("WEB_AGENT_TRIGGER_WORDS", default)
        self.trigger_words = [w.strip().lower() for w in raw.split(",") if w.strip()]

    def should_search(self, context: str) -> bool:
        text = (context or "").strip().lower()
        if not text:
            return False
        if re.search(r"\bkto\s+takoy\b|\bchto\s+takoe\b|\bwhat\s+is\b|\bwho\s+is\b", text):
            return True
        return any(w in text for w in self.trigger_words)

    def extract_query(self, context: str) -> str:
        text = (context or "").strip()
        if not text:
            return ""
        text = re.sub(r"^(naydi|poischi|prover|obnovi|skazhi|uznay)\s+","", text, flags=re.I).strip()
        m = re.search(r"\"([^\"]{3,256})\"", text)
        if m:
            text = m.group(1).strip()
        return text

    def decide_and_search(self, context: str) -> Optional[str]:
        mode = os.getenv("WEB_AGENT", "auto").strip().lower()
        if mode == "never":
            return None
        if mode != "always" and not self.should_search(context):
            return None

        q = self.extract_query(context)
        q = self.internet.sanitize_query(q)
        if not q:
            return None

        return self.internet.search_text(q, max_results=3)