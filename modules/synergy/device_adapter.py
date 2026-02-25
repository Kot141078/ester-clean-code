# -*- coding: utf-8 -*-
"""modules/synergy/device_adapter.py - fasad sloya adapterov telemetrii.

MOSTY:
- (Yavnyy) Register plaginov i konveyer: vendor-payload -> canonical -> TelemetryEvent (Pydantic).
- (Skrytyy #1) A/B-slot s avtokatbekom: A (novyy payplayn) po umolchaniyu, B — legacy-mepping cherez
  adapt_vendor_payload(); pri oshibke v A — myagkiy otkat k B.
- (Skrytyy #2) Kvotirovanie i deduplikatsiya na agenta (token-bucket + skolzyaschee okno) — zaschita ot burstov.

ZEMNOY ABZATs:
Lyuboy dron/UGV/manipulyator prisylaet "svoe". This modul privodit vse k edinomu
kanonicheskomu formatu, otsekaet dublikaty/bursty i vozvraschaet gotovyy TelemetryEvent.

# c=a+b"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Tuple

from modules.synergy.models import TelemetryEvent
from modules.synergy.telemetry_ingest import TelemetryIngestor, IngestResult
from modules.synergy.devices.base import DeviceAdapter, AdapterRegistry
from modules.synergy.devices.drone import DroneAdapter, AcmeUavAdapter, NeoDroneAdapter
from modules.synergy.devices.ugv import UgvAdapter
from modules.synergy.devices.robot_arm import RobotArmAdapter
from modules.synergy.devices.simulator import SimulatorAdapter
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Globalnyy reestr adapterov (podkhvatyvaem osnovnye)
REGISTRY = AdapterRegistry()
REGISTRY.register(AcmeUavAdapter())
REGISTRY.register(NeoDroneAdapter())
REGISTRY.register(DroneAdapter())     # generic drone fallback
REGISTRY.register(UgvAdapter())
REGISTRY.register(RobotArmAdapter())
REGISTRY.register(SimulatorAdapter())

# Globalnyy inzhestor (potokobezopasen)
INGESTOR = TelemetryIngestor()


def _select_adapter(vendor: Optional[str], profile: Dict[str, Any] | None) -> DeviceAdapter:
    return REGISTRY.find(vendor or "", profile or {}) or SimulatorAdapter()


def ingest_vendor_event(
    agent_id: str, vendor: Optional[str], payload: Dict[str, Any], profile: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[TelemetryEvent], IngestResult]:
    """Glavnyy vkhod: prinimaet syrye vendor-pakety i vozvraschaet TelemetryEvent (ili None, esli zaglusheno kvotami/dedupom)
    + sluzhebnyy rezultat inzhesta (dlya otladki i metrik)."""
    mode = os.getenv("SYNERGY_ADAPTER_MODE", "A").upper()
    if mode not in ("A", "B"):
        mode = "A"

    if mode == "B":
        # Pryamoy legacy-mepping
        canonical = adapt_vendor_payload(vendor or "", payload)
        evt = TelemetryEvent(
            model="synergy.TelemetryEvent",
            agent_id=agent_id,
            vendor=vendor,
            payload=payload,
            latency_ms=canonical.get("latency_ms"),
            flight_time_min=canonical.get("flight_time_min"),
            payload_g=canonical.get("payload_g"),
        )
        return INGESTOR.ingest(agent_id, evt)

    # Mode A - a modern pipeline with plugins and falsification on legacy in case of an error
    try:
        adapter = _select_adapter(vendor, profile)
        canonical = adapter.to_canonical(vendor or "", payload, profile or {})
    except Exception:
        # Fallback: legacy-mepping
        canonical = adapt_vendor_payload(vendor or "", payload)

    evt = TelemetryEvent(
        model="synergy.TelemetryEvent",
        agent_id=agent_id,
        vendor=vendor,
        payload=payload,
        latency_ms=canonical.get("latency_ms"),
        flight_time_min=canonical.get("flight_time_min"),
        payload_g=canonical.get("payload_g"),
    )
    return INGESTOR.ingest(agent_id, evt)


# ====== Legacy-sovmestimost (sokhraneno po kontraktu) ======

def adapt_vendor_payload(vendor: str, payload: Dict[str, Any]) -> Dict[str, float]:
    """Legacy API: keep the behavior from v1, but implement it through current adapters.
    Returns canonical fields: latenko_ms / flight_topic_min / payload_g"""
    v = (vendor or "").lower()
    try:
        adapter = _select_adapter(v, None)
        return adapter.to_canonical(v, payload, {})
    except Exception:
        # Minimalnye predpolozheniya
        out = {
            "latency_ms": float(payload.get("latency_ms", 120) or 120),
            "flight_time_min": float(payload.get("flight_time_min", 15) or 15),
            "payload_g": float(payload.get("payload_g", 100) or 100),
        }
        # Granitsy
        out["latency_ms"] = max(5.0, min(2000.0, out["latency_ms"]))
        out["flight_time_min"] = max(0.0, min(120.0, out["flight_time_min"]))
        out["payload_g"] = max(0.0, min(50000.0, out["payload_g"]))
        return out