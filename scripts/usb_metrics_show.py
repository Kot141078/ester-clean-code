# -*- coding: utf-8 -*-
"""scripts/usb_metrics_show.py - vyvod tekuschikh metrik agenta USB (JSON).

Mosty:
- Yavnyy (Nablyudenie ↔ Ekspluatatsiya): momentalnyy snimok sostoyaniya.
- Skrytyy 1 (Infoteoriya ↔ UI): minimalno neobkhodimaya svodka v JSON.
- Skrytyy 2 (Inzheneriya ↔ Nadezhnost): prigodno dlya health-chekov i alertov.

Zemnoy abzats:
Otkladka “v pole”: bystro ponyat, kak often srabatyvaem i kakaya p95 zaderzhka.

# c=a+b"""
from __future__ import annotations

import json
from metrics.usb_agent_stats import USBStats  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main() -> int:
    s = USBStats()
    print(json.dumps(s.snapshot(), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())