import asyncio

from modules.synaps import (
    SynapsConfig,
    SynapsMessageType,
    build_envelope,
    handle_inbound_payload,
    handle_inbound_payload_async,
    prepare_chat_message,
    prepare_outbound_request,
    prepare_thought_request,
)


def _config() -> SynapsConfig:
    return SynapsConfig(
        node_url="http://sister.local",
        sync_token="shared-secret",
        node_id="ester-test",
    )


def _payload(message_type: SynapsMessageType, content: str = "hello") -> dict:
    envelope = build_envelope(
        _config(),
        content,
        message_type,
        message_id="incoming-1",
        created_at="2026-04-26T00:00:00+00:00",
    )
    return prepare_outbound_request(_config(), envelope).json


def test_chat_payload_returns_legacy_ack_without_invoking_thought_handler():
    called = False

    def handler(_envelope):
        nonlocal called
        called = True
        return "should not be called"

    response = handle_inbound_payload(_payload(SynapsMessageType.CHAT), _config(), handler)

    assert response.status_code == 200
    assert response.accepted is True
    assert response.reason == "received"
    assert response.body["status"] == "received"
    assert response.body["thank_you"] == "sister"
    assert response.body["sender"] == "ester-test"
    assert response.body["correlation_id"] == "incoming-1"
    assert called is False
    assert "shared-secret" not in str(response.body)


def test_thought_request_invokes_injected_handler_and_returns_sanitized_reply():
    def handler(envelope):
        assert envelope.sender == "ester-test"
        assert envelope.content == "What should we watch?"
        return "Watch boundaries and timeouts."

    response = handle_inbound_payload(
        _payload(SynapsMessageType.THOUGHT_REQUEST, "What should we watch?"),
        _config(),
        handler,
    )

    assert response.status_code == 200
    assert response.reason == "thought_reply"
    assert response.body["status"] == "success"
    assert response.body["content"] == "Watch boundaries and timeouts."
    assert response.body["correlation_id"] == "incoming-1"
    assert response.response_envelope is not None
    assert response.response_envelope.message_type == SynapsMessageType.THOUGHT_REPLY
    assert "shared-secret" not in str(response.body)


def test_thought_request_without_handler_fails_closed():
    response = handle_inbound_payload(
        _payload(SynapsMessageType.THOUGHT_REQUEST),
        _config(),
    )

    assert response.status_code == 503
    assert response.accepted is True
    assert response.reason == "thought_handler_missing"
    assert response.body == {
        "status": "error",
        "schema": "ester.synaps.envelope.v1",
        "message": "thought_handler_missing",
    }


def test_handler_exception_is_not_disclosed_to_peer():
    def handler(_envelope):
        raise RuntimeError("internal stack detail")

    response = handle_inbound_payload(
        _payload(SynapsMessageType.THOUGHT_REQUEST),
        _config(),
        handler,
    )

    assert response.status_code == 500
    assert response.reason == "thought_handler_failed"
    assert "internal stack detail" not in str(response.body)


def test_invalid_token_is_rejected_before_handler():
    called = False
    payload = _payload(SynapsMessageType.THOUGHT_REQUEST)
    payload["token"] = "wrong"

    def handler(_envelope):
        nonlocal called
        called = True
        return "no"

    response = handle_inbound_payload(payload, _config(), handler)

    assert response.status_code == 403
    assert response.accepted is False
    assert response.reason == "invalid_token"
    assert called is False


def test_health_payload_returns_redacted_health_record():
    response = handle_inbound_payload(_payload(SynapsMessageType.HEALTH), _config())

    assert response.status_code == 200
    assert response.reason == "health"
    assert response.body["health"]["state"] == "ready"
    assert response.body["health"]["has_token"] is True
    assert response.body["health"]["target_url"] == "http://sister.local/sister/inbound"
    assert "shared-secret" not in str(response.body)


def test_file_manifest_without_handler_fails_closed_after_auth():
    response = handle_inbound_payload(_payload(SynapsMessageType.FILE_MANIFEST, "{}"), _config())

    assert response.status_code == 503
    assert response.accepted is True
    assert response.reason == "file_manifest_handler_missing"


def test_async_thought_handler_is_supported_without_owning_runtime_loop():
    async def run():
        async def handler(envelope):
            return f"async reply to {envelope.message_id}"

        return await handle_inbound_payload_async(
            _payload(SynapsMessageType.THOUGHT_REQUEST),
            _config(),
            handler,
        )

    response = asyncio.run(run())

    assert response.status_code == 200
    assert response.body["content"] == "async reply to incoming-1"


def test_prepare_helpers_keep_send_and_opinion_timeouts_separate():
    config = SynapsConfig(
        node_url="http://sister.local",
        sync_token="shared-secret",
        node_id="ester-test",
        timeout_sec=3.0,
        opinion_timeout_sec=45.0,
    )

    chat = prepare_chat_message(config, "hello")
    thought = prepare_thought_request(config, "think")

    assert chat.url == "http://sister.local/sister/inbound"
    assert chat.timeout_sec == 3.0
    assert chat.json["type"] == "chat"
    assert thought.timeout_sec == 45.0
    assert thought.json["type"] == "thought_request"
