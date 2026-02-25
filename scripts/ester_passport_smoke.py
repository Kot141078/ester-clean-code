"""scripts/ester_passport_smoke.py

Simple smoke-test dlya modulya modules.mem.passport:

1. Guarantee, chto koren proekta (D:\ester-project) est v sys.path.
2. Pechataem, where lezhit ester_identity.md.
3. Pechataem korotkuyu sistemnuyu vyzhimku profilea.
4. Delaem odnu probnuyu zapis cherez upsert_with_passport(..).
5. Vyvodim poslednie 3 zapisi iz zhurnala.

Zapusk iz kornya project:

    cd D:\ester-project
    python scripts\ester_passport_smoke.py"""

from __future__ import annotations

# === 0. Bootstrap paths: add the project root to sys.path ===============

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# === 1. Osnovnoy import ====================================================

from pprint import pprint

from modules.mem import passport as mem_passport  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def main() -> None:
    print("=== Ester passport smoke test ===")
    print(f"PASSPORT_MD_PATH: {mem_passport.PASSPORT_MD_PATH}")
    print()

    print("=== System prompt excerpt ===")
    prompt = mem_passport.get_identity_system_prompt(max_chars=600)
    print(prompt)
    print()

    print("=== Upsert test entry ===")
    res_upsert = mem_passport.upsert_with_passport(
        mm=None,
        text="Test record to check the profile's ester_identity.",
        meta={"owner": "ester", "kind": "smoke_test"},
        source="scripts/ester_passport_smoke.py",
        version=1,
    )
    pprint(res_upsert)
    print()

    print("=== Recent entries ===")
    res_list = mem_passport.list_recent(mm=None, limit=3)
    pprint(res_list)


if __name__ == "__main__":
    main()