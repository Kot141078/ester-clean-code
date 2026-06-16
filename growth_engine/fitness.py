# -*- coding: utf-8 -*-
"""growth_engine.fitness - the external fitness signal.

The single most important (and hardest) part of any honest growth engine.
Without an external, consequence-bound score, "growth" degrades into drift toward
self-pleasing answers - exactly the failure Kotov warns about.

Hard rule enforced here: an Outcome's score must declare a `source` that is one of
{human, reality, l4}. A score whose source is the model judging itself is rejected.
This turns experience.py from a labelled log into a ledger of *evaluated* outcomes:
    case -> action -> outcome(score, source) -> uncertainty.

SEAM for ester-clean-code: replace `record_outcome` callers with hooks fired from
(a) human edits/ratings, (b) task success/failure in reality, (c) L4 budget
satisfaction. Nothing else may mint fitness.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .common import mean, now_ts, ok, err

VALID_SOURCES = {"human", "reality", "l4"}


@dataclass(frozen=True)
class Episode:
    """A past interaction we can replay/score."""

    episode_id: str
    context: Dict[str, Any]
    action: Any
    behavior_version: str = ""
    ts: int = 0
    tags: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class Outcome:
    """An externally-attributed score for an episode."""

    episode_id: str
    score: float  # higher = better; keep in a known range per signal, e.g. (0, 1]
    source: str  # one of VALID_SOURCES
    uncertainty: float = 0.0
    ts: int = 0
    note: str = ""


class FitnessLedger:
    def __init__(self, root: str | os.PathLike) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = (self.root / "fitness.jsonl").resolve()

    def record_outcome(self, outcome: Outcome) -> Dict[str, Any]:
        if str(outcome.source) not in VALID_SOURCES:
            return err(
                "FITNESS_SOURCE_INVALID",
                f"source_must_be_external:{outcome.source}",
                allowed=sorted(VALID_SOURCES),
            )
        row = asdict(outcome)
        if not int(row.get("ts") or 0):
            row["ts"] = now_ts()
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n")
        return ok(recorded=row)

    def outcomes(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        out: List[Dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    out.append(obj)
        return out

    def low_fitness_episodes(self, threshold: float, limit: int = 0) -> List[Dict[str, Any]]:
        rows = [r for r in self.outcomes() if float(r.get("score", 1.0)) < float(threshold)]
        rows.sort(key=lambda r: float(r.get("score", 1.0)))
        if limit and limit > 0:
            rows = rows[: int(limit)]
        return rows

    def aggregate(self) -> Dict[str, Any]:
        rows = self.outcomes()
        return {
            "n": len(rows),
            "mean_score": mean(float(r.get("score", 0.0)) for r in rows),
            "by_source": {
                src: mean(float(r.get("score", 0.0)) for r in rows if r.get("source") == src)
                for src in VALID_SOURCES
            },
        }
