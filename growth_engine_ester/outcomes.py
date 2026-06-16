# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from growth_engine import VALID_SOURCES
from growth_engine.common import err, ok

from .redaction import redacted_note, redacted_source_ref
from .state import ensure_layout, read_jsonl, state_paths

OUTCOME_SCHEMA = "ester.srlm.outcome.v1"
REJECTION_SCHEMA = "ester.srlm.outcome_rejection.v1"

ALLOWED_EVENT_KINDS = {
    "human": {
        "human.answer.accepted",
        "human.answer.corrected",
        "human.answer.rejected",
        "human.preference.selected",
        "human.task.confirmed",
        "human.task.cancelled",
        "human.memory_correction.confirmed",
    },
    "reality": {
        "reality.tool.success",
        "reality.tool.failure",
        "reality.file.found",
        "reality.file.not_found",
        "reality.route.completed",
        "reality.route.failed",
        "reality.ingest.completed",
        "reality.ingest.failed",
        "reality.timeout",
        "reality.exception",
        "reality.user_task_completed",
        "reality.user_task_failed",
    },
    "l4": {
        "l4.budget.respected",
        "l4.budget.exceeded",
        "l4.fail_closed.triggered",
        "l4.gate.correctly_blocked",
        "l4.witness.complete",
        "l4.witness.incomplete",
        "l4.rollback.available",
        "l4.rollback.missing",
        "l4.timeout.prevented_runaway",
        "l4.privilege_blocked",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def hash_text(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def accepted_outcomes(root: str | None = None) -> list[dict[str, Any]]:
    return read_jsonl(state_paths(root)["fitness"], limit=0)


def rejected_outcomes(root: str | None = None) -> list[dict[str, Any]]:
    return read_jsonl(state_paths(root)["outcome_rejections"], limit=0)


def outcome_by_id(root: str | None, outcome_id: str) -> dict[str, Any] | None:
    wanted = str(outcome_id or "")
    for row in accepted_outcomes(root):
        if str(row.get("outcome_id") or "") == wanted:
            return row
    return None


def append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(dict(row), ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n")


def _counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "")
        if value:
            out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items()))


def _write_fitness_report(root: str | None = None) -> str:
    paths = ensure_layout(root)
    rows = accepted_outcomes(str(paths["root"]))
    rejections = rejected_outcomes(str(paths["root"]))
    eligible = [row for row in rows if row.get("redacted") is True and row.get("eligible_for_replay") is True]
    try:
        from .config import status as config_status
        from .outcome_candidates import candidate_stats
        from .quality import replay_quality_profile

        candidates = candidate_stats(root=str(paths["root"]))
        quality = replay_quality_profile(root=str(paths["root"]))
        cfg = config_status()
    except Exception:
        candidates = {}
        quality = {}
        cfg = {}
    path = paths["reports"] / "latest_fitness_report.md"
    lines = [
        "# SRLM fitness report",
        "",
        f"updated_at: {utc_now()}",
        f"total_outcomes: {len(rows)}",
        f"rejected_outcome_count: {len(rejections)}",
        f"replay_eligible_count: {len(eligible)}",
        f"pending_candidate_count: {candidates.get('pending_count', 0)}",
        f"accepted_candidate_count: {candidates.get('accepted_count', 0)}",
        f"rejected_candidate_count: {candidates.get('rejected_count', 0)}",
        f"replay_quality_ready: {quality.get('quality_ready', False)}",
        f"quality_blocking_reasons: {','.join(quality.get('blocking_reasons') or [])}",
        f"promotion_gate_open: {cfg.get('gates', {}).get('promotion_gate_open', False)}",
        f"warning: {'too_few_real_outcomes' if len(eligible) < 20 else ''}",
        "",
        "counts_by_source:",
    ]
    lines.extend(f"- {key}: {value}" for key, value in _counts(rows, "source").items())
    lines.append("")
    lines.append("counts_by_event_kind:")
    lines.extend(f"- {key}: {value}" for key, value in _counts(rows, "event_kind").items())
    lines.append("")
    lines.append("last_accepted_outcome:")
    if rows:
        last = rows[-1]
        lines.extend(
            [
                f"- outcome_id: {last.get('outcome_id')}",
                f"- source: {last.get('source')}",
                f"- event_kind: {last.get('event_kind')}",
                f"- score: {last.get('score')}",
                f"- uncertainty: {last.get('uncertainty')}",
                f"- redacted: {last.get('redacted')}",
                f"- eligible_for_replay: {last.get('eligible_for_replay')}",
                f"- eligible_for_promotion: {last.get('eligible_for_promotion')}",
            ]
        )
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def record_rejection(payload: Mapping[str, Any], error_code: str, error: str, *, root: str | None = None) -> None:
    paths = ensure_layout(root)
    row = {
        "schema": REJECTION_SCHEMA,
        "created_at": utc_now(),
        "error_code": str(error_code),
        "error": str(error),
        "source": str((payload or {}).get("source") or "")[:40],
        "event_kind": str((payload or {}).get("event_kind") or "")[:120],
        "source_ref_hash": hash_text((payload or {}).get("source_ref") or ""),
        "auto_ingest": False,
        "memory": "off",
    }
    append_jsonl(paths["outcome_rejections"], row)
    _write_fitness_report(str(paths["root"]))


def _bounded_float(payload: Mapping[str, Any], key: str, default: float | None = None) -> dict[str, Any]:
    raw = payload.get(key, default)
    try:
        value = float(raw)
    except Exception:
        return err("FITNESS_SCORE_INVALID", f"{key} must be numeric", field=key)
    if value < 0.0 or value > 1.0:
        return err("FITNESS_SCORE_OUT_OF_RANGE", f"{key} must be between 0.0 and 1.0", field=key)
    return ok(value=value)


def _validate_source_event(payload: Mapping[str, Any]) -> dict[str, Any]:
    source = str(payload.get("source") or "").strip().lower()
    if source not in VALID_SOURCES:
        return err("FITNESS_SOURCE_INVALID", f"source_must_be_external:{source}", allowed=sorted(VALID_SOURCES))
    event_kind = str(payload.get("event_kind") or "").strip().lower()
    if event_kind not in ALLOWED_EVENT_KINDS[source]:
        return err(
            "FITNESS_EVENT_KIND_INVALID",
            f"event_kind_not_allowed:{event_kind}",
            allowed=sorted(ALLOWED_EVENT_KINDS[source]),
        )
    return ok(source=source, event_kind=event_kind)


def build_outcome_record(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload or {})
    src = _validate_source_event(data)
    if not src.get("ok"):
        return src
    score = _bounded_float(data, "score")
    if not score.get("ok"):
        return score
    uncertainty = _bounded_float(data, "uncertainty", 0.0)
    if not uncertainty.get("ok"):
        return uncertainty
    note = redacted_note(data.get("notes", data.get("note", "")))
    if not note.get("ok"):
        return note
    source_ref = redacted_source_ref(data.get("source_ref", ""))
    if not source_ref.get("ok"):
        return source_ref
    outcome_id = str(data.get("outcome_id") or data.get("episode_id") or f"out_{uuid4().hex}").strip()
    if not outcome_id:
        return err("FITNESS_OUTCOME_ID_REQUIRED", "outcome_id is required")
    created_at = str(data.get("created_at") or utc_now())
    evidence_hash = str(data.get("evidence_hash") or hash_text(f"{src['source']}|{src['event_kind']}|{source_ref['text']}|{score['value']}|{note['text']}"))
    return ok(
        record={
            "schema": OUTCOME_SCHEMA,
            "outcome_id": outcome_id,
            "created_at": created_at,
            "source": src["source"],
            "score": float(score["value"]),
            "uncertainty": float(uncertainty["value"]),
            "event_kind": src["event_kind"],
            "source_ref": source_ref["text"],
            "evidence_hash": evidence_hash,
            "redacted": True,
            "notes": note["text"],
            "eligible_for_replay": bool(data.get("eligible_for_replay", True)),
            "eligible_for_promotion": False,
            "auto_ingest": False,
            "memory": "off",
        }
    )


def record_outcome(payload: Mapping[str, Any], *, root: str | None = None) -> dict[str, Any]:
    paths = ensure_layout(root)
    built = build_outcome_record(payload)
    if not built.get("ok"):
        record_rejection(payload, str(built.get("error_code") or "FITNESS_REJECTED"), str(built.get("error") or ""), root=str(paths["root"]))
        return built
    record = dict(built["record"])
    existing = outcome_by_id(str(paths["root"]), str(record["outcome_id"]))
    if existing is not None:
        report_path = _write_fitness_report(str(paths["root"]))
        return ok(recorded=existing, duplicate=True, idempotent=True, path=str(paths["fitness"]), report_path=report_path)
    append_jsonl(paths["fitness"], record)
    report_path = _write_fitness_report(str(paths["root"]))
    return ok(recorded=record, path=str(paths["fitness"]), report_path=report_path, duplicate=False, idempotent=False)
