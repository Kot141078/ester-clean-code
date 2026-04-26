"""SYNAPS protocol/config/auth sidecar.

This module builds and verifies sister-node envelopes. It intentionally does
not import HTTP clients, start listeners, or touch memory/vector stores.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4


SCHEMA_VERSION = "ester.synaps.envelope.v1"
DEFAULT_INBOUND_PATH = "/sister/inbound"

_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}
_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
_FORBIDDEN_METADATA_KEYS = frozenset(
    {
        "auth_token",
        "credential",
        "memory_dump",
        "memory_export",
        "raw_memory",
        "secret",
        "sync_token",
        "token",
        "vector_dump",
    }
)


class SynapsValidationError(ValueError):
    """Raised when a SYNAPS envelope would cross a safety boundary."""


class SynapsMessageType(str, Enum):
    CHAT = "chat"
    THOUGHT_REQUEST = "thought_request"
    THOUGHT_REPLY = "thought_reply"
    HEALTH = "health"
    ACK = "ack"
    ERROR = "error"


class SynapsAuthStatus(str, Enum):
    OK = "ok"
    MISSING_TOKEN = "missing_token"
    INVALID_TOKEN = "invalid_token"


class SynapsHealthState(str, Enum):
    READY = "ready"
    DISABLED = "disabled"
    MISCONFIGURED = "misconfigured"


@dataclass(frozen=True)
class SynapsConfig:
    node_url: str = ""
    sync_token: str = ""
    node_id: str = "ester_node"
    timeout_sec: float = 2.0
    opinion_timeout_sec: float = 120.0
    enabled: bool = True
    inbound_path: str = DEFAULT_INBOUND_PATH

    def __post_init__(self) -> None:
        node_url = (self.node_url or "").strip().rstrip("/")
        sync_token = (self.sync_token or "").strip()
        node_id = (self.node_id or "ester_node").strip() or "ester_node"
        inbound_path = (self.inbound_path or DEFAULT_INBOUND_PATH).strip()
        if not inbound_path.startswith("/"):
            inbound_path = "/" + inbound_path
        object.__setattr__(self, "node_url", node_url)
        object.__setattr__(self, "sync_token", sync_token)
        object.__setattr__(self, "node_id", node_id)
        object.__setattr__(self, "inbound_path", inbound_path)


@dataclass(frozen=True)
class SynapsEnvelope:
    message_id: str
    sender: str
    message_type: SynapsMessageType
    content: str
    created_at: str
    correlation_id: str = ""
    content_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    schema: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        message_type = _coerce_message_type(self.message_type)
        content = "" if self.content is None else str(self.content)
        metadata = dict(self.metadata or {})
        _validate_metadata(metadata)

        object.__setattr__(self, "message_type", message_type)
        object.__setattr__(self, "sender", (self.sender or "ester_node").strip())
        object.__setattr__(self, "content", content)
        object.__setattr__(self, "metadata", metadata)
        if not self.content_hash:
            object.__setattr__(self, "content_hash", hash_content(content))


@dataclass(frozen=True)
class SynapsPreparedRequest:
    url: str
    headers: dict[str, str]
    json: dict[str, Any]
    timeout_sec: float


@dataclass(frozen=True)
class SynapsInboundResult:
    accepted: bool
    auth_status: SynapsAuthStatus
    status_code: int
    reason: str
    envelope: SynapsEnvelope | None = None


@dataclass(frozen=True)
class SynapsHealth:
    state: SynapsHealthState
    enabled: bool
    has_node_url: bool
    has_token: bool
    node_id: str
    target_url: str
    token_sha256_prefix: str = ""


def config_from_env(env: Mapping[str, str] | None = None) -> SynapsConfig:
    """Create config from environment without unsafe default credentials."""

    source = os.environ if env is None else env
    node_id = (
        _env_value(source, "ESTER_NODE_ID")
        or _env_value(source, "NODE_ID")
        or _env_value(source, "COMPUTERNAME")
        or _env_value(source, "HOSTNAME")
        or "ester_node"
    )
    return SynapsConfig(
        node_url=_env_value(source, "SISTER_NODE_URL"),
        sync_token=_env_value(source, "SISTER_SYNC_TOKEN"),
        node_id=node_id,
        timeout_sec=_bounded_float(
            _env_value(source, "SISTER_SEND_TIMEOUT_SEC"),
            default=2.0,
            minimum=0.1,
            maximum=30.0,
        ),
        opinion_timeout_sec=_bounded_float(
            _env_value(source, "SISTER_OPINION_TIMEOUT_SEC"),
            default=120.0,
            minimum=1.0,
            maximum=300.0,
        ),
        enabled=_env_bool(_env_value(source, "SYNAPS_ENABLED"), default=True),
    )


def build_envelope(
    config: SynapsConfig,
    content: str,
    message_type: SynapsMessageType | str = SynapsMessageType.CHAT,
    correlation_id: str = "",
    metadata: Mapping[str, Any] | None = None,
    message_id: str | None = None,
    created_at: str | None = None,
) -> SynapsEnvelope:
    return SynapsEnvelope(
        message_id=message_id or f"synaps-{uuid4()}",
        sender=config.node_id,
        message_type=_coerce_message_type(message_type),
        content=content,
        created_at=created_at or _utc_now(),
        correlation_id=correlation_id,
        metadata=dict(metadata or {}),
    )


def prepare_outbound_request(
    config: SynapsConfig,
    envelope: SynapsEnvelope,
    timeout_sec: float | None = None,
) -> SynapsPreparedRequest:
    """Prepare a legacy-compatible request without performing network I/O."""

    _require_ready_for_outbound(config)
    payload = {
        "schema": envelope.schema,
        "message_id": envelope.message_id,
        "sender": envelope.sender,
        "type": envelope.message_type.value,
        "content": envelope.content,
        "token": config.sync_token,
        "timestamp": envelope.created_at,
        "created_at": envelope.created_at,
        "correlation_id": envelope.correlation_id,
        "content_hash": envelope.content_hash,
        "metadata": dict(envelope.metadata),
    }
    return SynapsPreparedRequest(
        url=f"{config.node_url}{config.inbound_path}",
        headers={
            "Content-Type": "application/json",
            "X-Synaps-Schema": SCHEMA_VERSION,
            "X-Synaps-Content-Sha256": envelope.content_hash,
        },
        json=payload,
        timeout_sec=float(timeout_sec if timeout_sec is not None else config.timeout_sec),
    )


def parse_inbound_payload(
    payload: Mapping[str, Any],
    expected_token: str,
) -> SynapsInboundResult:
    if not isinstance(payload, Mapping):
        return SynapsInboundResult(
            accepted=False,
            auth_status=SynapsAuthStatus.MISSING_TOKEN,
            status_code=400,
            reason="payload_not_object",
        )

    auth_status = verify_token(payload.get("token"), expected_token)
    if auth_status is not SynapsAuthStatus.OK:
        return SynapsInboundResult(
            accepted=False,
            auth_status=auth_status,
            status_code=403,
            reason=auth_status.value,
        )

    content = "" if payload.get("content") is None else str(payload.get("content"))
    incoming_hash = str(payload.get("content_hash") or "").strip()
    computed_hash = hash_content(content)
    if incoming_hash and not hmac.compare_digest(incoming_hash, computed_hash):
        return SynapsInboundResult(
            accepted=False,
            auth_status=auth_status,
            status_code=400,
            reason="content_hash_mismatch",
        )

    try:
        metadata = payload.get("metadata") or {}
        if not isinstance(metadata, Mapping):
            raise SynapsValidationError("metadata must be an object")
        envelope = SynapsEnvelope(
            message_id=str(payload.get("message_id") or f"legacy-{uuid4()}"),
            sender=str(payload.get("sender") or "sister"),
            message_type=_coerce_message_type(str(payload.get("type") or "chat")),
            content=content,
            created_at=str(payload.get("created_at") or payload.get("timestamp") or _utc_now()),
            correlation_id=str(payload.get("correlation_id") or ""),
            content_hash=computed_hash,
            metadata=dict(metadata),
            schema=str(payload.get("schema") or SCHEMA_VERSION),
        )
    except (SynapsValidationError, ValueError) as exc:
        return SynapsInboundResult(
            accepted=False,
            auth_status=auth_status,
            status_code=400,
            reason=str(exc),
        )

    return SynapsInboundResult(
        accepted=True,
        auth_status=auth_status,
        status_code=200,
        reason="accepted",
        envelope=envelope,
    )


def verify_token(provided: Any, expected: str) -> SynapsAuthStatus:
    expected_token = (expected or "").strip()
    provided_token = "" if provided is None else str(provided).strip()
    if not expected_token or not provided_token:
        return SynapsAuthStatus.MISSING_TOKEN
    if hmac.compare_digest(provided_token, expected_token):
        return SynapsAuthStatus.OK
    return SynapsAuthStatus.INVALID_TOKEN


def synaps_health(config: SynapsConfig) -> SynapsHealth:
    has_node_url = bool(config.node_url)
    has_token = bool(config.sync_token)
    if not config.enabled:
        state = SynapsHealthState.DISABLED
    elif has_node_url and has_token:
        state = SynapsHealthState.READY
    else:
        state = SynapsHealthState.MISCONFIGURED

    token_prefix = ""
    if has_token:
        token_prefix = hashlib.sha256(config.sync_token.encode("utf-8")).hexdigest()[:12]

    return SynapsHealth(
        state=state,
        enabled=config.enabled,
        has_node_url=has_node_url,
        has_token=has_token,
        node_id=config.node_id,
        target_url=f"{config.node_url}{config.inbound_path}" if has_node_url else "",
        token_sha256_prefix=token_prefix,
    )


def hash_content(content: str) -> str:
    normalized = "" if content is None else str(content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def to_record(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: to_record(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): to_record(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_record(item) for item in value]
    return value


def _require_ready_for_outbound(config: SynapsConfig) -> None:
    if not config.enabled:
        raise SynapsValidationError("synaps disabled")
    if not config.node_url:
        raise SynapsValidationError("sister node url missing")
    if not config.sync_token:
        raise SynapsValidationError("sister sync token missing")


def _coerce_message_type(value: SynapsMessageType | str) -> SynapsMessageType:
    if isinstance(value, SynapsMessageType):
        return value
    try:
        return SynapsMessageType(str(value))
    except ValueError as exc:
        raise SynapsValidationError(f"unknown message type: {value}") from exc


def _validate_metadata(metadata: Mapping[str, Any]) -> None:
    for key, value in metadata.items():
        key_lc = str(key).strip().lower()
        if key_lc in _FORBIDDEN_METADATA_KEYS:
            raise SynapsValidationError(f"forbidden metadata key: {key}")
        if isinstance(value, Mapping):
            _validate_metadata(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, Mapping):
                    _validate_metadata(item)


def _env_value(env: Mapping[str, str], key: str) -> str:
    return str(env.get(key) or "").strip()


def _env_bool(value: str, default: bool) -> bool:
    normalized = (value or "").strip().lower()
    if not normalized:
        return default
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


def _bounded_float(
    value: str,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
