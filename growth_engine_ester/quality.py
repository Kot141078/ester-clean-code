# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from collections import Counter
from typing import Any, Mapping

from growth_engine import VALID_SOURCES
from growth_engine.common import err, hash_obj, ok, q

from .outcomes import OUTCOME_SCHEMA, accepted_outcomes, rejected_outcomes
from .redaction import SECRET_RE, PRIVATE_DUMP_RE, MAX_NOTE_CHARS

FORBIDDEN_CONTAMINATION_SOURCES = {
    "model",
    "judge",
    "judge-only",
    "confidence",
    "confidence-only",
    "fluency",
    "fluency-only",
    "self",
    "self-score",
    "vibe",
}


def _counts(rows: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "") for row in rows if str(row.get(key) or "")).items()))


def _score_distribution(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    scores = [float(row.get("score", 0.0) or 0.0) for row in rows]
    if not scores:
        return {"n": 0, "min": 0.0, "max": 0.0, "mean": 0.0, "identical": False}
    return {
        "n": len(scores),
        "min": min(scores),
        "max": max(scores),
        "mean": sum(scores) / len(scores),
        "identical": len({q(score) for score in scores}) == 1,
    }


def _duplicate_counts(rows: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts = Counter(str(row.get(key) or "") for row in rows if str(row.get(key) or ""))
    return dict(sorted((key, value) for key, value in counts.items() if value > 1))


def _safe_outcome(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "outcome_id": row.get("outcome_id", ""),
        "created_at": row.get("created_at", ""),
        "source": row.get("source", ""),
        "score": row.get("score", 0.0),
        "uncertainty": row.get("uncertainty", 0.0),
        "event_kind": row.get("event_kind", ""),
        "source_ref": row.get("source_ref", ""),
        "evidence_hash": row.get("evidence_hash", ""),
        "redacted": row.get("redacted") is True,
        "notes": str(row.get("notes") or "")[:MAX_NOTE_CHARS],
        "eligible_for_replay": row.get("eligible_for_replay") is True,
        "eligible_for_promotion": row.get("eligible_for_promotion") is True,
        "auto_ingest": row.get("auto_ingest") is True,
        "memory": row.get("memory", ""),
    }


def list_outcomes(*, root: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    rows = [_safe_outcome(row) for row in accepted_outcomes(root)]
    start = max(0, int(offset))
    count = max(1, min(200, int(limit)))
    return ok(total=len(rows), limit=count, offset=start, outcomes=rows[start : start + count])


def list_rejections(*, root: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    rows = []
    for row in rejected_outcomes(root):
        rows.append(
            {
                "created_at": row.get("created_at", ""),
                "error_code": row.get("error_code", ""),
                "error": row.get("error", ""),
                "source": row.get("source", ""),
                "event_kind": row.get("event_kind", ""),
                "source_ref_hash": row.get("source_ref_hash", ""),
                "auto_ingest": row.get("auto_ingest") is True,
                "memory": row.get("memory", ""),
            }
        )
    start = max(0, int(offset))
    count = max(1, min(200, int(limit)))
    return ok(total=len(rows), limit=count, offset=start, rejections=rows[start : start + count])


def outcome_stats(*, root: str | None = None) -> dict[str, Any]:
    rows = accepted_outcomes(root)
    rejections = rejected_outcomes(root)
    replay_eligible = [row for row in rows if row.get("redacted") is True and row.get("eligible_for_replay") is True]
    evidence_present = sum(1 for row in rows if str(row.get("evidence_hash") or "") or str(row.get("source_ref") or ""))
    redacted_count = sum(1 for row in rows if row.get("redacted") is True)
    duplicate_ids = _duplicate_counts(rows, "outcome_id")
    duplicate_refs = _duplicate_counts(rows, "source_ref")
    return ok(
        total_outcomes=len(rows),
        replay_eligible_count=len(replay_eligible),
        rejection_count=len(rejections),
        duplicate_count=sum(duplicate_ids.values()) - len(duplicate_ids),
        near_duplicate_source_ref_count=sum(duplicate_refs.values()) - len(duplicate_refs),
        source_counts=_counts(rows, "source"),
        event_kind_counts=_counts(rows, "event_kind"),
        score_distribution=_score_distribution(rows),
        evidence_hash_present=evidence_present,
        redacted_count=redacted_count,
        redaction_status={"redacted": redacted_count, "not_redacted": len(rows) - redacted_count},
        duplicate_outcome_ids=duplicate_ids,
        near_duplicate_source_refs=duplicate_refs,
    )


def _row_is_convertible(row: Mapping[str, Any]) -> bool:
    try:
        score = float(row.get("score"))
        uncertainty = float(row.get("uncertainty", 0.0) or 0.0)
    except Exception:
        return False
    return math.isfinite(score) and math.isfinite(uncertainty) and 0.0 <= score <= 1.0 and 0.0 <= uncertainty <= 1.0


def _quality_rows(root: str | None = None) -> list[dict[str, Any]]:
    return [dict(row) for row in accepted_outcomes(root) if row.get("eligible_for_replay") is True]


def replay_quality_profile(*, root: str | None = None, min_total: int = 20) -> dict[str, Any]:
    rows = _quality_rows(root)
    blocking: list[str] = []
    warnings: list[str] = []

    eligible_total = len(rows)
    if eligible_total < int(min_total):
        blocking.append("insufficient_real_outcomes")

    source_counts = _counts(rows, "source")
    event_kind_counts = _counts(rows, "event_kind")
    valid_source_count = sum(1 for source in source_counts if source in VALID_SOURCES)
    if valid_source_count < 2 and eligible_total >= int(min_total):
        blocking.append("insufficient_source_mix")
    if valid_source_count < 3 and eligible_total:
        warnings.append("preferred_all_three_sources_missing")
    if eligible_total:
        max_source_fraction = max(source_counts.values()) / eligible_total
        if max_source_fraction > 0.80 and eligible_total >= int(min_total):
            blocking.append("single_source_exceeds_80_percent")
        if max_source_fraction >= 1.0:
            warnings.append("one_source_only")

    if len(event_kind_counts) < 3 and eligible_total:
        warnings.append("low_event_diversity")
    if len(event_kind_counts) == 1 and eligible_total:
        warnings.append("single_event_kind")

    scores = []
    for row in rows:
        try:
            score = float(row.get("score"))
            uncertainty = float(row.get("uncertainty", 0.0) or 0.0)
        except Exception:
            blocking.append("score_not_numeric")
            continue
        if not math.isfinite(score) or not math.isfinite(uncertainty):
            blocking.append("score_not_finite")
        if score < 0.0 or score > 1.0 or uncertainty < 0.0 or uncertainty > 1.0:
            blocking.append("score_out_of_range")
        scores.append(score)
    if scores and len({q(score) for score in scores}) == 1:
        warnings.append("identical_scores")
    if scores and max(scores) - min(scores) < 0.05:
        warnings.append("degenerate_score_distribution")

    for row in rows:
        source = str(row.get("source") or "").strip().lower()
        event_kind = str(row.get("event_kind") or "").strip().lower()
        notes = str(row.get("notes") or "")
        source_ref = str(row.get("source_ref") or "")
        if source not in VALID_SOURCES:
            blocking.append("forbidden_source_contamination")
        if source in FORBIDDEN_CONTAMINATION_SOURCES or any(token in event_kind for token in ("model", "self", "confidence", "fluency", "vibe", "judge-only")):
            blocking.append("self_score_contamination")
        if row.get("redacted") is not True:
            blocking.append("unredacted_outcome")
        if len(notes) > MAX_NOTE_CHARS:
            blocking.append("notes_too_long")
        if SECRET_RE.search(notes) or SECRET_RE.search(source_ref):
            blocking.append("secret_pattern_detected")
        if PRIVATE_DUMP_RE.search(notes) or PRIVATE_DUMP_RE.search(source_ref):
            blocking.append("private_payload_detected")
        if ".env" in notes.lower() or ".env" in source_ref.lower():
            blocking.append("env_dump_detected")
        if "full_chat_log" in notes.lower() or "raw chat" in notes.lower():
            blocking.append("raw_chat_log_detected")
        if not str(row.get("evidence_hash") or "") and not source_ref:
            warnings.append("missing_evidence_reference")
        if not _row_is_convertible(row):
            blocking.append("replay_case_not_convertible")

    duplicate_ids = _duplicate_counts(rows, "outcome_id")
    duplicate_refs = _duplicate_counts(rows, "source_ref")
    if duplicate_ids:
        blocking.append("duplicate_outcome_id")
    if duplicate_refs:
        warnings.append("near_duplicate_source_ref")

    evidence_missing = sum(1 for row in rows if not str(row.get("evidence_hash") or "") and not str(row.get("source_ref") or ""))
    if rows and evidence_missing / len(rows) > 0.5:
        warnings.append("most_outcomes_lack_evidence_reference")

    profile = {
        "ok": True,
        "quality_ready": not blocking,
        "min_total": int(min_total),
        "eligible_total": eligible_total,
        "blocking_reasons": sorted(set(blocking)),
        "warnings": sorted(set(warnings)),
        "source_counts": source_counts,
        "event_kind_counts": event_kind_counts,
        "score_distribution": _score_distribution(rows),
        "evidence_hash_present": sum(1 for row in rows if str(row.get("evidence_hash") or "")),
        "source_ref_present": sum(1 for row in rows if str(row.get("source_ref") or "")),
        "redacted_count": sum(1 for row in rows if row.get("redacted") is True),
        "duplicate_outcome_ids": duplicate_ids,
        "near_duplicate_source_refs": duplicate_refs,
    }
    profile["quality_hash"] = hash_obj(_canonical_quality(profile))
    return profile


def _canonical_quality(profile: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "quality_ready": bool(profile.get("quality_ready")),
        "min_total": int(profile.get("min_total", 0) or 0),
        "eligible_total": int(profile.get("eligible_total", 0) or 0),
        "blocking_reasons": list(profile.get("blocking_reasons") or []),
        "warnings": list(profile.get("warnings") or []),
        "source_counts": {str(k): int(v) for k, v in dict(profile.get("source_counts") or {}).items()},
        "event_kind_counts": {str(k): int(v) for k, v in dict(profile.get("event_kind_counts") or {}).items()},
    }


def fail_for_quality(profile: Mapping[str, Any]) -> dict[str, Any]:
    if "insufficient_real_outcomes" in set(profile.get("blocking_reasons") or []):
        return err(
            "insufficient_real_outcomes",
            "not enough eligible outcomes for real_redacted replay",
            quality=profile,
            eligible_count=int(profile.get("eligible_total", 0) or 0),
            min_required=int(profile.get("min_total", 20) or 20),
            replay_source="real_redacted",
        )
    return err(
        "replay_quality_not_ready",
        "real_redacted replay quality profile is not ready",
        quality=profile,
        blocking_reasons=list(profile.get("blocking_reasons") or []),
        replay_source="real_redacted",
    )
