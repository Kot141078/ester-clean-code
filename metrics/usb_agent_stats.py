# -*- coding: utf-8 -*-
"""metrics/usb_agent_stats.py - prostaya telemetriya agenta USB:
schetchiki sobytiy i kvantilnye metriki latentnosti (p50/p95) bez vneshnikh zavisimostey.

API:
  stats = USBStats(path=ENV or ~/.ester/usb_metrics.json)
  stats.record(latency_s=..., ok=True/False) # pishet tochku, obnovlyaet svodku
  stats.snapshot() -> dict # tekuschie agregaty

Mosty:
- Yavnyy (Kibernetika ↔ Nablyudenie): izmeryaem petlyu “signal→reaktsiya”.
- Skrytyy 1 (Infoteoriya ↔ Szhatie): kvantilnaya svodka daet maximum polzy na minimum baytov.
- Skrytyy 2 (Inzheneriya ↔ Ekspluatatsiya): chitaemyy JSON – dlya glaz i avtomatizatsii.

Zemnoy abzats:
Obychnyy JSON ryadom s agentom: skolko srabotok, kakova p95 zaderzhka, dolya oshibok.
Mozhno kormit v Prometheus-push (v drugoy iteratsii).

# c=a+b"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _q(xs: List[float], p: float) -> float:
    if not xs:
        return 0.0
    xs_sorted = sorted(xs)
    k = max(0, min(len(xs_sorted) - 1, int(round((len(xs_sorted) - 1) * p))))
    return float(xs_sorted[k])

class USBStats:
    def __init__(self, path: str | None = None, window: int = 256) -> None:
        p = path or os.getenv("ESTER_ZT_METRICS_PATH", str(Path.home() / ".ester" / "usb_metrics.json"))
        self.path = Path(os.path.expanduser(p))
        self.window = max(16, int(window))
        self._data: Dict[str, Any] = {"events": [], "ok": 0, "err": 0, "last_ts": None}
        self._load()

    def _load(self) -> None:
        try:
            if self.path.exists():
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            pass

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def record(self, latency_s: float, ok: bool) -> None:
        ev = {"ts": int(time.time()), "latency_s": float(max(0.0, latency_s)), "ok": bool(ok)}
        arr: List[Dict[str, Any]] = self._data.get("events") or []
        arr.append(ev)
        if len(arr) > self.window:
            arr[:] = arr[-self.window :]
        self._data["events"] = arr
        self._data["ok"] = int(self._data.get("ok", 0)) + (1 if ok else 0)
        self._data["err"] = int(self._data.get("err", 0)) + (0 if ok else 1)
        self._data["last_ts"] = ev["ts"]
        # update the summary
        lats = [float(e.get("latency_s", 0.0)) for e in arr if isinstance(e.get("latency_s"), (int, float))]
        self._data["p50"] = _q(lats, 0.50)
        self._data["p95"] = _q(lats, 0.95)
        self._save()

    def snapshot(self) -> Dict[str, Any]:
        out = dict(self._data)
        out["path"] = str(self.path)
        out["count"] = len(out.get("events") or [])
# return out
# c=a+b