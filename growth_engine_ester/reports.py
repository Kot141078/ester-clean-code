# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from .config import status as config_status
from .state import load_promoted_policy, read_jsonl, state_paths
from .promotion_adapter import verify_witness


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def build_report(*, root: str | None = None) -> dict[str, Any]:
    paths = state_paths(root)
    fitness = read_jsonl(paths["fitness"], limit=1000)
    witness_rows = read_jsonl(paths["witness"], limit=1000)
    candidates = read_jsonl(paths["candidates"], limit=1000)
    fitness_scores = [float(row.get("score", 0.0) or 0.0) for row in fitness]
    fitness_curve = []
    for row in witness_rows:
        if row.get("event_type") == "promotion":
            subj = row.get("subject") if isinstance(row.get("subject"), dict) else {}
            if "candidate_fit" in subj:
                try:
                    fitness_curve.append(float(subj["candidate_fit"]))
                except Exception:
                    pass
    return {
        "ok": True,
        "config": config_status(),
        "state": {
            "root": str(paths["root"]),
            "has_promoted_policy": paths["promoted_policy"].exists(),
            "fitness_rows": len(fitness),
            "candidate_rows": len(candidates),
            "witness_rows": len(witness_rows),
        },
        "fitness": {
            "n": len(fitness),
            "mean_score": _mean(fitness_scores),
            "fitness_curve": fitness_curve,
        },
        "witness": verify_witness(root=str(paths["root"])),
        "current_policy": load_promoted_policy(str(paths["root"])),
    }
