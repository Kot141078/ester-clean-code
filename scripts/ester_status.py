# -*- coding: utf-8 -*-
"""
scripts/ester_status.py — CLI dlya statusa rezhimov Ester.

Mosty:
- Yavnyy: (CLI ↔ modules.ester.status) — bystryy vyvod rezhimov.
- Skrytyy #1: (DevOps ↔ Myslitelnye rezhimy) — udobno v avtomaticheskikh proverkakh.
- Skrytyy #2: (Dokumentatsiya ↔ Kod) — pokazyvaet realnoe sostoyanie flagov.

Zemnoy abzats:
python -m scripts.ester_status — i vidno, vklyuchena li volya, kaskad, treys i debug.
# c=a+b
"""
from __future__ import annotations

import sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.ester.status import get_status, get_human_summary
except Exception as e:  # pragma: no cover
    sys.stderr.write(f"[ester_status] import error: {e}\n")
    raise SystemExit(1)


def main() -> int:
    st = get_status()
    summary = get_human_summary()
    sys.stdout.write("[Ester status]\n")
    for section, vals in st.items():
        sys.stdout.write(f"{section}: {vals}\n")
    sys.stdout.write(f"summary: {summary}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())