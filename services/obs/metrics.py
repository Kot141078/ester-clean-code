# -*- coding: utf-8 -*-
"""R7/services/obs/metrics.py - minimalnaya nablyudaemost (jsonl-metriki, taymery, snapshoty).

Mosty:
- Yavnyy: Enderton (logika) - metrika kak predikat nad (name, ts, value, labels), proveryaemyy i serializuemyy.
- Skrytyy #1: Ashbi (kibernetika) — A/B-slot: R7_MODE=A (schetchiki/taymery), B (plyus mini-histogrammy), pri oshibkakh → katbek.
- Skrytyy #2: Cover & Thomas (infoteoriya) — jsonl daet lineynyy “signal” nablyudeniy s minimalnoy entropiey formata.

Zemnoy abzats (inzheneriya):
No matter what. Pishet v `PERSIST_DIR/obs/metrics.jsonl` i sozdaet legkie snapshots (`latest.json`).
Use as biblioteku: `with timer("step", labels={"iter":"R5"}): ...` i `inc("ok")`.

# c=a+b"""
from __future__ import annotations
import json, os, time, threading
from contextlib import contextmanager
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_LOCK = threading.Lock()

def _paths():
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    obs = os.path.join(base, "obs")
    os.makedirs(obs, exist_ok=True)
    return os.path.join(obs, "metrics.jsonl"), os.path.join(obs, "latest.json")

def _write_jsonl(rec: Dict[str, Any]) -> None:
    jl, snap = _paths()
    with _LOCK:
        with open(jl, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        with open(snap, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)

def inc(name: str, value: float = 1.0, **labels) -> None:
    rec = {
        "ts": time.time(),
        "type": "counter",
        "name": name,
        "value": float(value),
        "labels": labels or {}
    }
    _write_jsonl(rec)

@contextmanager
def timer(name: str, **labels):
    t0 = time.time()
    err = None
    try:
        yield
    except Exception as e:  # doesn’t swallow - just fix it
        err = str(type(e).__name__)
        raise
    finally:
        dt = (time.time() - t0) * 1000.0
        mode = (os.getenv("R7_MODE") or "A").strip().upper()
        rec = {"ts": time.time(), "type": "timer", "name": name, "ms": dt, "labels": labels or {}}
        if err:
            rec["labels"]["error"] = err
        if mode == "B":
            try:
                # micro-histogram: nearest “bins” (log scale)
                import math
                b = int(max(0, math.log10(max(1e-3, dt/1000.0)) * 4))  # chetvertidesyatichnye biny
                rec["bin"] = b
            except Exception:
                pass  # katbek
        _write_jsonl(rec)

def record(name: str, payload: Dict[str, Any]) -> None:
    payload = dict(payload)
    payload.update({"ts": time.time(), "type": "record", "name": name})
    _write_jsonl(payload)

# c=a+b