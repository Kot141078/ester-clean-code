# -*- coding: utf-8 -*-
"""modules/thinking/actions_codegen.py — eksheny CodeSmith+ dlya “voli”

Mosty:
- Yavnyy: (Mysli ↔ Kodogeneratsiya) daem mozgu pryamye atomy deystviy.
- Skrytyy #1: (Pesochnitsa ↔ Proverka) vozmozhnost testirovat paket izmeneniy.
- Skrytyy #2: (Guard ↔ Nadezhnost) primenenie — cherez bezopasnuyu obertku.

Zemnoy abzats:
Teper lyuboe “ya khochu modul X” prevraschaetsya v spec→generatsiyu→test→akkuratnuyu ustanovku.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def a_gen(args: Dict[str,Any]):
        from modules.self.codegen import generate
        return generate(args or {})
    register("codesmith.generate", {"spec":"dict"}, {"ok":"bool"}, 60, a_gen)

    def a_test(args: Dict[str,Any]):
        from modules.self.codegen import test_files
        return test_files(list(args.get("files") or []), str(args.get("test_code","")))
    register("codesmith.test", {"files":"list","test_code":"str"}, {"ok":"bool"}, 60, a_test)

    def a_apply(args: Dict[str,Any]):
        from modules.self.codegen import guarded_apply
        return guarded_apply(list(args.get("files") or []))
    register("codesmith.apply", {"files":"list"}, {"ok":"bool"}, 90, a_apply)

_reg()
# c=a+b