import asyncio

from modules.synaps import (
    SynapsConfig,
    SynapsMessageType,
    build_envelope,
    build_safe_chat_thought_handler,
    config_from_legacy_listener_values,
    make_sister_inbound_view,
    prepare_outbound_request,
    read_payload_safely,
    run_awaitable_in_new_loop,
    synaps_health,
)


def _config() -> SynapsConfig:
    return SynapsConfig(
        node_url="http://sister.local",
        sync_token="shared-secret",
        node_id="ester-test",
    )


def _payload(message_type: SynapsMessageType, content: str = "hello", metadata: dict | None = None) -> dict:
    envelope = build_envelope(
        _config(),
        content,
        message_type,
        message_id="incoming-1",
        created_at="2026-04-26T00:00:00+00:00",
        metadata=metadata or {},
    )
    return prepare_outbound_request(_config(), envelope).json


class _Logger:
    def __init__(self):
        self.lines = []

    def info(self, message):
        self.lines.append(("info", message))

    def warning(self, message):
        self.lines.append(("warning", message))

    def error(self, message):
        self.lines.append(("error", message))


def test_legacy_default_token_is_rejected_as_missing_config():
    config = config_from_legacy_listener_values(
        node_url="http://sister.local",
        sync_token="default_token",
        node_id="ester-test",
    )

    health = synaps_health(config)

    assert config.sync_token == ""
    assert health.has_token is False


def test_safe_chat_handler_runs_async_safe_chat_in_injected_loop_runner():
    captured = {}

    async def safe_chat(provider, messages, **kwargs):
        captured["provider"] = provider
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return "bounded reply"

    handler = build_safe_chat_thought_handler(
        safe_chat,
        awaitable_runner=run_awaitable_in_new_loop,
        max_tokens=64,
    )
    envelope = build_envelope(_config(), "question", SynapsMessageType.THOUGHT_REQUEST)

    assert handler(envelope) == "bounded reply"
    assert captured["provider"] == "local"
    assert captured["messages"][1]["content"] == "question"
    assert captured["kwargs"]["temperature"] == 0.7
    assert captured["kwargs"]["max_tokens"] == 64


def test_make_sister_inbound_view_returns_flask_compatible_tuple():
    async def safe_chat(_provider, messages, **_kwargs):
        return f"reply to {messages[1]['content']}"

    view = make_sister_inbound_view(
        payload_reader=lambda: _payload(SynapsMessageType.THOUGHT_REQUEST, "risk?"),
        jsonifier=lambda body: {"json": body},
        config_factory=_config,
        safe_chat=safe_chat,
    )

    body, status = view()

    assert status == 200
    assert body["json"]["status"] == "success"
    assert body["json"]["content"] == "reply to risk?"
    assert body["json"]["correlation_id"] == "incoming-1"
    assert "shared-secret" not in str(body)


def test_view_sanitizes_handler_failure_and_logs_without_content():
    logger = _Logger()

    async def safe_chat(_provider, _messages, **_kwargs):
        raise RuntimeError("hidden runtime detail")

    view = make_sister_inbound_view(
        payload_reader=lambda: _payload(SynapsMessageType.THOUGHT_REQUEST, "prompt body"),
        jsonifier=lambda body: body,
        config_factory=_config,
        safe_chat=safe_chat,
        logger=logger,
    )

    body, status = view()

    assert status == 500
    assert body["message"] == "thought_handler_failed"
    assert "hidden runtime detail" not in str(body)
    assert "prompt body" not in str(logger.lines)
    assert "shared-secret" not in str(logger.lines)
    assert logger.lines[0][0] == "error"


def test_view_logs_safe_operator_metadata_without_content_or_token():
    logger = _Logger()

    async def safe_chat(_provider, _messages, **_kwargs):
        return "bounded reply"

    view = make_sister_inbound_view(
        payload_reader=lambda: _payload(
            SynapsMessageType.THOUGHT_REQUEST,
            "prompt body",
            metadata={
                "window_id": "synaps-window-test",
                "mode": "synaps_operator_gate",
                "operator_window": True,
                "message_index": 1,
            },
        ),
        jsonifier=lambda body: body,
        config_factory=_config,
        safe_chat=safe_chat,
        logger=logger,
    )

    _body, status = view()
    line = logger.lines[0][1]

    assert status == 200
    assert "metadata.window_id=synaps-window-test" in line
    assert "metadata.mode=synaps_operator_gate" in line
    assert "metadata.operator_window=true" in line
    assert "metadata.message_index=1" in line
    assert "prompt body" not in line
    assert "shared-secret" not in line


def test_view_rejects_invalid_token_before_safe_chat():
    called = False
    payload = _payload(SynapsMessageType.THOUGHT_REQUEST)
    payload["token"] = "wrong"

    async def safe_chat(_provider, _messages, **_kwargs):
        nonlocal called
        called = True
        return "no"

    view = make_sister_inbound_view(
        payload_reader=lambda: payload,
        jsonifier=lambda body: body,
        config_factory=_config,
        safe_chat=safe_chat,
    )

    body, status = view()

    assert status == 403
    assert body["message"] == "invalid_token"
    assert called is False


def test_payload_reader_failures_are_fail_closed():
    async def safe_chat(_provider, _messages, **_kwargs):
        return "no"

    view = make_sister_inbound_view(
        payload_reader=lambda: (_ for _ in ()).throw(RuntimeError("reader failed")),
        jsonifier=lambda body: body,
        config_factory=_config,
        safe_chat=safe_chat,
    )

    body, status = view()

    assert status == 403
    assert body["message"] == "missing_token"
    assert read_payload_safely(lambda: ["not", "mapping"]) == {}


def test_run_awaitable_in_new_loop_closes_loop_after_use():
    async def sample():
        await asyncio.sleep(0)
        return "ok"

    assert run_awaitable_in_new_loop(sample()) == "ok"
