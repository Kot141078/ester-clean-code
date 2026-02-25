# -*- coding: utf-8 -*-
"""tests/synergy/test_device_adapters.py - skvoznye testy ingest-konveyera i adapterov.

MOSTY:
- (Yavnyy) Proveryaem acme/neo/ugv/robarm/sim protiv ozhidaniy.
- (Skrytyy #1) A/B-rezhim: newy konveyer i legacy-sovmestimost.
- (Skrytyy #2) Kvoty i dedup: burst -> chast sobytiy otbrasyvaetsya s korrektnoy prichinoy.

ZEMNOY ABZATs:
Garantiya, what “syroy” paket v lyuboy forme prevraschaetsya v kanon, a shum filtruetsya.

# c=a+b"""
from __future__ import annotations

import json
import os
import time

import pytest

from modules.synergy.device_adapter import ingest_vendor_event, adapt_vendor_payload
from modules.synergy.models import TelemetryEvent
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


FIX_PATH = os.path.join(os.path.dirname(__file__), "..", "fixtures", "synergy", "vendor_packets.json")

with open(FIX_PATH, "r", encoding="utf-8") as f:
    FIX = json.load(f)


@pytest.mark.parametrize("vendor_key,device_profile", [
    ("acme_uav", {"device": "drone"}),
    ("neo", {"device": "drone"}),
    ("ugv_mk1", {"device": "ugv"}),
    ("robarm", {"device": "robot_arm"}),
    ("sim", {"device": "drone"})
])
def test_ingest_pipeline(vendor_key, device_profile, monkeypatch):
    monkeypatch.setenv("SYNERGY_ADAPTER_MODE", "A")
    agent_id = f"agent.{vendor_key}"
    vendor = vendor_key
    payload = FIX[vendor_key]["payload"]
    expect = FIX[vendor_key]["expect"]

    evt, res = ingest_vendor_event(agent_id, vendor, payload, device_profile)
    assert res.ok and evt is not None
    assert isinstance(evt, TelemetryEvent)
    assert round(float(evt.latency_ms or 0), 3) == round(float(expect["latency_ms"]), 3)
    assert round(float(evt.flight_time_min or 0), 3) == round(float(expect["flight_time_min"]), 3)
    assert round(float(evt.payload_g or 0), 3) == round(float(expect["payload_g"]), 3)


def test_legacy_fallback_compat():
    vendor = "acme_uav"
    payload = FIX[vendor]["payload"]
    canon = adapt_vendor_payload(vendor, payload)
    assert canon["latency_ms"] == pytest.approx(FIX[vendor]["expect"]["latency_ms"])
    assert canon["flight_time_min"] == pytest.approx(FIX[vendor]["expect"]["flight_time_min"])
    assert canon["payload_g"] == pytest.approx(FIX[vendor]["expect"]["payload_g"])


def test_rate_limit_and_dedup(monkeypatch):
    # We compress quotas and the window to make the test faster
    monkeypatch.setenv("SYNERGY_ADAPTER_MODE", "A")
    monkeypatch.setenv("SYNERGY_TEL_MAX_RPS", "5")
    monkeypatch.setenv("SYNERGY_TEL_DEDUP_WINDOW_MS", "2000")
    agent_id = "agent.burst"
    vendor = "neo"
    payload = FIX[vendor]["payload"]

    # Send 10 identical events in a row
    oks = 0
    dups = 0
    rate = 0
    for _ in range(10):
        evt, res = ingest_vendor_event(agent_id, vendor, payload, {"device": "drone"})
        if res.reason == "ok":
            oks += 1
        elif res.reason == "duplicate":
            dups += 1
        elif res.reason == "rate_limited":
            rate += 1
        time.sleep(0.01)  # Let's stretch it out a little so that the tokens flow in

    # There must be both duplicates and rate limits within the window
    assert oks >= 1
    assert dups >= 1
    assert rate >= 1