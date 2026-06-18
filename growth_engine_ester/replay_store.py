# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from growth_engine import ReplaySet
from growth_engine.common import err, ok

from .outcomes import accepted_outcomes
from .quality import fail_for_quality, replay_quality_profile
from .state import ensure_layout, state_paths

REAL_REPLAY_SCHEMA = "ester.srlm.replay.real_redacted.v1"
DEFAULT_MIN_REAL_OUTCOMES = 20


class ReplayUnavailable(ValueError):
    def __init__(self, report: dict[str, Any]) -> None:
        super().__init__(str(report.get("error_code") or "replay_unavailable"))
        self.report = report


def _default_contexts() -> list[dict[str, Any]]:
    return [
        {"local_signal": 1.0, "judge_signal": 0.1, "online_signal": 0.0, "semantic_signal": 0.8, "target": 1.4},
        {"local_signal": 0.2, "judge_signal": 1.0, "online_signal": 0.0, "semantic_signal": 0.7, "target": 1.1},
        {"local_signal": 0.0, "judge_signal": 0.5, "online_signal": 1.0, "semantic_signal": 0.4, "target": 0.9},
        {"local_signal": 0.4, "judge_signal": 0.4, "online_signal": 0.2, "semantic_signal": 1.0, "target": 1.0},
    ]


