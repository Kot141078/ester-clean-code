# -*- coding: utf-8 -*-
"""modules/synergy/devices/robot_arm.py - adapter manipulyatorov.

MOSTY:
- (Yavnyy) Translate latency/hold_weight_g → kanon; flight_time_min=0 po umolchaniyu.
- (Skrytyy #1) Uchityvaet safe-payload iz profilya pri otsutstvii v pakete.
- (Skrytyy #2) Granitsy bezopasnosti.

ZEMNOY ABZATs:
Manipulyator ne avtonomen po vremeni, no ego “peyload” vazhen dlya naznacheniya zadach podem/manipulyatsii.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict

from modules.synergy.devices.base import DeviceAdapter
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class RobotArmAdapter(DeviceAdapter):
    def can_handle(self, vendor: str, profile: Dict[str, Any]) -> bool:
        typ = (profile or {}).get("device", "").lower()
        v = (vendor or "").lower()
        return "arm" in typ or v in ("robarm", "robot_arm")

    def to_canonical(self, vendor: str, payload: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, float]:
        lat = float(payload.get("latency_ms", payload.get("latency", 120)) or 120)
        pg = float(payload.get("hold_weight_g", payload.get("payload_g", profile.get("payload_g", 0))) or 0)
        out = {
            "latency_ms": lat,
            "flight_time_min": 0.0,
            "payload_g": pg,
        }
        return self._cap(out)