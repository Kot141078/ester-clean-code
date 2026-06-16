# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from growth_engine import GrowthWitnessLedger
from growth_engine.common import err, ok

from .config import status as config_status
from .outcomes import _write_fitness_report, build_outcome_record, record_outcome, utc_now
from .quality import outcome_stats, replay_quality_profile
from .redaction import redacted_note
from .state import ensure_layout, read_jsonl, state_paths

OUTCOME_CANDIDATE_SCHEMA = "ester.srlm.outcome_candidate.v1"

ALLOWED_AUTO_EVENT_KINDS = {
    "l4": {
        "l4.gate.correctly_blocked",
        "l4.fail_closed.triggered",
        "l4.witness.complete",
        "l4.witness.incomplete",
    },
    "reality": {
        "reality.tool.success",
        "reality.tool.failure",
        "reality.timeout",
        "reality.exception",
    },
    "human": {
        "human.answer.accepted",
        "human.answer.corrected",
        "human.task.confirmed",
    },
}

_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,96}$")


def candidate_events(root: str | None = None) -> list[dict[str, Any]]:
    return read_jsonl(state_paths(root)["outcome_candidates"], limit=0)


def _latest_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        candidate_id = str(row.get("candidate_id") or "")
        if candidate_id:
            latest[candidate_id] = dict(row)
    return latest


def candidate_by_id(root: str | None, candidate_id: str) -> dict[str, Any] | None:
    return _latest_by_id(candidate_events(root)).get(str(candidate_id or ""))


def _counts(rows: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "") for row in rows if str(row.get(key) or "")).items()))


def _parse_created_at(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _safe_id(value: Any) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return ok(value="cand_" + uuid4().hex)
    if not _ID_RE.match(text):
        return err("SRLM_CANDIDATE_ID_INVALID", "candidate_id must be a short safe identifier")
    return ok(value=text)


def _truthy(value: Any, default: bool = True) -> bool:
    if value is None:
        return bool(default)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _candidate_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload or {})
    return {
        "source": data.get("proposed_source", data.get("source", "")),
        "event_kind": data.get("event_kind", data.get("kind", "")),
        "score": data.get("proposed_score", data.get("score", 0.0)),
        "uncertainty": data.get("proposed_uncertainty", data.get("uncertainty", 0.0)),
        "source_ref": data.get("source_ref", ""),
        "notes": data.get("notes", data.get("note", "")),
    }


def build_candidate_record(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload or {})
    redacted = _truthy(data.get("redacted"), True)
    if redacted is not True:
        return err("SRLM_CANDIDATE_NOT_REDACTED", "candidate must be redacted before proposal")
    candidate_id = _safe_id(data.get("candidate_id"))
    if not candidate_id.get("ok"):
        return candidate_id
    reason = redacted_note(data.get("reason", "bounded runtime event may represent a fitness outcome"))
    if not reason.get("ok"):
        return reason
    built = build_outcome_record(_candidate_payload(data))
    if not built.get("ok"):
        return built
    record = dict(built["record"])
    return ok(
        record={
            "schema": OUTCOME_CANDIDATE_SCHEMA,
            "candidate_id": candidate_id["value"],
            "created_at": str(data.get("created_at") or utc_now()),
            "proposed_source": record["source"],
            "event_kind": record["event_kind"],
            "proposed_score": float(record["score"]),
            "proposed_uncertainty": float(record["uncertainty"]),
            "source_ref": record["source_ref"],
            "evidence_hash": record["evidence_hash"],
            "redacted": True,
            "notes": record["notes"],
            "reason": reason["text"],
            "status": "pending",
            "accepted_outcome_id": "",
            "reviewed_by": "",
            "reviewed_at": "",
            "review_note": "",
            "auto_execute": False,
            "auto_ingest": False,
            "memory": "off",
        }
    )


