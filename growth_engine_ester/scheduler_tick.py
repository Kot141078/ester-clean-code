# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Mapping

from growth_engine.common import ok

from .config import load_config
from .decision_adapter import shadow_step


def tick_once(payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = load_config()
    if not cfg.enable:
        return ok(action="disabled")
    if cfg.shadow_only:
        body = dict(payload or {})
        if not body:
            return ok(action="shadow_only_idle")
        rep = shadow_step(body)
        return ok(action="shadow_step", result=rep)
    return ok(action="promotion_not_scheduled")


def install_scheduler(app: Any) -> dict[str, Any]:
    return ok(action="not_installed", reason="no safe scheduler integration is assumed by default")
