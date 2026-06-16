# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Any, Mapping

from growth_engine import FitnessLedger, Outcome, VALID_SOURCES
from growth_engine.common import err

from .config import load_config
from .state import ensure_layout

_SENSITIVE = re.compile(r"(?i)(api[_-]?key|authorization|bearer|password|secret|token)\s*[:=]\s*\S+")


def _clean_note(value: Any) -> str:
    text = " ".join(str(value or "").split())[:500]
    return _SENSITIVE.sub(r"\1=<redacted>", text)


def record_outcome(payload: Mapping[str, Any], *, root: str | None = None) -> dict[str, Any]:
    data = dict(payload or {})
    source = str(data.get("source") or "").strip().lower()
    if source not in VALID_SOURCES:
        return err("FITNESS_SOURCE_INVALID", f"source_must_be_external:{source}", allowed=sorted(VALID_SOURCES))
    try:
        score = float(data.get("score"))
    except Exception:
        return err("FITNESS_SCORE_INVALID", "score must be numeric")
    try:
        uncertainty = float(data.get("uncertainty", 0.0) or 0.0)
    except Exception:
        uncertainty = 0.0
    episode_id = str(data.get("episode_id") or "").strip()
    if not episode_id:
        return err("FITNESS_EPISODE_ID_REQUIRED", "episode_id is required")
    cfg = load_config()
    paths = ensure_layout(root or cfg.root)
    ledger = FitnessLedger(str(paths["root"]))
    return ledger.record_outcome(
        Outcome(
            episode_id=episode_id,
            score=score,
            source=source,
            uncertainty=uncertainty,
            note=_clean_note(data.get("note", "")),
        )
    )