def _write_bytes_if_changed(path: Path, data: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.exists() and path.read_bytes() == data:
            return False
    except Exception:
        pass
    path.write_bytes(data)
    return True


def _load_replay_contexts(root: str | None = None) -> list[dict[str, Any]]:
    folder = state_paths(root)["replay"]
    if not folder.exists():
        return []
    contexts: list[dict[str, Any]] = []
    for path in sorted(Path(folder).glob("*.jsonl")):
        if path.name == "real_redacted.jsonl":
            continue
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


def eligible_real_outcomes(root: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for row in accepted_outcomes(root):
        if row.get("schema") != "ester.srlm.outcome.v1":
            continue
        if row.get("redacted") is not True:
            continue
        if row.get("eligible_for_replay") is not True:
            continue
        rows.append(row)
    return rows


def _context_from_outcome(row: dict[str, Any]) -> dict[str, Any]:
    source = str(row.get("source") or "")
    score = max(0.0, min(1.0, float(row.get("score", 0.0) or 0.0)))
    uncertainty = max(0.0, min(1.0, float(row.get("uncertainty", 0.0) or 0.0)))
    ctx = {
        "local_signal": 0.0,
        "judge_signal": 0.0,
        "online_signal": 0.0,
        "semantic_signal": 0.0,
        "structured_signal": 0.0,
        "card_signal": 0.0,
        "target": score * 2.0,
        "uncertainty": uncertainty,
    }
    if source == "human":
        ctx["local_signal"] = 1.0
        ctx["semantic_signal"] = 0.6
    elif source == "reality":
        ctx["online_signal"] = 1.0
        ctx["structured_signal"] = 0.6
    elif source == "l4":
        ctx["judge_signal"] = 1.0
        ctx["card_signal"] = 0.4
    return ctx


def score_context(ctx: dict[str, Any], action: Any) -> float:
    target = float(ctx.get("target", 1.0))
    uncertainty = max(0.0, min(1.0, float(ctx.get("uncertainty", 0.0) or 0.0)))
    base = 1.0 / (1.0 + abs(float(action) - target))
    return base * (1.0 - (uncertainty * 0.5))


def replay_status(*, root: str | None = None, min_n: int = DEFAULT_MIN_REAL_OUTCOMES) -> dict[str, Any]:
    paths = state_paths(root)
    rows = eligible_real_outcomes(str(paths["root"]))
    quality = replay_quality_profile(root=str(paths["root"]), min_total=int(min_n))
    return ok(
        synthetic={"available": True, "label": "synthetic"},
        real_redacted={
            "available": bool(quality.get("quality_ready")),
            "eligible_count": len(rows),
            "min_required": int(min_n),
            "path": str(paths["real_replay"]),
            "label": "real_redacted",
            "status": "ready" if quality.get("quality_ready") else str((quality.get("blocking_reasons") or ["replay_quality_not_ready"])[0]),
            "quality": quality,
        },
    )


def build_real_replay(*, root: str | None = None, min_n: int = DEFAULT_MIN_REAL_OUTCOMES) -> dict[str, Any]:
    paths = ensure_layout(root)
    quality = replay_quality_profile(root=str(paths["root"]), min_total=int(min_n))
    if not quality.get("quality_ready"):
        return fail_for_quality(quality)
    rows = eligible_real_outcomes(str(paths["root"]))
    records = []
    for row in rows:
        records.append(
            {
                "schema": REAL_REPLAY_SCHEMA,
                "outcome_id": row.get("outcome_id"),
                "source": row.get("source"),
                "event_kind": row.get("event_kind"),
                "evidence_hash": row.get("evidence_hash"),
                "score": row.get("score"),
                "uncertainty": row.get("uncertainty"),
                "redacted": True,
                "context": _context_from_outcome(row),
            }
        )
    path = paths["real_replay"]
    replay_text = "".join(json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n" for record in records)
    replay_bytes = replay_text.encode("utf-8")
    replay_written = _write_bytes_if_changed(path, replay_bytes)
    replay_hash = hashlib.sha256(replay_bytes).hexdigest()
    meta = {
        "schema": "ester.srlm.replay.real_redacted.meta.v1",
        "replay_source": "real_redacted",
        "path": str(path),
        "count": len(records),
        "replay_hash": replay_hash,
        "quality_hash": quality.get("quality_hash", ""),
        "quality": quality,
        "source_counts": quality.get("source_counts", {}),
        "event_kind_counts": quality.get("event_kind_counts", {}),
    }
    metadata_written = _write_bytes_if_changed(
        paths["real_replay_meta"],
        json.dumps(meta, ensure_ascii=True, sort_keys=True, indent=2).encode("utf-8"),
    )
    return ok(
        path=str(path),
        metadata_path=str(paths["real_replay_meta"]),
        count=len(records),
        replay_source="real_redacted",
        label="real_redacted",
        replay_hash=replay_hash,
        quality_hash=quality.get("quality_hash", ""),
        quality=quality,
        replay_written=replay_written,
        metadata_written=metadata_written,
    )


def replay_metadata(*, root: str | None = None) -> dict[str, Any]:
    path = state_paths(root)["real_replay_meta"]
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _real_replay_unavailable(root: str | None, min_n: int, error_code: str, error: str, **extra: Any) -> ReplayUnavailable:
    quality = replay_quality_profile(root=root, min_total=int(min_n))
    if not quality.get("quality_ready"):
        return ReplayUnavailable(fail_for_quality(quality))
    return ReplayUnavailable(
        err(
            error_code,
            error,
            replay_source="real_redacted",
            quality=quality,
            min_required=int(min_n),
            **extra,
        )
    )


def _load_real_replay_contexts(root: str | None = None, *, min_n: int = DEFAULT_MIN_REAL_OUTCOMES) -> list[dict[str, Any]]:
    paths = state_paths(root)
    replay_path = paths["real_replay"]
    meta_path = paths["real_replay_meta"]
    if not replay_path.exists() or not meta_path.exists():
        raise _real_replay_unavailable(
            str(paths["root"]),
            min_n,
            "real_redacted_replay_missing",
            "real_redacted replay is missing; run /srlm/replay/build first",
            replay_path=str(replay_path),
            metadata_path=str(meta_path),
        )
    meta = replay_metadata(root=str(paths["root"]))
    if not meta:
        raise _real_replay_unavailable(
            str(paths["root"]),
            min_n,
            "real_redacted_replay_metadata_invalid",
            "real_redacted replay metadata is missing or invalid; run /srlm/replay/build first",
            metadata_path=str(meta_path),
        )
    expected_hash = str(meta.get("replay_hash") or "")
    actual_hash = hashlib.sha256(replay_path.read_bytes()).hexdigest()
    if not expected_hash or actual_hash != expected_hash:
        raise _real_replay_unavailable(
            str(paths["root"]),
            min_n,
            "real_redacted_replay_hash_mismatch",
            "real_redacted replay hash does not match metadata; run /srlm/replay/build first",
            replay_hash=actual_hash,
            expected_replay_hash=expected_hash,
        )
    quality = replay_quality_profile(root=str(paths["root"]), min_total=int(min_n))
    if not quality.get("quality_ready"):
        raise ReplayUnavailable(fail_for_quality(quality))
    current_quality_hash = str(quality.get("quality_hash") or "")
    metadata_quality_hash = str(meta.get("quality_hash") or "")
    if current_quality_hash != metadata_quality_hash:
        raise _real_replay_unavailable(
            str(paths["root"]),
            min_n,
            "real_redacted_replay_stale",
            "real_redacted replay quality hash does not match current outcomes; run /srlm/replay/build first",
            replay_quality_hash=metadata_quality_hash,
            current_quality_hash=current_quality_hash,
        )
    contexts: list[dict[str, Any]] = []
    with replay_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            ctx = obj.get("context") if isinstance(obj, dict) else None
            if isinstance(ctx, dict) and "target" in ctx:
                contexts.append({k: v for k, v in ctx.items() if isinstance(v, (int, float))})
    if len(contexts) < int(min_n):
        raise ReplayUnavailable(
            err(
                "insufficient_real_outcomes",
                "real replay file contains too few usable contexts",
                eligible_count=len(contexts),
                min_required=int(min_n),
                replay_source="real_redacted",
            )
        )
    return contexts


def build_replay(root: str | None = None, *, source: str = "synthetic", min_real: int = DEFAULT_MIN_REAL_OUTCOMES) -> ReplaySet:
    replay_source = str(source or "synthetic").strip().lower()
    if replay_source == "synthetic":
        contexts = _load_replay_contexts(root) or _default_contexts()
        return ReplaySet("ester_srlm_replay_synthetic", contexts, score_context)
    if replay_source == "real_redacted":
        contexts = _load_real_replay_contexts(root, min_n=min_real)
        return ReplaySet("ester_srlm_replay_real_redacted", contexts, score_context)
    raise ReplayUnavailable(err("SRLM_REPLAY_SOURCE_INVALID", f"unknown replay_source:{replay_source}", replay_source=replay_source))
