"""Beacon Profile bundle validation and recognition classification.

Beacon Profile is inter-entity recognition. It is intentionally separate from
the legacy KG/activity beacons route and does not require raw memory disclosure.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4


SCHEMA_VERSION = "beacon-0.1"


class AssuranceClass(str, Enum):
    CLASS0_UNKNOWN = "class0"
    CLASS1_TOOL_ORACLE_COMPONENT = "class1"
    CLASS2_PROVISIONAL_ENTITY = "class2"
    CLASS3_VERIFIED_ENTITY = "class3"
    UNVERIFIED = "unverified"


class PrivilegeContinuity(str, Enum):
    STABLE = "stable"
    LIMITED = "limited"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class BeaconIssuer:
    entity_id: str
    key_id: str
    role: str = "ENTITY"


@dataclass(frozen=True)
class IdentityLineage:
    lineage_id: str
    rotation_declared: bool
    provider_independent: bool
    anchor_cosign_present: bool = False


@dataclass(frozen=True)
class ContinuityWindow:
    start_at: str
    end_at: str


@dataclass(frozen=True)
class ContinuityEvidence:
    continuity_window: ContinuityWindow | None = None
    memory_bound: bool = False
    privilege_continuity: PrivilegeContinuity = PrivilegeContinuity.UNKNOWN
    behavior_markers: tuple[str, ...] = ()
    drift_declared: bool = False
    uncertainty_markers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChallengePolicy:
    challengeable: bool
    witness_refs: tuple[str, ...] = ()
    window_policy: str = "bounded"
    arbiter_policy_ref: str | None = None


@dataclass(frozen=True)
class PrivacyPolicy:
    raw_memory_disclosed: bool = False
    evidence_mode: str = "hashes_and_bounded_summaries"
    selective_disclosure: bool = True


@dataclass(frozen=True)
class ReceiverVerification:
    assurance_class_verified_by_receiver: AssuranceClass = AssuranceClass.UNVERIFIED
    receiver_id: str = ""
    verified_at: str = ""


@dataclass(frozen=True)
class BeaconBundle:
    beacon_id: str
    issued_at: str
    assurance_class_claimed: AssuranceClass
    issuer: BeaconIssuer
    identity: IdentityLineage
    continuity: ContinuityEvidence
    challenge: ChallengePolicy
    privacy: PrivacyPolicy
    hash_alg: str
    sig_alg: str
    payload_hash: str
    record_sig: str
    receiver: ReceiverVerification = field(default_factory=ReceiverVerification)
    schema_version: str = SCHEMA_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SlotAVerdict:
    ok: bool
    max_class: AssuranceClass
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SlotBVerdict:
    ok: bool
    max_class: AssuranceClass
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class BeaconDecision:
    decision_id: str
    created_at: str
    beacon_id: str
    claimed_class: AssuranceClass
    verified_class: AssuranceClass
    slot_a: SlotAVerdict
    slot_b: SlotBVerdict
    reason_codes: tuple[str, ...] = ()
    privileges: tuple[str, ...] = ()
    raw_memory_disclosure_accepted: bool = False


class BeaconValidationError(ValueError):
    def __init__(self, reason_codes: Iterable[str]) -> None:
        self.reason_codes = tuple(reason_codes)
        super().__init__("; ".join(self.reason_codes))


class BeaconProfileStore:
    """Explicit-root store for Beacon Profile bundles and decisions."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.base_dir = self.root / "beacon_profile"
        self.bundles_dir = self.base_dir / "bundles"
        self.decisions_path = self.base_dir / "decisions.jsonl"
        self.manifest_path = self.base_dir / "manifest.json"

    def ensure_dirs(self) -> None:
        self.bundles_dir.mkdir(parents=True, exist_ok=True)
        self.write_manifest()

    def manifest(self) -> dict[str, Any]:
        return {
            "schema": "ester.beacon_profile.store.v1",
            "purpose": "inter_entity_recognition_sidecar",
            "bundles": str(self.bundles_dir),
            "decisions": str(self.decisions_path),
            "kg_activity_beacons": False,
            "raw_memory_required": False,
        }

    def write_manifest(self) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        _write_json(self.manifest_path, self.manifest())
        return self.manifest_path

    def save_bundle(self, bundle: BeaconBundle) -> Path:
        self.ensure_dirs()
        target = self.bundles_dir / f"{_safe_file_id(bundle.beacon_id)}.json"
        _write_json(target, to_record(bundle))
        return target

    def append_decision(self, decision: BeaconDecision) -> Path:
        self.ensure_dirs()
        with self.decisions_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(to_record(decision), ensure_ascii=False, sort_keys=True) + "\n")
        return self.decisions_path

    def load_bundle(self, beacon_id: str) -> dict[str, Any] | None:
        path = self.bundles_dir / f"{_safe_file_id(beacon_id)}.json"
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None

    def load_decisions(self) -> list[dict[str, Any]]:
        if not self.decisions_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.decisions_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
        return rows


def classify_beacon_bundle(
    bundle: BeaconBundle,
    *,
    decision_id: str | None = None,
    created_at: str | None = None,
) -> BeaconDecision:
    slot_a = _slot_a(bundle)
    slot_b = _slot_b(bundle)
    verified_class = _verified_class(bundle, slot_a, slot_b)
    reasons = tuple(dict.fromkeys((*slot_a.reason_codes, *slot_b.reason_codes)))
    return BeaconDecision(
        decision_id=decision_id or f"beacon-decision:{uuid4().hex}",
        created_at=created_at or _now_iso(),
        beacon_id=bundle.beacon_id,
        claimed_class=bundle.assurance_class_claimed,
        verified_class=verified_class,
        slot_a=slot_a,
        slot_b=slot_b,
        reason_codes=reasons,
        privileges=_privileges_for(verified_class),
        raw_memory_disclosure_accepted=False,
    )


