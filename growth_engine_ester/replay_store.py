# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from growth_engine import ReplaySet

from .state import state_paths


def _default_contexts() -> list[dict[str, Any]]:
    return [
        {"local_signal": 1.0, "judge_signal": 0.1, "online_signal": 0.0, "semantic_signal": 0.8, "target": 1.4},
        {"local_signal": 0.2, "judge_signal": 1.0, "online_signal": 0.0, "semantic_signal": 0.7, "target": 1.1},
        {"local_signal": 0.0, "judge_signal": 0.5, "online_signal": 1.0, "semantic_signal": 0.4, "target": 0.9},
        {"local_signal": 0.4, "judge_signal": 0.4, "online_signal": 0.2, "semantic_signal": 1.0, "target": 1.0},
    ]


def _load_replay_contexts(root: str | None = None) -> list[dict[str, Any]]:
    folder = state_paths(root)["replay"]
    if not folder.exists():
        return []
    contexts: list[dict[str, Any]] = []
    for path in sorted(Path(folder).glob("*.jsonl")):
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue
                ctx = obj.get("context") if isinstance(obj.get("context"), dict) else obj
                if "target" in ctx:
                    contexts.append({k: v for k, v in ctx.items() if isinstance(v, (int, float))})
    return contexts


def score_context(ctx: dict[str, Any], action: Any) -> float:
    target = float(ctx.get("target", 1.0))
    return 1.0 / (1.0 + abs(float(action) - target))


def build_replay(root: str | None = None) -> ReplaySet:
    contexts = _load_replay_contexts(root) or _default_contexts()
    return ReplaySet("ester_srlm_replay", contexts, score_context)
