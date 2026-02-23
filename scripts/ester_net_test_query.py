# -*- coding: utf-8 -*-
"""
scripts/ester_net_test_query.py

Test starogo net-mosta (modules/net_bridge.py) v otryve ot Flask.

Zemnoy abzats:
Skript imitiruet to, chto delaet Ester pri obychnom setevom poiske, no bez HTTP.
Polezen, chtoby ponyat: problema v marshrutakh/Flask ili v samom net-dvigatele.
"""

from __future__ import annotations

from pathlib import Path
import sys

from dotenv import load_dotenv  # pip install python-dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from modules import net_bridge  # noqa: E402
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def main() -> None:
    from pprint import pprint

    q = "RTX 5090 novosti 2025"
    res = net_bridge.search(q, max_items=3)
    pprint(res)


if __name__ == "__main__":
    main()