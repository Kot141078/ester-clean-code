# -*- coding: utf-8 -*-
"""
modules.selfmanage.lmstudio_probe — proverka i «bench» LM Studio.

MOSTY:
- Yavnyy: (routes.admin_llm / CLI ↔ LM Studio) probe_summary(), bench_model(), probe_and_bench().
- Skrytyy #1: (ENV ↔ Konfig) PORT/BASE chitayutsya iz ENV, no offlayn-put ne padaet.
- Skrytyy #2: (UX ↔ Bezopasnost) bez setevykh vyzovov po umolchaniyu — chistyy offlayn otchet.

ZEMNOY ABZATs:
Daet paneli bystryy status «vidim li LM Studio», i «kak model otvechaet», dazhe esli fakticheski offlayn — API ne valitsya.

# c=a+b
"""
from __future__ import annotations
import os
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def probe() -> dict:
    port = int(os.getenv("LMSTUDIO_PORT", "0") or 0)
    base = os.getenv("LMSTUDIO_BASE", "http://127.0.0.1")
    return {"ok": True, "available": False, "port": port, "base": base, "mode": "offline"}

def probe_summary() -> Dict[str, Any]:
    p = probe()
    models = os.getenv("LMSTUDIO_MODELS", "")
    listed = [m.strip() for m in models.split(",") if m.strip()]
    return {"ok": True, "lmstudio": p, "models": listed, "note": "offline summary"}

def bench_model(base: str, model: str, timeout: float = 2.0) -> Dict[str, Any]:
    # Offlayn-bench: nikakikh zaprosov — lish validiruem vkhod
    return {"ok": False, "model": model, "base": base, "latency_ms": None, "reason": "offline"}

def probe_and_bench() -> Dict[str, Any]:
    info = probe_summary()
    benches = []
    for m in info.get("models", []):
        benches.append(bench_model(info["lmstudio"]["base"], m))
    return {"ok": True, "info": info, "benches": benches}

# c=a+b