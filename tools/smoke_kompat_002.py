# -*- coding: utf-8 -*-
"""Smoke dlya KOMPAT-002: zapuskaetsya iz podkataloga tools, sam dobavlyaet koren proekta v sys.path.
MOSTY: (yavnyy) tools↔core importy; (skrytyy 1) sys.path↔struktura proekta; (skrytyy 2) JSON↔chtenie v PS5.
ZEMNOY ABZATs: isklyuchaem vliyanie tekuschego kataloga - proveryaem imenno proektnye importy.
c=a+b"""
from __future__ import annotations
import sys, os, json
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

res = {}

try:
    from messaging.telegram_adapter import TelegramAdapter
    res["telegram"] = bool(getattr(TelegramAdapter, "send", None))
except Exception as e:
    res["telegram"] = f"ERR:{e}"

try:
    from modules.scheduler import WatchConfig
    res["scheduler_inbox_dir"] = WatchConfig().inbox_dir
except Exception as e:
    res["scheduler_inbox_dir"] = f"ERR:{e}"

try:
    from thinking.think_core import THINKER
    res["thinker_ok"] = True
except Exception as e:
    res["thinker_ok"] = f"ERR:{e}"

try:
    from modules.ingest.code_ingest import analyze_code, ingest_code
    res["analyze_ok"] = analyze_code(".")["ok"]
    res["ingest_ok"] = ingest_code(".")["ok"]
except Exception as e:
    res["ingest"] = f"ERR:{e}"

try:
    from security import e2ee
    res["e2ee_ok"] = len(e2ee.encrypt(b"ping")) > 0
except Exception as e:
    res["e2ee_ok"] = f"ERR:{e}"

try:
    from modules.graph.dag_engine import DAGEngine
    res["dag_ok"] = DAGEngine().run({"steps":[{"kind":"echo","msg":"hi"}]})["ok"]
except Exception as e:
    res["dag_ok"] = f"ERR:{e}"

print(json.dumps(res, ensure_ascii=False, indent=2))