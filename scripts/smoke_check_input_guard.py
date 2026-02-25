# -*- coding: utf-8 -*-
"""scripts/smoke_check_input_guard.py

Smoke-test dlya modules.core.input_guard.

Name:
- Garantirovat, what input_guard viden kak paket iz lyuboy rabochey direktorii.
- Check:
  * korrektnoe chtenie ESTER_CHAT_MAX_INPUT_CHARS,
  * otsutstvie iskazheniy korotkogo vvoda,
  * obrezku slishkom dlinnogo vvoda do limita,
  * bezopasnuyu obrabotku pustykh znacheniy.

Zapusk (iz kornya proekta):
    python scripts/smoke_check_input_guard.py"""

from __future__ import annotations

import os
import sys
import random
import string
from pathlib import Path

# --- We connect the root of the project so that import modules.* works when launched from script/ ---

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- Importiruem limiter ---

from modules.core import input_guard  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _make_text(n: int) -> str:
    return "".join(random.choice(string.ascii_letters) for _ in range(n))


def main() -> None:
    # For the test, it strictly sets the limit (as in combat .env).
    os.environ["ESTER_CHAT_MAX_INPUT_CHARS"] = "16000"

    limit = input_guard.get_effective_limit()
    assert limit == 16000, f"Expected limit 16000, got {limit}"
    print(f"[OK] Effective limit = {limit}")

    # 1) Short input - should not be cut
    short = _make_text(100)
    out_short, info_short = input_guard.normalize_input(short)
    assert out_short == short, "Short input must stay untouched."
    assert not info_short.trimmed, "Short input must not be marked as trimmed."
    print("[OK] Short input preserved.")

    # 2) Long input - must be trimmed to the limit
    long = _make_text(limit + 500)
    out_long, info_long = input_guard.normalize_input(long)
    assert len(out_long) == limit, f"Long input must be trimmed to {limit} chars."
    assert info_long.trimmed, "Long input must be marked as trimmed."
    print("[OK] Long input trimmed correctly.")

    # 3) Empty values ​​- safe processing
    empty, info_empty = input_guard.normalize_input(None)
    assert empty == "", "None must become empty string."
    assert not info_empty.trimmed, "Empty is not 'trimmed'."
    print("[OK] Empty/None handled safely.")

    print("[SMOKE] input_guard is consistent with configuration.")


if __name__ == "__main__":
    main()