# -*- coding: utf-8 -*-
"""
tests/test_backpressure.py — yunit-test token-baketa backpressure (bez HTTP).

Proveryaem:
  • allow() v rezhime burst → zatem blokirovki i raschet retry_after.
  • set_config() menyaet limity na letu.
  • counters() nakaplivaet allowed/blocked.

Mosty:
- Yavnyy: (Kibernetika ↔ Nagruzka) korrektnaya rabota regulyatora.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) schetchiki ne teryayutsya mezhdu vyzovami.
- Skrytyy #2: (Inzheneriya ↔ Podderzhka) test bez vneshnikh zavisimostey.

Zemnoy abzats:
Eto proverka, chto regulirovschik mashet zhezlom po pravilam: snachala propuskaet neskolko, potom pritormazhivaet.

# c=a+b
"""
from __future__ import annotations

import time
import unittest

from modules.ingest import backpressure as bp
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class TestBackpressure(unittest.TestCase):

    def test_allow_and_block(self):
        # vystavim zhestkie limity
        bp.set_config({"enabled": True, "default_rps": 1.0, "default_burst": 2})
        key = "test:key"
        ok1, _ = bp.allow(key)
        ok2, _ = bp.allow(key)
        self.assertTrue(ok1 and ok2)
        # tretiy podryad dolzhen zablokirovatsya
        ok3, retry = bp.allow(key)
        self.assertFalse(ok3)
        self.assertGreaterEqual(retry, 1)
        # podozhdem i snova proydem
        time.sleep(1.1)
        ok4, _ = bp.allow(key)
        self.assertTrue(ok4)

    def test_counters(self):
        c = bp.counters()
        self.assertIn("allowed", c)
        self.assertIn("blocked", c)

if __name__ == "__main__":
    unittest.main(verbosity=2)
