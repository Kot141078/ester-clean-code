# -*- coding: utf-8 -*-
"""scripts/test_ddg_html.py

Simple hand test HTML-fallback DuckDuckGo.

Zemnoy abzats:
Zapuskaetsya otdelno ot app.py, sam dobavlyaet koren proekta v sys.path i podkhvatyvaet .env,
chtoby rabotat tak zhe, kak osnovnoe prilozhenie."""

from __future__ import annotations

from pathlib import Path
import sys

from dotenv import load_dotenv  # pip install python-dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from modules import web_search as ws  # noqa: E402
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def main() -> None:
    from pprint import pprint

    q = "RTX 5090 novosti 2025"
    res = ws._search_ddg_html(q, topk=3)
    pprint(res)


if __name__ == "__main__":
    main()