def append_candidate_event(row: Mapping[str, Any], *, root: str | None = None) -> str:
    paths = ensure_layout(root)
    path = paths["outcome_candidates"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        import json

        f.write(json.dumps(dict(row), ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n")
    return str(path)


def _safe_candidate(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": row.get("schema", ""),
        "candidate_id": row.get("candidate_id", ""),
        "created_at": row.get("created_at", ""),
        "proposed_source": row.get("proposed_source", ""),
        "event_kind": row.get("event_kind", ""),
        "proposed_score": row.get("proposed_score", 0.0),
        "proposed_uncertainty": row.get("proposed_uncertainty", 0.0),
        "source_ref": row.get("source_ref", ""),
        "evidence_hash": row.get("evidence_hash", ""),
        "redacted": row.get("redacted") is True,
        "notes": row.get("notes", ""),
        "reason": row.get("reason", ""),
        "status": row.get("status", ""),
        "accepted_outcome_id": row.get("accepted_outcome_id", ""),
        "reviewed_by": row.get("reviewed_by", ""),
        "reviewed_at": row.get("reviewed_at", ""),
        "review_note": row.get("review_note", ""),
        "auto_execute": row.get("auto_execute") is True,
        "auto_ingest": row.get("auto_ingest") is True,
        "memory": row.get("memory", ""),
    }


def list_candidates(
    *,
    root: str | None = None,
    limit: int = 50,
    offset: int = 0,
    status: str = "",
) -> dict[str, Any]:
    latest = list(_latest_by_id(candidate_events(root)).values())
    if status:
        latest = [row for row in latest if str(row.get("status") or "") == status]
    latest.sort(key=lambda row: str(row.get("created_at") or ""))
    start = max(0, int(offset))
    count = max(1, min(200, int(limit)))
    return ok(
        total=len(latest),
        events_total=len(candidate_events(root)),
        limit=count,
        offset=start,
        candidates=[_safe_candidate(row) for row in latest[start : start + count]],
    )


def candidate_stats(*, root: str | None = None) -> dict[str, Any]:
    events = candidate_events(root)
    latest = list(_latest_by_id(events).values())
    pending = [row for row in latest if row.get("status") == "pending"]
    now = datetime.now(timezone.utc)
    ages = []
    for row in pending:
        created = _parse_created_at(row.get("created_at"))
        if created is not None:
            ages.append(max(0, int((now - created).total_seconds())))
    status_counts = _counts(latest, "status")
    warnings: list[str] = []
    if len(pending) >= 20:
        warnings.append("candidate_queue_needs_review")
    if ages and max(ages) >= 86400:
        warnings.append("old_pending_candidates")
    return ok(
        candidate_path=str(state_paths(root)["outcome_candidates"]),
        total_events=len(events),
        total_candidates=len(latest),
        pending_count=int(status_counts.get("pending", 0)),
        accepted_count=int(status_counts.get("accepted", 0)),
        rejected_count=int(status_counts.get("rejected", 0)),
        expired_count=int(status_counts.get("expired", 0)),
        status_counts=status_counts,
        source_counts=_counts(latest, "proposed_source"),
        event_kind_counts=_counts(latest, "event_kind"),
        oldest_pending_age_seconds=max(ages) if ages else 0,
        warnings=warnings,
    )


def _write_candidate_report(root: str | None = None) -> str:
    paths = ensure_layout(root)
    stats = candidate_stats(root=str(paths["root"]))
    fitness = outcome_stats(root=str(paths["root"]))
    quality = replay_quality_profile(root=str(paths["root"]))
    cfg = config_status()
    candidate_warning = ",".join(stats.get("warnings") or [])
    source_counts = dict(fitness.get("source_counts") or {})
    event_counts = dict(fitness.get("event_kind_counts") or {})
    diversity_warning = ""
    if int(fitness.get("total_outcomes", 0) or 0) and (len(source_counts) <= 1 or len(event_counts) <= 1):
        diversity_warning = "accepted_outcomes_low_diversity"
    path = paths["reports"] / "latest_outcome_candidate_report.md"
    lines = [
        "# SRLM outcome candidate report",
        "",
        f"updated_at: {utc_now()}",
        f"accepted_outcomes_total: {fitness.get('total_outcomes', 0)}",
        f"pending_candidate_count: {stats.get('pending_count', 0)}",
        f"accepted_candidate_count: {stats.get('accepted_count', 0)}",
        f"rejected_candidate_count: {stats.get('rejected_count', 0)}",
        f"expired_candidate_count: {stats.get('expired_count', 0)}",
        f"oldest_pending_age_seconds: {stats.get('oldest_pending_age_seconds', 0)}",
        f"replay_quality_ready: {quality.get('quality_ready')}",
        f"quality_blocking_reasons: {','.join(quality.get('blocking_reasons') or [])}",
        f"candidate_warning: {candidate_warning}",
        f"diversity_warning: {diversity_warning}",
        f"promotion_gate_open: {cfg.get('gates', {}).get('promotion_gate_open')}",
        f"shadow_only: {cfg.get('limits', {}).get('shadow_only')}",
        f"canary_enable: {cfg.get('limits', {}).get('canary_enable')}",
        "",
        "candidate_counts_by_status:",
    ]
    lines.extend(f"- {key}: {value}" for key, value in dict(stats.get("status_counts") or {}).items())
    lines.append("")
    lines.append("candidate_counts_by_source:")
    lines.extend(f"- {key}: {value}" for key, value in dict(stats.get("source_counts") or {}).items())
    lines.append("")
    lines.append("candidate_counts_by_event_kind:")
    lines.extend(f"- {key}: {value}" for key, value in dict(stats.get("event_kind_counts") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def propose_candidate(payload: Mapping[str, Any], *, root: str | None = None) -> dict[str, Any]:
    paths = ensure_layout(root)
    built = build_candidate_record(payload)
    if not built.get("ok"):
        return built
    record = dict(built["record"])
    existing = candidate_by_id(str(paths["root"]), str(record["candidate_id"]))
    if existing is not None:
        report_path = _write_candidate_report(str(paths["root"]))
        _write_fitness_report(str(paths["root"]))
        return ok(
            candidate=_safe_candidate(existing),
            duplicate=True,
            idempotent=True,
            path=str(paths["outcome_candidates"]),
            report_path=report_path,
        )
    path = append_candidate_event(record, root=str(paths["root"]))
    report_path = _write_candidate_report(str(paths["root"]))
    _write_fitness_report(str(paths["root"]))
    return ok(candidate=_safe_candidate(record), path=path, report_path=report_path, duplicate=False, idempotent=False)


def auto_propose_candidate(payload: Mapping[str, Any], *, root: str | None = None) -> dict[str, Any]:
    data = dict(payload or {})
    event_kind = str(data.get("event_kind", data.get("kind", "")) or "").strip().lower()
    source = str(data.get("proposed_source", data.get("source", "")) or "").strip().lower()
    if not source and "." in event_kind:
        source = event_kind.split(".", 1)[0]
    if event_kind not in ALLOWED_AUTO_EVENT_KINDS.get(source, set()):
        return err("SRLM_AUTO_CANDIDATE_EVENT_NOT_ALLOWED", f"auto candidate event not allowed:{event_kind}")
    data["source"] = source
    data["event_kind"] = event_kind
    data.setdefault("reason", "safe bounded auto-candidate event requires operator review")
    return propose_candidate(data, root=root)


def _review_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload or {})
    candidate_id = str(data.get("candidate_id") or "").strip()
    reviewed_by = str(data.get("reviewed_by") or "").strip()
    review_note = redacted_note(data.get("review_note", data.get("note", "")))
    if not candidate_id:
        return err("SRLM_CANDIDATE_ID_REQUIRED", "candidate_id is required")
    if not reviewed_by:
        return err("SRLM_REVIEWER_REQUIRED", "reviewed_by is required")
    if not review_note.get("ok"):
        return review_note
    if not str(review_note.get("text") or "").strip():
        return err("SRLM_REVIEW_NOTE_REQUIRED", "review note is required")
    return ok(candidate_id=candidate_id, reviewed_by=reviewed_by[:80], review_note=review_note["text"])


def _append_review_witness(root: str, row: Mapping[str, Any]) -> dict[str, Any]:
    witness = GrowthWitnessLedger(str(state_paths(root)["root"]))
    event_type = "rejected" if str(row.get("status") or "") == "rejected" else "candidate_proposed"
    return witness.append(
        event_type,
        {
            "candidate_id": str(row.get("candidate_id") or ""),
            "status": str(row.get("status") or ""),
            "accepted_outcome_id": str(row.get("accepted_outcome_id") or ""),
            "proposed_source": str(row.get("proposed_source") or ""),
            "event_kind": str(row.get("event_kind") or ""),
            "reviewed_by": str(row.get("reviewed_by") or ""),
            "auto_execute": False,
            "auto_ingest": False,
            "memory": "off",
        },
    )


def accept_candidate(payload: Mapping[str, Any], *, root: str | None = None) -> dict[str, Any]:
    paths = ensure_layout(root)
    review = _review_payload(payload)
    if not review.get("ok"):
        return review
    candidate_id = str(review["candidate_id"])
    candidate = candidate_by_id(str(paths["root"]), candidate_id)
    if candidate is None:
        return err("SRLM_CANDIDATE_NOT_FOUND", "candidate_id was not found")
    if candidate.get("status") == "accepted":
        report_path = _write_candidate_report(str(paths["root"]))
        _write_fitness_report(str(paths["root"]))
        return ok(candidate=_safe_candidate(candidate), duplicate=True, idempotent=True, report_path=report_path)
    if candidate.get("status") != "pending":
        return err("SRLM_CANDIDATE_NOT_PENDING", f"candidate is not pending:{candidate.get('status')}")

    outcome_id = str((payload or {}).get("accepted_outcome_id") or (payload or {}).get("outcome_id") or f"out_{candidate_id}")
    outcome_payload = {
        "outcome_id": outcome_id,
        "source": candidate.get("proposed_source"),
        "event_kind": candidate.get("event_kind"),
        "score": candidate.get("proposed_score"),
        "uncertainty": candidate.get("proposed_uncertainty"),
        "source_ref": candidate.get("source_ref"),
        "notes": candidate.get("notes"),
        "evidence_hash": candidate.get("evidence_hash"),
    }
    recorded = record_outcome(outcome_payload, root=str(paths["root"]))
    if not recorded.get("ok"):
        return recorded
    accepted = dict(candidate)
    accepted.update(
        {
            "status": "accepted",
            "accepted_outcome_id": str((recorded.get("recorded") or {}).get("outcome_id") or outcome_id),
            "reviewed_by": str(review["reviewed_by"]),
            "reviewed_at": utc_now(),
            "review_note": str(review["review_note"]),
            "auto_execute": False,
            "auto_ingest": False,
            "memory": "off",
        }
    )
    path = append_candidate_event(accepted, root=str(paths["root"]))
    witness = _append_review_witness(str(paths["root"]), accepted)
    report_path = _write_candidate_report(str(paths["root"]))
    _write_fitness_report(str(paths["root"]))
    return ok(
        candidate=_safe_candidate(accepted),
        recorded=recorded.get("recorded"),
        outcome_duplicate=recorded.get("duplicate", False),
        witness=witness,
        path=path,
        report_path=report_path,
    )


def reject_candidate(payload: Mapping[str, Any], *, root: str | None = None) -> dict[str, Any]:
    paths = ensure_layout(root)
    review = _review_payload(payload)
    if not review.get("ok"):
        return review
    candidate_id = str(review["candidate_id"])
    candidate = candidate_by_id(str(paths["root"]), candidate_id)
    if candidate is None:
        return err("SRLM_CANDIDATE_NOT_FOUND", "candidate_id was not found")
    if candidate.get("status") == "rejected":
        report_path = _write_candidate_report(str(paths["root"]))
        _write_fitness_report(str(paths["root"]))
        return ok(candidate=_safe_candidate(candidate), duplicate=True, idempotent=True, report_path=report_path)
    if candidate.get("status") != "pending":
        return err("SRLM_CANDIDATE_NOT_PENDING", f"candidate is not pending:{candidate.get('status')}")
    rejected = dict(candidate)
    rejected.update(
        {
            "status": "rejected",
            "accepted_outcome_id": "",
            "reviewed_by": str(review["reviewed_by"]),
            "reviewed_at": utc_now(),
            "review_note": str(review["review_note"]),
            "auto_execute": False,
            "auto_ingest": False,
            "memory": "off",
        }
    )
    path = append_candidate_event(rejected, root=str(paths["root"]))
    witness = _append_review_witness(str(paths["root"]), rejected)
    report_path = _write_candidate_report(str(paths["root"]))
    _write_fitness_report(str(paths["root"]))
    return ok(candidate=_safe_candidate(rejected), witness=witness, path=path, report_path=report_path)
