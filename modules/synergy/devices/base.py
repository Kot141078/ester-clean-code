# -*- coding: utf-8 -*-
"""
modules/synergy/devices/base.py — bazovyy interfeys adapterov.

MOSTY:
- (Yavnyy) Edinyy protokol adapterov: can_handle(...) i to_canonical(...).
- (Skrytyy #1) Reestr plaginov s prioritetom (registratsiya poryadka = prioritet).
- (Skrytyy #2) Besstoronnost: adaptery ne delayut set/IO; tolko chistaya normalizatsiya.

ZEMNOY ABZATs:
Lyuboy novyy vendor podklyuchaetsya odnoy realizatsiey klassa — bez pravok ostalnogo koda.

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class DeviceAdapter:
    """Bazovyy klass adaptera ustroystva/vendora."""

    def can_handle(self, vendor: str, profile: Dict[str, Any]) -> bool:
        want = str(vendor or "").strip().lower()
        if not want:
            return False
        own = str(profile.get("vendor") or profile.get("adapter_vendor") or "").strip().lower()
        if own and own == want:
            return True
        aliases = profile.get("vendor_aliases") or profile.get("aliases") or []
        if isinstance(aliases, list):
            for alias in aliases:
                if str(alias or "").strip().lower() == want:
                    return True
        return False

    def to_canonical(self, vendor: str, payload: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, float]:
        """Vernut {'latency_ms','flight_time_min','payload_g'} s granitsami bezopasnosti."""
        def _pick_float(*candidates: Any, default: float = 0.0) -> float:
            for value in candidates:
                try:
                    if value is None:
                        continue
                    return float(value)
                except Exception:
                    continue
            return float(default)

        out = {
            "latency_ms": _pick_float(
                payload.get("latency_ms"),
                payload.get("latency"),
                payload.get("ping_ms"),
                profile.get("latency_ms"),
                default=120.0,
            ),
            "flight_time_min": _pick_float(
                payload.get("flight_time_min"),
                payload.get("flight_min"),
                payload.get("airtime_min"),
                profile.get("flight_time_min"),
                default=0.0,
            ),
            "payload_g": _pick_float(
                payload.get("payload_g"),
                payload.get("payload"),
                payload.get("payload_grams"),
                payload.get("weight_g"),
                profile.get("payload_g"),
                default=0.0,
            ),
        }
        return self._cap(out)

    @staticmethod
    def _cap(out: Dict[str, float]) -> Dict[str, float]:
        out["latency_ms"] = max(5.0, min(2000.0, float(out.get("latency_ms", 120) or 120)))
        out["flight_time_min"] = max(0.0, min(120.0, float(out.get("flight_time_min", 0) or 0)))
        out["payload_g"] = max(0.0, min(50000.0, float(out.get("payload_g", 0) or 0)))
        return out


class AdapterRegistry:
    def __init__(self):
        self._adapters: List[DeviceAdapter] = []

    def register(self, adapter: DeviceAdapter) -> None:
        self._adapters.append(adapter)

    def find(self, vendor: str, profile: Dict[str, Any]) -> Optional[DeviceAdapter]:
        for ad in self._adapters:
            try:
                if ad.can_handle(vendor, profile):
                    return ad
            except Exception:
                continue
        return None
