# -*- coding: utf-8 -*-
"""modules/synergy/devices/simulator.py - adapter simulyatora/ekho.

MOSTY:
- (Yavnyy) Prinimaet lyubye polya, akkuratno kapiruet v kanon.
- (Skrytyy #1) Udoben dlya testov/demo — rabotaet vsegda.
- (Skrytyy #2) Nikakoy logiki vendora, tolko bezopasnye defolty.

ZEMNOY ABZATs:
Kogda "zheleza" net pod rukoy - simulyator pozvolyaet obkatat ves konveyer.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict

from modules.synergy.devices.base import DeviceAdapter
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class SimulatorAdapter(DeviceAdapter):
    def can_handle(self, vendor: str, profile: Dict[str, Any]) -> bool:
        return True

    def to_canonical(self, vendor: str, payload: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, float]:
        out = {
            "latency_ms": float(payload.get("latency_ms", 120) or 120),
            "flight_time_min": float(payload.get("flight_time_min", 10) or 10),
            "payload_g": float(payload.get("payload_g", 0) or 0),
        }
        return self._cap(out)