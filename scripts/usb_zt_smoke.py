# -*- coding: utf-8 -*-
"""
scripts/usb_zt_smoke.py — bezopasnyy smoke dlya Zero-Touch bez pobochek.

Mosty:
- Yavnyy (Enderton ↔ Praktika): proveryaemye shagi → predikaty istinnosti.
- Skrytyy 1 (Ashbi ↔ Ustoychivost): ne pishem na disk — tolko nablyudaem.
- Skrytyy 2 (Cover&Thomas ↔ Signaly): vyvodim kompaktnyy JSON — udobno chitat glazami i parsit.

Zemnoy abzats:
Zapusti — uvidish, kakie fleshki vidny i kak by proshla podgotovka, ne trogaya faylovuyu sistemu.
# c=a+b
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from modules.selfmanage.usb_locator import list_usb_roots  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main() -> int:
    mounts = list_usb_roots() or []
    rep: Dict[str, Any] = {"ok": True, "mounts": mounts}
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b