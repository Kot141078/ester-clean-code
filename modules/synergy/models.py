# -*- coding: utf-8 -*-
"""modules/synergy/models.py - Kontrakty dannykh dlya Synergy (Pydantic).

MOSTY:
- (Yavnyy) Edinye modeli: Role/Capability/Agent/Policy/Override/Assignment*/Outcome/Telemetry/Risk.
- (Skrytyy #1) Sovmestimost: from_legacy(...) normalizuet starye dict'y STORE (id/kind/profile/bio/channels).
- (Skrytyy #2) Explainability: AssignmentPlan khranit trace shagov (opisanie + vklad v metriku).

ZEMNOY ABZATs:
Dannye stabilizirovany i samodokumentirovany: v API/khranilische gulyayut proverennye struktury,
kotorye legko validirovat, serializovat i podpisyvat.

# c=a+b"""
from __future__ import annotations

import datetime as dt
import uuid
from enum import Enum
from typing import Any, Dict, List, Literal, Mapping, Optional, Tuple

from pydantic import BaseModel, Field, PositiveInt, conlist, confloat, root_validator, validator
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# ===== Obschie tipy =====

def _uid() -> str:
    return uuid.uuid4().hex


class VersionedModel(BaseModel):
    model: str = Field(..., description="Imya modeli (tip)")
    version: str = Field("1.0", description="Schematic version of the model")
    uid: str = Field(default_factory=_uid, description="Lokalnyy UID obekta")
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc))
    updated_at: Optional[dt.datetime] = Field(
        default=None, description="Time of last update. Auto-fills when changes occur."
    )

    class Config:
        allow_mutation = True
        frozen = False
        validate_assignment = True


# ===== Capabilities / Roles =====

class RoleName(str, Enum):
    operator = "operator"
    strategist = "strategist"
    platform = "platform"
    communicator = "communicator"
    observer = "observer"
    mentor = "mentor"
    backup = "backup"
    qa = "qa"


class Capability(BaseModel):
    name: str = Field(..., description="Nazvanie sposobnosti (reaction/strategy/comms/...)")
    score: confloat(ge=0.0, le=1.0) = Field(..., description="Normalized estimate 00..1")


class Role(BaseModel):
    name: RoleName
    required: bool = False
    weight: confloat(ge=0.0, le=1.0) = 1.0


# ===== Agent =====

class AgentKind(str, Enum):
    human = "human"
    device = "device"


class HumanProfile(BaseModel):
    name: str = Field(..., min_length=1)
    age: PositiveInt = Field(..., ge=14, le=120)
    exp_years: int = Field(0, ge=0, le=80)
    domains: List[str] = Field(default_factory=list, description="Key Domains (Command/Drones/Tactics)")
    extras: Dict[str, Any] = Field(default_factory=dict)


class DeviceProfile(BaseModel):
    name: str = Field(..., min_length=1)
    device: str = Field(..., description="Tip ustroystva (drone/ugv/robot_arm/...)")
    flight_time_min: float = Field(0.0, ge=0.0, le=360.0)
    payload_g: float = Field(0.0, ge=0.0, le=50000.0)
    latency_ms: float = Field(0.0, ge=0.0, le=5000.0)
    extras: Dict[str, Any] = Field(default_factory=dict)


class Channels(BaseModel):
    whatsapp: Optional[str] = Field(None, description="MSISDN bez + ili s kodom strany")
    telegram: Optional[int] = Field(None, description="chat_id ili user_id")
    email: Optional[str] = None


