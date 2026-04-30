"""Runtime bridge helpers for legacy SYNAPS listeners.

These helpers let a Flask-style listener reuse the framework-neutral SYNAPS
adapter without importing Flask here and without exposing handler exceptions.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from .adapter import FileManifestHandler, SynapsRouteResponse, handle_inbound_payload
from .protocol import SynapsConfig, SynapsEnvelope


PayloadReader = Callable[[], Mapping[str, Any] | None]
Jsonifier = Callable[[dict[str, Any]], Any]
SafeChatCallable = Callable[..., Awaitable[str] | str]
AwaitableRunner = Callable[[Awaitable[Any]], Any]
ConfigFactory = Callable[[], SynapsConfig]

DEFAULT_SISTER_SYSTEM_PROMPT = (
    "You help your sister form a concise, bounded opinion. "
    "Do not expose private memory, secrets, traces, or stack details."
)


def config_from_legacy_listener_values(
    node_url: str,
    sync_token: str,
    node_id: str = "ester_node",
    timeout_sec: float = 2.0,
    opinion_timeout_sec: float = 120.0,
    enabled: bool = True,
) -> SynapsConfig:
    """Build config from old listener globals while rejecting unsafe defaults."""

    token = (sync_token or "").strip()
    if token == "default_token":
        token = ""
    return SynapsConfig(
        node_url=node_url,
        sync_token=token,
        node_id=node_id,
        timeout_sec=timeout_sec,
        opinion_timeout_sec=opinion_timeout_sec,
        enabled=enabled,
    )


def run_awaitable_in_new_loop(awaitable: Awaitable[Any]) -> Any:
    """Run an awaitable from a synchronous listener thread."""

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(awaitable)
    finally:
        try:
            loop.close()
        finally:
            asyncio.set_event_loop(None)


def build_safe_chat_thought_handler(
    safe_chat: SafeChatCallable,
    provider: str = "local",
    system_prompt: str = DEFAULT_SISTER_SYSTEM_PROMPT,
    awaitable_runner: AwaitableRunner = run_awaitable_in_new_loop,
    **safe_chat_kwargs: Any,
) -> Callable[[SynapsEnvelope], str]:
    """Adapt the legacy async `_safe_chat` shape into a SYNAPS thought handler."""

    kwargs = {"temperature": 0.7}
    kwargs.update(safe_chat_kwargs)

    def _handler(envelope: SynapsEnvelope) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": envelope.content},
        ]
        result = safe_chat(provider, messages, **kwargs)
        if inspect.isawaitable(result):
            result = awaitable_runner(result)
        return str(result or "")

    return _handler


def read_payload_safely(payload_reader: PayloadReader) -> Mapping[str, Any]:
    try:
        payload = payload_reader() or {}
    except Exception:
        return {}
    if not isinstance(payload, Mapping):
        return {}
    return payload


def make_sister_inbound_view(
    payload_reader: PayloadReader,
    jsonifier: Jsonifier,
    config_factory: ConfigFactory,
    safe_chat: SafeChatCallable,
    logger: Any | None = None,
    file_manifest_handler: FileManifestHandler | None = None,
    **safe_chat_kwargs: Any,
) -> Callable[[], tuple[Any, int]]:
    """Build a Flask-compatible view function without importing Flask."""

    thought_handler = build_safe_chat_thought_handler(safe_chat, **safe_chat_kwargs)

    def _view() -> tuple[Any, int]:
        payload = read_payload_safely(payload_reader)
        response = handle_inbound_payload(payload, config_factory(), thought_handler, file_manifest_handler)
        log_synaps_route_response(logger, response)
        return jsonifier(response.body), response.status_code

    return _view


def log_synaps_route_response(logger: Any | None, response: SynapsRouteResponse) -> None:
    """Log routing metadata only; never log content, tokens, or stack details."""

    if logger is None:
        return
    envelope = response.request_envelope
    sender = envelope.sender if envelope is not None else ""
    message_type = envelope.message_type.value if envelope is not None else ""
    metadata = _safe_log_metadata(envelope)
    message = (
        "[SYNAPS] inbound "
        f"status={response.status_code} reason={response.reason} "
        f"accepted={response.accepted} sender={sender} type={message_type}{metadata}"
    )
    try:
        if response.status_code >= 500 and hasattr(logger, "error"):
            logger.error(message)
        elif response.status_code >= 400 and hasattr(logger, "warning"):
            logger.warning(message)
        elif hasattr(logger, "info"):
            logger.info(message)
    except Exception:
        return


def _safe_log_metadata(envelope: SynapsEnvelope | None) -> str:
    if envelope is None:
        return ""
    metadata = envelope.metadata or {}
    fields = []
    for key in ("window_id", "mode", "operator_window", "message_index", "transfer_id"):
        if key not in metadata:
            continue
        value = _safe_log_value(metadata.get(key))
        if value:
            fields.append(f"{key}={value}")
    if not fields:
        return ""
    return " metadata." + " metadata.".join(fields)


def _safe_log_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value or "").strip()
    if not text:
        return ""
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", ".", ":"} else "_" for ch in text)
    return safe[:120]
