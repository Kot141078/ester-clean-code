# -*- coding: utf-8 -*-
"""tools/backup_state.py - bezopasnyy bekap kataloga sostoyaniya v tar.gz.

Mosty:
- Yavnyy: (QA ↔ Bezopasnost) - ruchnoy, yavnyy bekap bez skrytogo zapuska.
- Skrytyy 1: (Diagnostika ↔ Vosstanovlenie) - arkhiv prigoden dlya vosstanovleniya sostoyaniya posle sboev.
- Skrytyy 2: (Infrastruktura ↔ Portativnost) - tar.gz legko perenosit mezhdu uzlami P2P.

Zemnoy abzats:
Po komande upakovyvaem `ESTER_STATE_DIR` v arkhiv. Nikakikh demonov i kronov - tolko ruchnoy zapusk."""
from __future__ import annotations
import os, tarfile, time
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main():
    state = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))).expanduser()
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = Path.cwd() / f"ester_state_{ts}.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        tar.add(state, arcname="ester_state")
    print("backup created:", out)

if __name__ == "__main__":
    main()

# finalnaya stroka
# c=a+b