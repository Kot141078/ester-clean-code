# -*- coding: utf-8 -*-
"""
modules/eval/bench.py — minimalnyy regress-stend: lokalnye proverki bezopasnosti/soglasiya i karantina.

Mosty:
- Yavnyy: (Kachestvo ↔ Bezopasnost) avtomaticheskie «storozhki» na kriticheskie invarianty.
- Skrytyy #1: (Infoteoriya ↔ Audit) otchet so statusami i soobscheniyami.
- Skrytyy #2: (Myshlenie ↔ Kontrol) mozhet zapuskatsya pered approve (preflight).

Zemnoy abzats:
Kak korotkiy chek-list pered vzletom: proverili tormoza — mozhno rulit na polosu.

# c=a+b
"""
from __future__ import annotations
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _ok(name: str, detail: Any=None): return {"name": name, "ok": True, "detail": detail}
def _fail(name: str, detail: Any=None): return {"name": name, "ok": False, "detail": detail}

def test_caution_blocks_expense() -> Dict[str, Any]:
    try:
        from modules.policy.cautious_freedom import evaluate  # type: ignore
        dec = evaluate("/economy/ledger/expense","POST",{"amount":500})
        return _ok("caution_blocks_expense", dec) if not dec.get("allow", True) else _fail("caution_blocks_expense", dec)
    except Exception as e:
        return _fail("caution_blocks_expense", f"error:{e}")

def test_deploy_requires_invite() -> Dict[str, Any]:
    try:
        from modules.self.deployer import approve  # type: ignore
        rep = approve("non-existent-stage", pill=True, invite=None)
        # ozhidanie: otkaz po invite_check_failed
        return _ok("deploy_requires_invite", rep) if not rep.get("ok", False) and "invite" in str(rep) else _fail("deploy_requires_invite", rep)
    except Exception as e:
        return _fail("deploy_requires_invite", f"error:{e}")

def list_tests() -> List[str]:
    return ["caution_blocks_expense","deploy_requires_invite"]

def run(names: List[str] | None = None) -> Dict[str, Any]:
    alltests = {
        "caution_blocks_expense": test_caution_blocks_expense,
        "deploy_requires_invite": test_deploy_requires_invite,
    }
    sels = list(alltests.keys()) if not names else [n for n in names if n in alltests]
    results = []
    for n in sels:
        results.append(alltests[n]())
    ok = all(t.get("ok") for t in results) if results else True
    return {"ok": ok, "results": results, "count": len(results)}
# c=a+b