def validate_beacon_bundle(bundle: BeaconBundle) -> tuple[str, ...]:
    return classify_beacon_bundle(bundle).reason_codes


def to_record(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: to_record(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): to_record(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_record(item) for item in value]
    return value


def _slot_a(bundle: BeaconBundle) -> SlotAVerdict:
    reasons: list[str] = []
    if bundle.schema_version != SCHEMA_VERSION:
        reasons.append("BEACON_SCHEMA_INVALID")
    if not str(bundle.beacon_id or "").strip():
        reasons.append("BEACON_ID_REQUIRED")
    if not str(bundle.issuer.entity_id or "").strip():
        reasons.append("BEACON_ISSUER_REQUIRED")
    if not str(bundle.issuer.key_id or "").strip():
        reasons.append("BEACON_KEY_REQUIRED")
    if not str(bundle.identity.lineage_id or "").strip():
        reasons.append("BEACON_LINEAGE_REQUIRED")
    if not bundle.identity.provider_independent:
        reasons.append("BEACON_PROVIDER_INDEPENDENCE_REQUIRED")
    if not str(bundle.hash_alg or "").strip():
        reasons.append("BEACON_HASH_ALG_REQUIRED")
    if not str(bundle.sig_alg or "").strip():
        reasons.append("BEACON_SIG_ALG_REQUIRED")
    if not str(bundle.payload_hash or "").strip():
        reasons.append("BEACON_PAYLOAD_HASH_REQUIRED")
    if not str(bundle.record_sig or "").strip():
        reasons.append("BEACON_RECORD_SIG_REQUIRED")
    if bundle.privacy.raw_memory_disclosed:
        reasons.append("BEACON_RAW_MEMORY_DISCLOSED")
    if bundle.assurance_class_claimed == AssuranceClass.CLASS3_VERIFIED_ENTITY:
        if not bundle.challenge.challengeable:
            reasons.append("BEACON_CHALLENGE_REQUIRED")
        if not bundle.challenge.witness_refs:
            reasons.append("BEACON_WITNESS_REQUIRED")
    if reasons:
        return SlotAVerdict(False, AssuranceClass.CLASS0_UNKNOWN, tuple(reasons))
    if bundle.assurance_class_claimed == AssuranceClass.CLASS1_TOOL_ORACLE_COMPONENT:
        return SlotAVerdict(True, AssuranceClass.CLASS1_TOOL_ORACLE_COMPONENT, ())
    if bundle.challenge.challengeable and bundle.challenge.witness_refs:
        return SlotAVerdict(True, AssuranceClass.CLASS2_PROVISIONAL_ENTITY, ())
    return SlotAVerdict(True, AssuranceClass.CLASS2_PROVISIONAL_ENTITY, ("BEACON_CHALLENGE_INCOMPLETE",))


def _slot_b(bundle: BeaconBundle) -> SlotBVerdict:
    reasons: list[str] = []
    continuity = bundle.continuity
    if continuity.continuity_window is None:
        reasons.append("BEACON_CONTINUITY_WINDOW_REQUIRED")
    if not continuity.memory_bound:
        reasons.append("BEACON_MEMORY_BOUND_REQUIRED")
    if continuity.privilege_continuity == PrivilegeContinuity.UNKNOWN:
        reasons.append("BEACON_PRIVILEGE_CONTINUITY_UNKNOWN")
    if not continuity.behavior_markers:
        reasons.append("BEACON_BEHAVIOR_MARKERS_REQUIRED")
    if continuity.drift_declared:
        reasons.append("BEACON_DRIFT_DECLARED")
    if continuity.uncertainty_markers:
        reasons.append("BEACON_UNCERTAINTY_MARKED")
    if reasons:
        return SlotBVerdict(False, AssuranceClass.CLASS2_PROVISIONAL_ENTITY, tuple(reasons))
    return SlotBVerdict(True, AssuranceClass.CLASS3_VERIFIED_ENTITY, ())


def _verified_class(
    bundle: BeaconBundle,
    slot_a: SlotAVerdict,
    slot_b: SlotBVerdict,
) -> AssuranceClass:
    if not slot_a.ok:
        return AssuranceClass.CLASS0_UNKNOWN
    if bundle.assurance_class_claimed == AssuranceClass.CLASS1_TOOL_ORACLE_COMPONENT:
        return AssuranceClass.CLASS1_TOOL_ORACLE_COMPONENT
    if slot_b.ok and slot_a.max_class == AssuranceClass.CLASS2_PROVISIONAL_ENTITY:
        return AssuranceClass.CLASS3_VERIFIED_ENTITY
    return slot_a.max_class


def _privileges_for(assurance_class: AssuranceClass) -> tuple[str, ...]:
    if assurance_class == AssuranceClass.CLASS3_VERIFIED_ENTITY:
        return (
            "higher_trust_coordination",
            "bounded_delegation",
            "challenge_bearing_responsibility",
        )
    if assurance_class == AssuranceClass.CLASS2_PROVISIONAL_ENTITY:
        return ("limited_trust_interaction", "constrained_privilege")
    if assurance_class == AssuranceClass.CLASS1_TOOL_ORACLE_COMPONENT:
        return ("tool_use", "oracle_query")
    return ("record_only",)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _safe_file_id(value: str) -> str:
    safe = []
    for char in value:
        if char.isalnum() or char in ("-", "_", "."):
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe).strip("._") or "beacon"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
