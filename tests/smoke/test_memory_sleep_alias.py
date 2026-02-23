# -*- coding: utf-8 -*-
"""
tests/smoke/test_memory_sleep_alias.py

SMOKE-test dlya sloya "son Ester" (modules.memory.sleep_alias).

Tsel:
- Garantirovat, chto modul modules.memory.sleep_alias importiruetsya
  v realnoy strukture proekta Ester.
- Proverit nalichie klyuchevykh funktsiy i bazovyy contract vozvrata.

Mosty:
- Yavnyy: (Testy ↔ sleep_alias) — bystraya proverka fasada sna.
- Skrytyy #1: (CI ↔ Struktura repo) — bootstrap sys.path, kak v ostalnykh testakh.
- Skrytyy #2: (Inzheneriya ↔ Memory) — esli etot test zelenyy, sloy sna integrirovan korrektno.

Zemnoy abzats:
Eto prostoy inzhenernyy multimetr: votknuli schupy — esli import proshel i funktsii na meste,
znachit novaya obvyazka sna ne lomaet vsyu sistemu.
"""
from __future__ import annotations

import sys
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Bootstrap: dobavlyaem koren proekta (ester-project) v sys.path.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_sleep_alias_import_and_api():
    import modules.memory.sleep_alias as s  # type: ignore

    assert hasattr(s, "status")
    assert hasattr(s, "run_cycle")
    assert hasattr(s, "switch_slot")

    st = s.status()
    assert isinstance(st, dict)
    assert "slot" in st
    assert "impl" in st

    rc = s.run_cycle()
    assert isinstance(rc, dict)
    assert "ok" in rc
    assert "slot" in rc