# -*- coding: utf-8 -*-
"""tools/run_experience_context_preview.py - prosmotr konteksta opyta.

MOSTY:
- Yavnyy: (CLI ↔ experience_context_adapter) — pokazyvaem tot zhe kontekst, chto uvidit kaskad.
- Skrytyy #1: (sys.path ↔ struktura repo) - akkuratno addavlyaem koren proekta.
- Skrytyy #2: (operator ↔ layer opyta) — daem prostoy kontrol kachestva nakoplennogo opyta.

ZEMNOY ABZATs:
Inzhenerno: standard bootstrap sys.path + vyzov adaptera. Nikakikh syurprizov:
esli opyt nedostupen - skript chestno pechataet, what kontekst pust.
# c=a+b"""
from __future__ import annotations

import os
import sys

# Add the project root (the folder where modules/ are located)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.thinking import experience_context_adapter as adapter  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def main(argv: list[str]) -> int:
    ctx = adapter.get_experience_context()
    print(ctx or "[experience context is empty]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))