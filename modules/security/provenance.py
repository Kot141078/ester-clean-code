# -*- coding: utf-8 -*-
"""modules.security.provenance - fiksatsiya i proverka proiskhozhdeniya sobytiy + reestry + shina sobytiy.

MOSTY:
- Yavnyy: (routes.* ↔ Security) record_event(), verify_event(), _load_registries(), forward_to_bus().
- Skrytyy #1: (Zhurnaly ↔ Audit) faylovye logi i json-reestry.
- Skrytyy #2: (Klyuchi ↔ Bezopasnost) HMAC cherez ENV.

ZEMNOY ABZATs:
Prostaya “chernaya korobka”: zapisyvaet sobytie, umeet ego proverit i protolknut v lokalnuyu shinu (ndjson).

Anti-ekho / bezopasnaya samo-redaktura:
- A/B-slot ne nuzhen: operatsii lokalnye.

# c=a+b"""
from __future__ import annotations
import os, json, time, hmac, hashlib
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_BASE = os.path.join("data", "provenance")
os.makedirs(_BASE, exist_ok=True)
_LOG = os.path.join(_BASE, "events.log")
_REG = os.path.join(_BASE, "registries.json")
_BUS = os.path.join(_BASE, "bus.ndjson")
_KEY = (os.getenv("ESTER_HMAC_KEY") or "ester-dev-key").encode("utf-8")

def _sign(blob: bytes) -> str:
    return hmac.new(_KEY, blob, hashlib.sha256).hexdigest()

def record_event(kind: str, data: Dict[str, Any]) -> Dict[str, Any]:
    ts = int(time.time())
    payload = {"kind": kind, "ts": ts, "data": data}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sig = _sign(raw)
    with open(_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"sig": sig, "payload": payload}, ensure_ascii=False) + "\n")
    return {"ok": True, "sig": sig, "ts": ts}

def verify_event(payload: Dict[str, Any], sig: str) -> Dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ok = hmac.compare_digest(_sign(raw), str(sig))
    return {"ok": ok}

def _load_registries() -> Dict[str, Any]:
    """Returns the registry structure (if there is no file, empty)."""
    if not os.path.isfile(_REG):
        return {}
    try:
        with open(_REG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def forward_to_bus(event: Dict[str, Any]) -> Dict[str, Any]:
    """Sending an event to the local “bus” (njson), without a network.
    Contract: forward_to_bus(ZZF0Z) -> ZZF1ZZ"""
    ts = int(time.time())
    rec = {"ts": ts, "event": event}
    with open(_BUS, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    # Parallelno fiksiruem v audit
    record_event("bus", event)
    return {"ok": True, "ts": ts, "path": _BUS}

# c=a+b