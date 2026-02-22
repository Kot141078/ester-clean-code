# -*- coding: utf-8 -*-
"""
modules/synergy/devices/ugv.py — adapter nazemnykh platform (UGV).

MOSTY:
- (Yavnyy) Konvertiruet t_ms/batt_min/cargo_kg → latentnost/vremya/peyload.
- (Skrytyy #1) Approksimatsiya flight_time_min kak "runtime_min" (dlya unifikatsii s dronom).
- (Skrytyy #2) Fallback na adekvatnye defolty, esli polya chastichno otsutstvuyut.

ZEMNOY ABZATs:
UGV ne «letaet», no orkestratoru udobnee imet odno pole vremeni avtonomnosti — runtime = flight_time_min.

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict

from modules.synergy.devices.base import DeviceAdapter
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class UgvAdapter(DeviceAdapter):
    def can_handle(self, vendor: str, profile: Dict[str, Any]) -> bool:
        typ = (profile or {}).get("device", "").lower()
        v = (vendor or "").lower()
        return "ugv" in typ or v in ("ugv_mk1", "ugv", "ground_robot")

    def to_canonical(self, vendor: str, payload: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, float]:
        lat = float(payload.get("t_ms", payload.get("latency_ms", 150)) or 150)
        runtime_min = float(payload.get("runtime_min", payload.get("batt_min", 30)) or 30)
        cargo_kg = float(payload.get("cargo_kg", payload.get("payload_kg", 0.0)) or 0.0)
        out = {
            "latency_ms": lat,
            "flight_time_min": runtime_min,  # unifitsirovannoe pole
            "payload_g": cargo_kg * 1000.0,
        }
        return self._cap(out)