# -*- coding: utf-8 -*-
"""Universalnyy smoke-test (Windows/PowerShell sovmestimyy).
Mosty:
- Yavnyy: (Testy ↔ Koren) — dobavlyaem koren proekta v sys.path, esli zapuscheno kak fayl iz tools/.
- Skrytyy #1: (DX ↔ Nadezhnost) — odinakovo rabotaet kak `python -m tools.smoke_inline`, tak i `python tools\smoke_inline.py`.
- Skrytyy #2: (Orkestratsiya ↔ Podsistemy) — proveryaet podsoznanie, DAG i judge odnim rankom.

Zemnoy abzats:
Kogda skript ispolnyayut kak fayl, Python stavit sys.path[0] = <...>\tools. Iz‑za etogo `modules/` ne visible.
My nakhodim koren (roditel tools) i garantiruem ego v sys.path pered importami.
# c=a+b"""
from __future__ import annotations
import sys, pathlib

# --- A/B-safe bootstrap of project root ---
_THIS = pathlib.Path(__file__).resolve()
_ROOT = _THIS.parent.parent  # predpolagaemyy koren: <project>/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# --- Tests ---
from modules.subconscious import engine as se
print("subconscious.tick:", se.tick_once("smoke"))

from modules.graph import dag_engine as dg
g = dg.build_graph({"A": {"fn": lambda **k: "ok", "deps": []}})
print("graph.run:", g.run())

from modules.judge import select_best, synthesize
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
print("judge.select_best:", select_best(["a","bbb","cc"]))
print("judge.synthesize:", synthesize(["a","bbb","cc"]))