"""Manual adapters from existing runtime signals into Glitch M1 contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .m1 import (
    CanonicalEvent,
    GlitchNode,
    GuardDecision,
    ResearchNode,
    RuntimeLockType,
    TimeWindow,
    WitnessRef,
    attach_collision_witness,
    derive_research_node,
    open_collision_challenge_window,
    register_runtime_collision,
)


@dataclass(frozen=True)
class AdapterResult:
    ok: bool
    decision: GuardDecision
    lock_type: RuntimeLockType | None
    glitch: GlitchNode | None = None
    research: ResearchNode | None = None
    events: tuple[CanonicalEvent, ...] = ()


def build_m1_bundle_from_quarantine_row(
    row: dict[str, Any],
    *,
    witness_id: str = "drift_quarantine",
    derive_research: bool = True,
    open_challenge: bool = True,
    occurred_at: str | None = None,
) -> AdapterResult:
    """Build a dry-run Glitch M1 bundle from an explicit quarantine row.

    This adapter intentionally accepts plain data instead of importing
    `modules.runtime.drift_quarantine`, so it cannot mutate live quarantine state.
    """

    if not bool(row.get("active")):
        return AdapterResult(
            ok=False,
            decision=GuardDecision.deny(
                "QUARANTINE_ROW_INACTIVE",
                "Only active quarantine rows can produce Glitch M1 collision bundles.",
            ),
            lock_type=None,
        )
    if not witness_id and (open_challenge or derive_research):
        return AdapterResult(
            ok=False,
            decision=GuardDecision.deny(
                "QUARANTINE_ADAPTER_WITNESS_REQUIRED",
                "Challenge and research derivation require an explicit witness.",
            ),
            lock_type=lock_type_from_quarantine_row(row),
        )

    collision_id = _collision_id(row)
    lock_type = lock_type_from_quarantine_row(row)
    glitch, events = register_runtime_collision(
        collision_id=collision_id,
        lock_type=lock_type,
        summary=_summary(row),
        occurred_at=occurred_at,
        metadata=_metadata(row),
    )
    out_events: tuple[CanonicalEvent, ...] = tuple(events)

    if witness_id:
        witness = WitnessRef(
            witness_id=witness_id,
            witness_kind="runtime_signal",
            signature_ref=str(row.get("event_id") or "") or None,
        )
        glitch, witness_event = attach_collision_witness(
            glitch,
            witness,
            evidence_id=f"evidence:{collision_id}",
            payload_hash=_payload_hash(row),
            details=_metadata(row),
            occurred_at=occurred_at,
        )
        out_events = (*out_events, witness_event)

    if open_challenge:
        glitch, challenge_event = open_collision_challenge_window(
            glitch,
            _challenge_window(row),
            occurred_at=occurred_at,
        )
        out_events = (*out_events, challenge_event)

    research: ResearchNode | None = None
    if derive_research:
        research, research_event = derive_research_node(
            glitch,
            summary=f"Quarantined research lane for {collision_id}",
            occurred_at=occurred_at,
            metadata=_metadata(row),
        )
        out_events = (*out_events, research_event)

    return AdapterResult(
        ok=True,
        decision=GuardDecision.allow(
            "QUARANTINE_ROW_ADAPTED",
            "Active quarantine row was adapted into a dry-run Glitch M1 bundle.",
            collision_id=collision_id,
        ),
        lock_type=lock_type,
        glitch=glitch,
        research=research,
        events=out_events,
    )


def lock_type_from_quarantine_row(row: dict[str, Any]) -> RuntimeLockType:
    text = " ".join(
        str(row.get(key) or "")
        for key in ("reason_code", "kind", "severity", "source", "template_id")
    ).upper()
    if any(marker in text for marker in ("PRIVILEGE", "AUTH", "RBAC", "PERMISSION")):
        return RuntimeLockType.PRIVILEGE_LOCK
    if "VOLITION" in text:
        return RuntimeLockType.VOLITION_LOCK
    if "CONSENT" in text:
        return RuntimeLockType.CONSENT_LOCK
    if any(marker in text for marker in ("TRUST", "TAMPER", "INTEGRITY", "SPEC_MISMATCH")):
        return RuntimeLockType.INTEGRITY_LOCK
    if "EVIDENCE" in text:
        return RuntimeLockType.EVIDENCE_LOCK
    if any(marker in text for marker in ("CONTINUITY", "DRIFT", "ALLOWLIST_CHANGED")):
        return RuntimeLockType.CONTINUITY_LOCK
    if "MAINTENANCE" in text:
        return RuntimeLockType.MAINTENANCE_LOCK
    return RuntimeLockType.CAUTION_LOCK


def _collision_id(row: dict[str, Any]) -> str:
    event_id = str(row.get("event_id") or "").strip()
    if event_id:
        return event_id
    parts = [
        str(row.get("agent_id") or "agent").strip() or "agent",
        str(row.get("kind") or "quarantine").strip() or "quarantine",
        str(row.get("reason_code") or "reason").strip() or "reason",
    ]
    return ":".join(parts)


def _summary(row: dict[str, Any]) -> str:
    agent_id = str(row.get("agent_id") or "").strip() or "unknown-agent"
    kind = str(row.get("kind") or "").strip() or "quarantine"
    reason = str(row.get("reason_code") or "").strip() or "unspecified"
    return f"Quarantine collision for {agent_id}: {kind}/{reason}"


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "agent_id",
        "kind",
        "severity",
        "reason_code",
        "template_id",
        "caps_hash",
        "computed_hash",
        "stored_hash",
        "added",
        "removed",
        "challenge_open_ts",
        "challenge_deadline_ts",
        "challenge_sec",
        "expired",
        "expired_ts",
        "source",
    )
    return {key: row.get(key) for key in keys if key in row}


def _payload_hash(row: dict[str, Any]) -> str | None:
    for key in ("computed_hash", "stored_hash", "caps_hash", "event_id"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return None


def _challenge_window(row: dict[str, Any]) -> TimeWindow:
    opened_at = _epoch_to_iso(row.get("challenge_open_ts")) or _epoch_to_iso(row.get("since_ts"))
    closes_at = _epoch_to_iso(row.get("challenge_deadline_ts"))
    return TimeWindow(opened_at=opened_at or _now_iso(), closes_at=closes_at)


def _epoch_to_iso(value: Any) -> str | None:
    try:
        ts = float(value)
    except Exception:
        return None
    if ts <= 0:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).replace(microsecond=0).isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