class Agent(VersionedModel):
    model: str = "synergy.Agent"
    kind: AgentKind
    id: str = Field(..., description="Human/machine-readable ID")
    profile: HumanProfile | DeviceProfile
    bio: Optional[str] = Field(None, description="Short free biography/description")
    channels: Optional[Channels] = None
    capabilities: List[Capability] = Field(default_factory=list)

    @validator("capabilities", pre=True, always=True)
    def _cap_default(cls, v):
        return v or []

    @staticmethod
    def from_legacy(raw: Mapping[str, Any]) -> "Agent":
        """Converts the old STORE agent (id/kind/profile/bio/hannels) into a strict Agent."""
        kind = str(raw.get("kind") or "").strip().lower()
        prof = dict(raw.get("profile") or {})
        bio = raw.get("bio")
        ch = raw.get("channels") or {}

        if kind == "human":
            profile = HumanProfile(
                name=str(prof.get("name") or raw.get("id") or "Human"),
                age=int(prof.get("age") or 35),
                exp_years=int(prof.get("exp_years") or max(0, int(prof.get("age") or 35) - 20)),
                domains=[str(d) for d in (prof.get("domains") or [])],
                extras={k: v for k, v in prof.items() if k not in {"name", "age", "exp_years", "domains"}},
            )
        else:
            profile = DeviceProfile(
                name=str(prof.get("name") or raw.get("id") or "Device"),
                device=str(prof.get("device") or "unknown"),
                flight_time_min=float(prof.get("flight_time_min") or 0.0),
                payload_g=float(prof.get("payload_g") or 0.0),
                latency_ms=float(prof.get("latency_ms") or 0.0),
                extras={k: v for k, v in prof.items() if k not in {"name", "device", "flight_time_min", "payload_g", "latency_ms"}},
            )

        channels = None
        if ch:
            channels = Channels(
                whatsapp=ch.get("whatsapp"),
                telegram=ch.get("telegram"),
                email=ch.get("email"),
            )

        return Agent(
            kind=AgentKind(kind if kind in ("human", "device") else "human"),
            id=str(raw.get("id") or "unknown"),
            profile=profile,
            bio=str(bio) if bio else None,
            channels=channels,
            capabilities=[Capability(name=k, score=float(v)) for k, v in (raw.get("capabilities") or {}).items()],
        )


# ===== Politiki / Overraydy =====

class Policy(VersionedModel):
    model: str = "synergy.Policy"
    max_roles_per_agent: int = Field(2, ge=1, le=10)
    incompat: List[Tuple[RoleName, RoleName]] = Field(default_factory=list, description="Spisok par nesovmestimykh roley")
    required_for_purpose: Dict[str, List[RoleName]] = Field(default_factory=dict)

    @validator("incompat", pre=True, always=True)
    def _incompat_norm(cls, v):
        # prinimaem kak spiski/kortezhi lyubykh strok → normalizuem v (roleA, roleB)
        out = []
        for it in v or []:
            try:
                a, b = list(it)[0], list(it)[1]
                out.append((RoleName(a), RoleName(b)))
            except Exception:
                continue
        return out


class Override(BaseModel):
    mapping: Dict[RoleName, str] = Field(default_factory=dict)

    @staticmethod
    def from_legacy(raw: Mapping[str, Any]) -> "Override":
        m = {}
        for k, v in (raw or {}).items():
            try:
                m[RoleName(k)] = str(v)
            except Exception:
                continue
        return Override(mapping=m)


# ===== Request/Plan/Step/Outcome =====

class AssignmentStep(BaseModel):
    description: str
    delta_score: float = 0.0


class AssignmentRequest(VersionedModel):
    model: str = "synergy.AssignmentRequest"
    team_id: str
    roles: Optional[List[RoleName]] = None
    overrides: Optional[Override] = None
    request_id: str = Field(default_factory=_uid)
    ts: dt.datetime = Field(default_factory=lambda: dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc))


class AssignmentPlan(VersionedModel):
    model: str = "synergy.AssignmentPlan"
    team_id: str
    assigned: Dict[RoleName, str] = Field(default_factory=dict)
    total_score: float = 0.0
    steps: List[AssignmentStep] = Field(default_factory=list)
    trace_id: str = Field(default_factory=_uid)


class Outcome(VersionedModel):
    model: str = "synergy.Outcome"
    team_id: str
    outcome: Literal["success", "failure", "partial", "cancelled"] = "success"
    notes: Optional[str] = None
    ts: dt.datetime = Field(default_factory=lambda: dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc))


# ===== Telemetriya / Riski =====

class TelemetryEvent(VersionedModel):
    model: str = "synergy.TelemetryEvent"
    agent_id: str = Field(..., description="ID agenta/ustroystva")
    vendor: Optional[str] = Field(None, description="Istochnik (acme_uav/neo/...)")
    payload: Dict[str, Any] = Field(default_factory=dict)
    # Canonical fields (if known)
    latency_ms: Optional[float] = Field(None, ge=0.0, le=5000.0)
    flight_time_min: Optional[float] = Field(None, ge=0.0, le=360.0)
    payload_g: Optional[float] = Field(None, ge=0.0, le=50000.0)


class Risk(BaseModel):
    name: str
    severity: confloat(ge=0.0, le=1.0) = 0.0
    reason: Optional[str] = None
