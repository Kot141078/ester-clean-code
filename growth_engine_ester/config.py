# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping


def _truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _float_env(env: Mapping[str, str], key: str, default: float) -> float:
    try:
        return float(env.get(key, str(default)) or default)
    except Exception:
        return float(default)


def _int_env(env: Mapping[str, str], key: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(env.get(key, str(default)) or default))
    except Exception:
        return max(minimum, int(default))


@dataclass(frozen=True)
class SRLMConfig:
    root: str
    enable: bool
    ack_risk: bool
    allow_promote: bool
    min_margin: float
    max_promotions_per_window: int
    window_seconds: int
    shadow_only: bool
    canary_enable: bool
    promote_low_only: bool

    @property
    def promotion_gate_open(self) -> bool:
        return self.enable and self.ack_risk and self.allow_promote

    def as_status(self) -> dict[str, Any]:
        return {
            "ok": True,
            "enabled": self.enable,
            "root": self.root,
            "gates": {
                "ESTER_SRLM_ENABLE": self.enable,
                "ESTER_SRLM_ACK_RISK": self.ack_risk,
                "ESTER_SRLM_ALLOW_PROMOTE": self.allow_promote,
                "promotion_gate_open": self.promotion_gate_open,
            },
            "limits": {
                "min_margin": self.min_margin,
                "max_promotions_per_window": self.max_promotions_per_window,
                "window_seconds": self.window_seconds,
                "shadow_only": self.shadow_only,
                "canary_enable": self.canary_enable,
                "promote_low_only": self.promote_low_only,
            },
        }


def load_config(env: Mapping[str, str] | None = None) -> SRLMConfig:
    src = env or os.environ
    return SRLMConfig(
        root=str(src.get("ESTER_SRLM_ROOT", os.path.join("data", "srlm")) or os.path.join("data", "srlm")),
        enable=_truthy(src.get("ESTER_SRLM_ENABLE"), False),
        ack_risk=str(src.get("ESTER_SRLM_ACK_RISK", "") or "") == "I_UNDERSTAND",
        allow_promote=_truthy(src.get("ESTER_SRLM_ALLOW_PROMOTE"), False),
        min_margin=_float_env(src, "ESTER_SRLM_MIN_MARGIN", 0.02),
        max_promotions_per_window=_int_env(src, "ESTER_SRLM_MAX_PROMOTIONS_PER_WINDOW", 3, 0),
        window_seconds=_int_env(src, "ESTER_SRLM_WINDOW_SECONDS", 86400, 1),
        shadow_only=_truthy(src.get("ESTER_SRLM_SHADOW_ONLY"), True),
        canary_enable=_truthy(src.get("ESTER_SRLM_CANARY_ENABLE"), False),
        promote_low_only=_truthy(src.get("ESTER_SRLM_PROMOTE_LOW_ONLY"), True),
    )


def status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    return load_config(env).as_status()
