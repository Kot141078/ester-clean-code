# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Tuple


def _clean_str(value: Any) -> str:
    return str(value or "").strip()


def _ensure_budget(raw: Any) -> Dict[str, int]:
    src = dict(raw or {})
    out = {
        "max_actions": int(src.get("max_actions") or 4),
        "max_work_ms": int(src.get("max_work_ms") or 2000),
        "window": int(src.get("window") or 60),
        "est_work_ms": int(src.get("est_work_ms") or 250),
    }
    out["max_actions"] = max(1, out["max_actions"])
    out["max_work_ms"] = max(1, out["max_work_ms"])
    out["window"] = max(1, out["window"])
    out["est_work_ms"] = max(1, min(out["max_work_ms"], out["est_work_ms"]))
    return out


@dataclass
class AgentSpec:
    name: str
    goal: str
    allowed_actions: List[str] = field(default_factory=list)
    budgets: Dict[str, int] = field(default_factory=dict)
    owner: str = "unknown"
    oracle_policy: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_any(cls, raw: Any) -> "AgentSpec":
        src = dict(raw or {})
        return cls(
            name=_clean_str(src.get("name")),
            goal=_clean_str(src.get("goal")),
            allowed_actions=[
                _clean_str(x)
                for x in list(src.get("allowed_actions") or [])
                if _clean_str(x)
            ],
            budgets=_ensure_budget(src.get("budgets")),
            owner=_clean_str(src.get("owner") or "unknown"),
            oracle_policy=dict(src.get("oracle_policy") or {}),
        )

    def validate(self) -> Tuple[bool, List[str]]:
        errs: List[str] = []
        if not self.name:
            errs.append("name_required")
        if not self.goal:
            errs.append("goal_required")
        if not self.allowed_actions:
            errs.append("allowed_actions_required")
        if any((not str(a).strip()) for a in self.allowed_actions):
            errs.append("allowed_actions_invalid")
        self.budgets = _ensure_budget(self.budgets)
        if self.owner == "":
            errs.append("owner_required")
        return len(errs) == 0, errs

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["budgets"] = _ensure_budget(out.get("budgets"))
        return out


__all__ = ["AgentSpec"]

