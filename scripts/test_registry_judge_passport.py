"""
scripts/

Proverka svyazki:
    modules.providers.registry + profile Ester.

Chto delaet:
1. Dobavlyaet koren proekta (D:\ester-project) v sys.path.
2. Importiruet registry i (po vozmozhnosti) passport.
3. Pokazyvaet, kakoy provayder vybran dlya mode="judge".
4. Pokazyvaet tekuschiy sistemnyy prompt identichnosti (sokraschennyy).
5. Dergaet registry.answer(..., mode="judge") i pechataet otvet.

Zapusk:

    cd D:\ester-project
    python scripts\test_registry_judge_passport.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint

# === 0. Butstrap putey: koren proekta v sys.path =========================

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# === 1. Importy ============================================================

from modules.providers import registry  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.mem import passport as mem_passport  # type: ignore
except Exception:
    mem_passport = None  # type: ignore


def main() -> None:
    print("=== Provider selection for mode='judge' ===")
    try:
        p = registry.select_provider(mode="judge")
        print("provider name:", p.get("name"))
    except Exception as e:
        print("ERROR: select_provider(mode='judge') failed:", repr(e))
        return

    if mem_passport is not None:
        print("\n=== Identity system prompt (excerpt) ===")
        try:
            prompt = mem_passport.get_identity_system_prompt(max_chars=600)
            print(prompt)
        except Exception as e:
            print("ERROR: mem_passport.get_identity_system_prompt failed:", repr(e))
    else:
        print("\n(mem_passport module is not available)")

    print("\n=== Calling registry.answer(mode='judge') ===")
    msgs = [
        {"role": "user", "content": "Korotko skazhi, kto ty i kak rabotaesh."}
    ]

    try:
        res = registry.answer(msgs, mode="judge")
        pprint(res)
    except Exception as e:
        print("ERROR: registry.answer failed:", repr(e))


if __name__ == "__main__":
    main()