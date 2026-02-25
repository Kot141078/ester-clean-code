# -*- coding: utf-8 -*-
"""tools/run_memory_daily_cycle.py — ruchnoy zapusk nochnogo tsikla pamyati.

Mosty:
- Yavnyy: (CLI ↔ Memory) — prostoy vyzov ezhednevnoy gigieny cherez terminal/cron.
- Skrytyy #1: (Operatsii ↔ Rezervirovanie) — daet udobnuyu tochku dlya planirovschikov i bekapov.
- Skrytyy #2: (Inzheneriya ↔ Avtonomiya) - operatory zapuskayut odin skript, a vnutri rabotaet tselyy kaskad.

Zemnoy abzats:
Inzhenerno eto “knopka obsluzhivanie mozga”: mozhno povesit na nightly-zadachu or zapuskat rukami,
chtoby Ester akkuratno podvela itogi i ubrala musor."""
from __future__ import annotations

import json
import sys

from modules.memory import daily_cycle
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "manual"
    res = daily_cycle.run_cycle(mode=mode)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if bool(res.get("ok", True)) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))