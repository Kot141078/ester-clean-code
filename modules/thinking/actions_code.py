# -*- coding: utf-8 -*-
"""
modules/thinking/actions_code.py — eksheny «voli» vokrug izmeneniy koda.

Mosty:
- Yavnyy: (Mysli ↔ Kod) mozg mozhet sformirovat dry-run i podgotovit guarded_apply.
- Skrytyy #1: (Ostorozhnost ↔ HTTP) samo primenenie — tolko cherez zaschischennuyu ruchku.
- Skrytyy #2: (LLM ↔ Podskazki) optsionalno prosim LLM szhat plan izmeneniy.

Zemnoy abzats:
Inzhenernyy assistent vnutri Ester: «posmotri, chto pomenyaem» i «gotovo k primeneniyu, zhdu klyuch».

# c=a+b
"""
from __future__ import annotations
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def a_dry(args: Dict[str,Any]):
        from modules.self.forge import dry_run
        return dry_run(list(args.get("changes") or []))
    register("self.guard.dry", {"changes":"list"}, {"ok":"bool","plan":"list"}, 8, a_dry)

    def a_apply(args: Dict[str,Any]):
        # Primenenie dolzhno idti cherez HTTP s «pilyuley», vozvraschaem podskazku
        return {"ok": True, "hint":"use /self/codegen/guarded_apply with ?pill=...", "changes": args.get("changes"), "tests": args.get("tests"), "note": args.get("note","")}
    register("self.guard.apply", {"changes":"list","tests":"list","note":"str"}, {"ok":"bool"}, 3, a_apply)

_reg()
# c=a+b