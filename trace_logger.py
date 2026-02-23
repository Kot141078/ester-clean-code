# -*- coding: utf-8 -*-
from __future__ import annotations

"""trace_logger.py — tonkiy wrapper dlya TraceLogger.

Zachem:
- U tebya est DVA fayla: kornevoy trace_logger.py i vstore/trace_logger.py.
- Import mozhet letet to v odin, to v drugoy (kak s journal/actions_discovery).
- Poetomu koren dolzhen byt stabilnym: on pytaetsya vzyat kanonicheskiy TraceLogger iz vstore,
  a esli ne poluchilos — vklyuchaet minimalnyy fallback (best-effort).

FIX konkretnoy oshibki:
- 'expected an indented block after except' — v starom fayle byl pustoy except (kommentariy vmesto pass).

Mosty:
- Yavnyy: edinyy import TraceLogger → vse moduli pishut v odin format.
- Skrytye:
  1) Inzheneriya ↔ nadezhnost: wrapper ustranyaet “paket pobedil modul” i khaos dubley.
  2) Infoteoriya ↔ kontrol: edinyy trace-format oblegchaet agregirovanie/poisk.

ZEMNOY ABZATs: v kontse fayla.
"""


import json
import os
import time
from typing import Any, Dict, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# ---- Prefer canonical implementation ----
try:
    # esli vstore — paket
    from vstore.trace_logger import TraceLogger as TraceLogger  # type: ignore
except Exception:
    try:
        # esli lezhit ryadom kak fayl trace_logger.py vnutri vstore (sys.path uzhe vklyuchaet koren)
        from trace_logger_vstore import TraceLogger as TraceLogger  # type: ignore
    except Exception:
        # ---- Minimal fallback ----
        class TraceLogger:  # type: ignore
            def __init__(self, path: Optional[str] = None) -> None:
                persist = os.path.join(os.getcwd(), "data")
                default_dir = os.path.join(persist, "events")
                os.makedirs(default_dir, exist_ok=True)
                self.path = path or os.path.join(default_dir, "trace.jsonl")
                os.makedirs(os.path.dirname(self.path), exist_ok=True)

            def log(self, obj: Optional[Dict[str, Any]] = None, **kwargs: Any) -> str:
                row = dict(obj or {})
                row.update(kwargs or {})
                row.setdefault("ts", float(time.time()))
                eid = row.get("event_id") or f"E{int(time.time()*1000)}"
                row["event_id"] = eid
                try:
                    with open(self.path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(row, ensure_ascii=False) + "\n")
                except Exception:
                    pass
                return str(eid)


__all__ = ["TraceLogger"]


ZEMNOY = """
ZEMNOY ABZATs (anatomiya/inzheneriya):
Wrapper — kak perekhodnik mezhdu rozetkami raznykh stran. On ne delaet tok “umnee”, on delaet tak,
chtoby pribor (ves proekt) rabotal stabilno i ne sgoral iz-za nesovpadeniya vilki (dubley moduley).
"""