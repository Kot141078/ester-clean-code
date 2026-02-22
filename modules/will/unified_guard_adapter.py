# -*- coding: utf-8 -*-
"""
modules/will/unified_guard_adapter.py
(soderzhimoe sm. v osnovnom otvete; eta kopiya identichna)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.autonomy import state as autonomy_state  # type: ignore
except Exception:  # pragma: no cover
    autonomy_state = None  # type: ignore

try:
    from modules.will import consent_gate as will_consent  # type: ignore
except Exception:  # pragma: no cover
    will_consent = None  # type: ignore


@dataclass
class WillDecision:
    ok: bool
    reason: str
    area: str
    need: List[str]
    min_level: int
    snapshot: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _ab_mode() -> str:
    v = os.getenv("ESTER_WILL_UNIFIED_AB", "A").strip().upper()
    return "B" if v == "B" else "A"


def _safe_snapshot() -> Dict[str, Any]:
    snap: Dict[str, Any] = {}
    if autonomy_state is not None:
        try:
            snap["autonomy"] = autonomy_state.get()
        except Exception:
            snap["autonomy"] = {"error": "autonomy_state_get_failed"}
    if will_consent is not None:
        try:
            base = will_consent.check(need=None, min_level=0)  # type: ignore[arg-type]
            snap["will_probe"] = {k: v for k, v in base.items() if k != "snapshot"}
        except Exception:
            snap["will_probe"] = {"error": "will_check_failed"}
    return snap


def classify_http_path(path: str):
    p = path or "/"
    if p.startswith("/replication") or p.startswith("/backup"):
        return "files", ["files"], 1
    if p.startswith("/p2p") or p.startswith("/sync"):
        return "network", ["network"], 2
    if p.startswith("/ingest"):
        return "files", ["files"], 1
    if p.startswith("/computer_use") or p.startswith("/rpa"):
        return "rpa_ui", ["rpa_ui"], 2
    if p.startswith("/ops") or p.startswith("/admin/ops"):
        return "ops", ["files", "network"], 2
    return "generic", [], 0


def decide(area=None, need=None, min_level: int = 1, strict: bool = False) -> WillDecision:
    mode = _ab_mode()
    eff_area = (area or "generic").lower()
    eff_need = list(need or [])
    eff_min = int(min_level)
    snap = _safe_snapshot()

    if mode == "A":
        return WillDecision(
            ok=True,
            reason="observe_only",
            area=eff_area,
            need=eff_need,
            min_level=eff_min,
            snapshot=snap,
        )

    if will_consent is None:
        return WillDecision(
            ok=not strict,
            reason="will_consent_missing" if strict else "missing_but_not_strict",
            area=eff_area,
            need=eff_need,
            min_level=eff_min,
            snapshot=snap,
        )

    try:
        res = will_consent.check(eff_need, eff_min)  # type: ignore[arg-type]
    except Exception as e:  # pragma: no cover
        return WillDecision(
            ok=not strict,
            reason=f"will_check_error:{e!s}" if strict else "will_check_error_soft",
            area=eff_area,
            need=eff_need,
            min_level=eff_min,
            snapshot=snap,
        )

    ok = bool(res.get("allowed", False))
    reason = str(res.get("reason", "unknown"))
    nested = res.get("snapshot")
    if isinstance(nested, dict):
        snap["will_snapshot"] = nested

    if strict and not ok:
        return WillDecision(
            ok=False,
            reason=f"denied:{reason}",
            area=eff_area,
            need=eff_need,
            min_level=eff_min,
            snapshot=snap,
        )

    return WillDecision(
        ok=ok,
        reason=reason,
        area=eff_area,
        need=eff_need,
        min_level=eff_min,
        snapshot=snap,
    )


def require(area=None, need=None, min_level: int = 1, strict: bool = True) -> WillDecision:
    dec = decide(area=area, need=need, min_level=min_level, strict=strict)
    if strict and not dec.ok:
        raise PermissionError(f"Ester will denied action: {dec.reason}")
    return dec


__all__ = ["WillDecision", "decide", "require", "classify_http_path"]