# -*- coding: utf-8 -*-
"""
tests/test_ner_linker.py — bazovaya proverka NER-linkovschika.

Proveryaem:
  • extract_entities() vozvraschaet khotya by odnu suschnost dlya tipichnogo teksta.
  • upsert_entities() otrabatyvaet (libo napryamuyu, libo v fallback-ochered).

Mosty:
- Yavnyy: (Memory ↔ KG) suschnosti izvlekayutsya v ozhidaemom formate.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) dazhe bez spaCy rabotaet fallback.
- Skrytyy #2: (Inzheneriya ↔ Podderzhka) test bez zavisimostey.

Zemnoy abzats:
Eto proverka, chto shtempelevschik ne spit: vidit imena/mesta i zanosit ikh v zhurnal.

# c=a+b
"""
from __future__ import annotations

import os
import unittest

from modules.nlp import ner_linker as nl
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class TestNERLinker(unittest.TestCase):

    def test_extract(self):
        text = "Alan Turing worked at Bletchley Park in 1943"
        ents = nl.extract_entities(text)
        self.assertIsInstance(ents, list)
        self.assertGreater(len(ents), 0)

    def test_upsert(self):
        ents = [{"type":"PERSON","value":"Alan Turing"}]
        rep = nl.upsert_entities(ents)
        self.assertIn("ok", rep)

if __name__ == "__main__":
    unittest.main(verbosity=2)
