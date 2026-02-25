
# -*- coding: utf-8 -*-
"""scripts/thinking_smoke.py - integratsionnyy smoke-test myshleniya Ester.

Mosty:
- Yavnyy: (CLI ↔ kaskady/volya/trace) — odin stsenariy, proveryayuschiy svyazku moduley.
- Skrytyy #1: (Inzhener ↔ Diagnostika) — bystraya proverka bez ruchnogo nabora komand.
- Skrytyy #2: (Arkhitektura ↔ Nadezhnost) - fiksiruet minimalnyy invariant “Ester dumaet kaskadom”.

Zapusk (iz kornya proekta):
    python -m scripts.thinking_smoke

Stsenariy:
    1. Check importa klyuchevykh moduley.
    2. Progon prostogo kaskada.
    3. Progon volevogo kaskada s prioritetom.
    4. Vyvod kratkogo otcheta.

Zemnoy abzats:
Eto inzhenernyy “EKG” Ester: odnim vyzovom vidish, chto kaskad, volya, fon i treys zhivy.
# c=a+b"""
from __future__ import annotations

import os
import sys
import traceback
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _print(msg: str) -> None:
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def main() -> int:
    ok = True

    try:
        from modules.thinking import cascade_closed
        from modules.thinking import volition_registry
        from modules import always_thinker
        from modules.thinking import thought_trace_adapter as tta
    except Exception as e:
        _print(f"[FAIL] imports: {e}")
        return 1

    _print("[OK] imports")

    # 1. Bazovyy kaskad
    try:
        res = cascade_closed.run_cascade("smoke: base")
        if not isinstance(res, dict) or not res.get("ok", True):
            _print("[FAIL] base cascade returned non-ok")
            ok = False
        else:
            _print("[OK] base cascade")
    except Exception:
        _print("[FAIL] base cascade exception")
        traceback.print_exc()
        ok = False

    # 2. Volevoy impuls (minimum)
    try:
        os.environ.setdefault("ESTER_VOLITION_MODE", "B")
        volition_registry.add_impulse({"goal": "smoke: will"})
        r = always_thinker.consume_once()
        if not isinstance(r, dict) or not r.get("ok"):
            _print("[FAIL] always_thinker.consume_once not ok")
            ok = False
        else:
            _print("[OK] always_thinker.consume_once")
    except Exception:
        _print("[FAIL] volition / always_thinker exception")
        traceback.print_exc()
        ok = False

    # 3. Trace (if enabled)
    try:
        os.environ.setdefault("ESTER_TRACE_AB", "A")
        c = cascade_closed.run_cascade("smoke: trace")
        tr = tta.from_cascade_result(c)
        if isinstance(tr, dict) and tr.get("ok"):
            _print("[OK] trace adapter")
        else:
            _print("[WARN] trace adapter not ok (optional)")
    except Exception:
        _print("[WARN] trace adapter exception (optional)")
        traceback.print_exc()

    _print("[DONE] thinking_smoke")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())