# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from .config import status as config_status
from .outcome_candidates import candidate_stats
from .state import load_promoted_policy, read_jsonl, state_paths
from .promotion_adapter import verify_witness
from .quality import replay_quality_profile


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "")
        if value:
            out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items()))


def build_report(*, root: str | None = None) -> dict[str, Any]:
    paths = state_paths(root)
    fitness = read_jsonl(paths["fitness"], limit=1000)
    rejections = read_jsonl(paths["outcome_rejections"], limit=1000)
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
    latest_shadow_event = None
    for row in reversed(witness_rows):
        if row.get("event_type") == "shadow_eval":
            latest_shadow_event = row
            break
    latest_candidate = candidates[-1] if candidates else None
    latest_report = paths["reports"] / "latest_shadow_report.md"
    replay_eligible = [row for row in fitness if row.get("redacted") is True and row.get("eligible_for_replay") is True]
    min_real = 20
    outcome_candidate_stats = candidate_stats(root=str(paths["root"]))
    replay_quality = replay_quality_profile(root=str(paths["root"]), min_total=min_real)
    config = config_status()
    return {
        "ok": True,
        "config": config,
        "state": {
            "root": str(paths["root"]),
            "has_promoted_policy": paths["promoted_policy"].exists(),
            "fitness_rows": len(fitness),
            "candidate_rows": len(candidates),
            "outcome_candidate_rows": int(outcome_candidate_stats.get("total_candidates", 0) or 0),
            "witness_rows": len(witness_rows),
            "latest_shadow_report": str(latest_report) if latest_report.exists() else "",
        },
        "fitness": {
            "n": len(fitness),
            "mean_score": _mean(fitness_scores),
            "fitness_curve": fitness_curve,
            "total_outcomes": len(fitness),
            "counts_by_source": _counts(fitness, "source"),
            "counts_by_event_kind": _counts(fitness, "event_kind"),
            "rejected_outcome_count": len(rejections),
            "last_accepted_outcome": fitness[-1] if fitness else None,
            "replay_eligible_count": len(replay_eligible),
            "warning": "too_few_real_outcomes" if len(replay_eligible) < min_real else "",
            "min_real_outcomes_for_replay": min_real,
        },
        "outcome_candidates": outcome_candidate_stats,
        "replay_quality": replay_quality,
        "promotion": {
            "promotion_gate_open": bool(config.get("gates", {}).get("promotion_gate_open")),
            "shadow_only": bool(config.get("limits", {}).get("shadow_only", True)),
            "canary_enable": bool(config.get("limits", {}).get("canary_enable", False)),
        },
        "latest_shadow_event": latest_shadow_event,
        "latest_candidate": latest_candidate,
        "witness": verify_witness(root=str(paths["root"])),
        "current_policy": load_promoted_policy(str(paths["root"])),
    }
