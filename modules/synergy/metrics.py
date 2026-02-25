# -*- coding: utf-8 -*-
"""modules/synergy/metrics.py - domain metrics orkestratsii Synergy.

MOSTY:
- (Yavnyy) record_assign_latency_ms/record_assign_quality/record_api_status/inc_sse_clients — gotovye vyzovy iz orkestratora i API.
- (Skrytyy #1) Initsializatsiya OTel odin raz; vse instrumenty sozdayutsya lenivo i keshiruyutsya.
- (Skrytyy #2) Bezopasnye no-op — vyzovy nichego ne lomayut dazhe bez SDK/Collector.

ZEMNOY ABZATs:
Para vyzovov - i u vas dashbord: latentnost naznacheniya, dolya oshibok, “kachestvo” planov, chislo SSE-podklyucheniy k borde.

# c=a+b"""
from __future__ import annotations

from typing import Dict

from observability.otel import init_otel, get_meter
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_init = init_otel  # re-export for explicit call outside

_METER = None
_H_ASSIGN_LAT = None
_C_ASSIGN_ERR = None
_H_PLAN_TOTAL = None
_H_PLAN_PENALTY = None
_C_API_STATUS = None
_G_SSE = None

def _ensure():
    global _METER, _H_ASSIGN_LAT, _C_ASSIGN_ERR, _H_PLAN_TOTAL, _H_PLAN_PENALTY, _C_API_STATUS, _G_SSE
    if _METER is not None:
        return
    init_otel()
    _METER = get_meter()
    _H_ASSIGN_LAT = _METER.create_histogram("synergy.assign.latency_ms", unit="ms", description="Latency of assign_v2")
    _C_ASSIGN_ERR = _METER.create_counter("synergy.assign.errors_total", description="Errors during assign")
    _H_PLAN_TOTAL = _METER.create_histogram("synergy.plan.total", description="Plan total score")
    _H_PLAN_PENALTY = _METER.create_histogram("synergy.plan.penalty", description="Plan penalty score")
    _C_API_STATUS = _METER.create_counter("synergy.api.status_count", description="API responses by status")
    _G_SSE = _METER.create_up_down_counter("synergy.board.sse_clients", description="Current SSE clients")

def record_assign_latency_ms(value: float, attrs: Dict[str, str] | None = None) -> None:
    _ensure(); _H_ASSIGN_LAT.record(float(value), attributes=attrs or {})

def record_assign_error(kind: str = "unknown", attrs: Dict[str, str] | None = None) -> None:
    _ensure(); a = {"kind": kind}; a.update(attrs or {}); _C_ASSIGN_ERR.add(1, attributes=a)

def record_assign_quality(total: float, penalty: float, attrs: Dict[str, str] | None = None) -> None:
    _ensure(); _H_PLAN_TOTAL.record(float(total), attributes=attrs or {}); _H_PLAN_PENALTY.record(float(penalty), attributes=attrs or {})

def record_api_status(path: str, status_code: int) -> None:
    _ensure(); _C_API_STATUS.add(1, attributes={"path": path, "status": str(int(status_code))})

def inc_sse_clients(delta: int = 1) -> None:
    _ensure(); _G_SSE.add(int(delta), attributes={})