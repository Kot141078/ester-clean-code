"""SYNAPS inbound/outbound adapter helpers.

The adapter is framework-neutral: callers can wrap its plain response objects
with Flask/FastAPI/etc. It does not import HTTP clients or start listeners.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .protocol import (
    SCHEMA_VERSION,
    SynapsConfig,
    SynapsEnvelope,
    SynapsMessageType,
    SynapsPreparedRequest,
    build_envelope,
    parse_inbound_payload,
    prepare_outbound_request,
    synaps_health,
    to_record,
)


ThoughtHandler = Callable[[SynapsEnvelope], str]
AsyncThoughtHandler = Callable[[SynapsEnvelope], Awaitable[str]]


@dataclass(frozen=True)
class SynapsRouteResponse:
    body: dict[str, Any]
    status_code: int
    accepted: bool
    reason: str
    request_envelope: SynapsEnvelope | None = None
    response_envelope: SynapsEnvelope | None = None


def handle_inbound_payload(
    payload: Mapping[str, Any],
    config: SynapsConfig,
    thought_handler: ThoughtHandler | None = None,
) -> SynapsRouteResponse:
    """Handle a legacy-compatible `/sister/inbound` payload.

    `thought_handler` is injected by the runtime wrapper. This keeps model calls,
    memory access, and event loops outside the protocol layer.
    """

    initial = _parse_and_gate(payload, config)
    if initial is not None:
        return initial

    parsed = parse_inbound_payload(payload, config.sync_token)
    envelope = parsed.envelope
    if envelope is None:
        return _error_response(parsed.status_code, parsed.reason, accepted=False)

    if envelope.message_type is SynapsMessageType.THOUGHT_REQUEST:
        if thought_handler is None:
            return _error_response(
                503,
                "thought_handler_missing",
                request_envelope=envelope,
                accepted=True,
            )
        try:
            thought = str(thought_handler(envelope) or "")
        except Exception:
            return _error_response(
                500,
                "thought_handler_failed",
                request_envelope=envelope,
                accepted=True,
            )
        return _thought_reply(config, envelope, thought)

    if envelope.message_type is SynapsMessageType.HEALTH:
        return _health_response(config, envelope)

    return _ack_response(config, envelope)


async def handle_inbound_payload_async(
    payload: Mapping[str, Any],
    config: SynapsConfig,
    thought_handler: AsyncThoughtHandler | None = None,
) -> SynapsRouteResponse:
    """Async twin for runtimes that already own an event loop."""

    initial = _parse_and_gate(payload, config)
    if initial is not None:
        return initial

    parsed = parse_inbound_payload(payload, config.sync_token)
    envelope = parsed.envelope
    if envelope is None:
        return _error_response(parsed.status_code, parsed.reason, accepted=False)

    if envelope.message_type is SynapsMessageType.THOUGHT_REQUEST:
        if thought_handler is None:
            return _error_response(
                503,
                "thought_handler_missing",
                request_envelope=envelope,
                accepted=True,
            )
        try:
            thought = str(await thought_handler(envelope) or "")
        except Exception:
            return _error_response(
                500,
                "thought_handler_failed",
                request_envelope=envelope,
                accepted=True,
            )
        return _thought_reply(config, envelope, thought)

    if envelope.message_type is SynapsMessageType.HEALTH:
        return _health_response(config, envelope)

    return _ack_response(config, envelope)


def prepare_thought_request(
    config: SynapsConfig,
    query_text: str,
    correlation_id: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> SynapsPreparedRequest:
    envelope = build_envelope(
        config,
        query_text,
        SynapsMessageType.THOUGHT_REQUEST,
        correlation_id=correlation_id,
        metadata=metadata,
    )
    return prepare_outbound_request(config, envelope, timeout_sec=config.opinion_timeout_sec)


def prepare_chat_message(
    config: SynapsConfig,
    message_text: str,
    metadata: Mapping[str, Any] | None = None,
) -> SynapsPreparedRequest:
    envelope = build_envelope(
        config,
        message_text,
        SynapsMessageType.CHAT,
        metadata=metadata,
    )
    return prepare_outbound_request(config, envelope, timeout_sec=config.timeout_sec)


def _parse_and_gate(
    payload: Mapping[str, Any],
    config: SynapsConfig,
) -> SynapsRouteResponse | None:
    if not config.enabled:
        return _error_response(503, "synaps_disabled", accepted=False)

    parsed = parse_inbound_payload(payload, config.sync_token)
    if parsed.accepted:
        return None
    return _error_response(parsed.status_code, parsed.reason, accepted=False)


def _ack_response(config: SynapsConfig, request_envelope: SynapsEnvelope) -> SynapsRouteResponse:
    response_envelope = build_envelope(
        config,
        "received",
        SynapsMessageType.ACK,
        correlation_id=request_envelope.message_id,
        metadata={"reply_to": request_envelope.message_id},
    )
    return SynapsRouteResponse(
        body={
            "status": "received",
            "thank_you": "sister",
            "schema": SCHEMA_VERSION,
            "sender": config.node_id,
            "message_id": response_envelope.message_id,
            "correlation_id": response_envelope.correlation_id,
            "content_hash": response_envelope.content_hash,
        },
        status_code=200,
        accepted=True,
        reason="received",
        request_envelope=request_envelope,
        response_envelope=response_envelope,
    )


def _health_response(config: SynapsConfig, request_envelope: SynapsEnvelope) -> SynapsRouteResponse:
    response_envelope = build_envelope(
        config,
        "health",
        SynapsMessageType.HEALTH,
        correlation_id=request_envelope.message_id,
        metadata={"reply_to": request_envelope.message_id},
    )
    return SynapsRouteResponse(
        body={
            "status": "success",
            "schema": SCHEMA_VERSION,
            "sender": config.node_id,
            "message_id": response_envelope.message_id,
            "correlation_id": response_envelope.correlation_id,
            "health": to_record(synaps_health(config)),
        },
        status_code=200,
        accepted=True,
        reason="health",
        request_envelope=request_envelope,
        response_envelope=response_envelope,
    )


def _thought_reply(
    config: SynapsConfig,
    request_envelope: SynapsEnvelope,
    thought: str,
) -> SynapsRouteResponse:
    response_envelope = build_envelope(
        config,
        thought,
        SynapsMessageType.THOUGHT_REPLY,
        correlation_id=request_envelope.message_id,
        metadata={
            "reply_to": request_envelope.message_id,
            "request_sender": request_envelope.sender,
        },
    )
    return SynapsRouteResponse(
        body={
            "status": "success",
            "schema": SCHEMA_VERSION,
            "sender": config.node_id,
            "content": response_envelope.content,
            "message_id": response_envelope.message_id,
            "correlation_id": response_envelope.correlation_id,
            "content_hash": response_envelope.content_hash,
        },
        status_code=200,
        accepted=True,
        reason="thought_reply",
        request_envelope=request_envelope,
        response_envelope=response_envelope,
    )


def _error_response(
    status_code: int,
    reason: str,
    request_envelope: SynapsEnvelope | None = None,
    accepted: bool = False,
) -> SynapsRouteResponse:
    return SynapsRouteResponse(
        body={
            "status": "error",
            "schema": SCHEMA_VERSION,
            "message": reason,
        },
        status_code=status_code,
        accepted=accepted,
        reason=reason,
        request_envelope=request_envelope,
    )
