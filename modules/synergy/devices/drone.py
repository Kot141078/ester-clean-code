# -*- coding: utf-8 -*-
"""modules/synergy/devices/drone.py - adaptery drones.

MOSTY:
- (Yavnyy) Podderzhka acme_uav/neo + generic drone.
- (Skrytyy #1) Tonkaya normalizatsiya edinits (sek→ms, kg→g, sek→min) s bezopasnymi granitsami.
- (Skrytyy #2) Profile pozvolyaet prikinut defolty (dalnost/peyload), esli payload partialhno pust.

ZEMNOY ABZATs:
Raznye proshivki → edinyy vmenyaemyy format dlya orkestratora: zaderzhka, ostavsheesya vremya, gruzopodemnost.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict

from modules.synergy.devices.base import DeviceAdapter
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class DroneAdapter(DeviceAdapter):
    """Generic drone fallback."""

    def can_handle(self, vendor: str, profile: Dict[str, Any]) -> bool:
        typ = (profile or {}).get("device", "").lower()
        return "drone" in typ or vendor in ("drone", "generic_drone", "")

    def to_canonical(self, vendor: str, payload: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, float]:
        out = {
            "latency_ms": float(payload.get("latency_ms", 120) or 120),
            "flight_time_min": float(payload.get("flight_time_min", 15) or 15),
            "payload_g": float(payload.get("payload_g", 100) or 100),
        }
        return self._cap(out)


class AcmeUavAdapter(DeviceAdapter):
    """ACME UAV: {"latency": 0.045, "flight": {"remain_s": 1200}, "payload_kg": 0.2}"""

    def can_handle(self, vendor: str, profile: Dict[str, Any]) -> bool:
        v = (vendor or "").lower()
        return v in ("acme_uav", "acme-drone", "acme")

    def to_canonical(self, vendor: str, payload: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, float]:
        lat_s = float(payload.get("latency", 0.1) or 0.1)
        remain_s = float((payload.get("flight") or {}).get("remain_s", 0) or 0)
        kg = float(payload.get("payload_kg", 0.0) or 0.0)
        out = {
            "latency_ms": lat_s * 1000.0,
            "flight_time_min": remain_s / 60.0,
            "payload_g": kg * 1000.0,
        }
        return self._cap(out)


class NeoDroneAdapter(DeviceAdapter):
    """NEO Drone: {"t_ms":80,"battery_min":22,"max_payload_g":350}"""

    def can_handle(self, vendor: str, profile: Dict[str, Any]) -> bool:
        v = (vendor or "").lower()
        return v in ("neo", "neo_robotix", "neo-robotix")

    def to_canonical(self, vendor: str, payload: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, float]:
        out = {
            "latency_ms": float(payload.get("t_ms", 120) or 120),
            "flight_time_min": float(payload.get("battery_min", 0) or 0),
            "payload_g": float(payload.get("max_payload_g", 0) or 0),
        }
        return self._cap(out)