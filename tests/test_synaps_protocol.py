import pytest

from modules.synaps import (
    SynapsAuthStatus,
    SynapsConfig,
    SynapsHealthState,
    SynapsMessageType,
    SynapsValidationError,
    build_envelope,
    config_from_env,
    hash_content,
    parse_inbound_payload,
    prepare_outbound_request,
    synaps_health,
    to_record,
    verify_token,
)


def test_config_from_env_has_no_default_token_and_reports_misconfigured():
    config = config_from_env({})
    health = synaps_health(config)

    assert config.sync_token == ""
    assert config.node_url == ""
    assert health.state == SynapsHealthState.MISCONFIGURED
    assert health.has_token is False
    assert health.token_sha256_prefix == ""


def test_prepare_outbound_request_is_legacy_compatible_without_network_io():
    config = SynapsConfig(
        node_url="http://127.0.0.1:8081/",
        sync_token="shared-secret",
        node_id="ester-test",
    )
    envelope = build_envelope(
        config,
        "one bounded thought",
        SynapsMessageType.THOUGHT_REQUEST,
        correlation_id="corr-1",
        metadata={"scope": "test"},
        message_id="msg-1",
        created_at="2026-04-26T00:00:00+00:00",
    )

    request = prepare_outbound_request(config, envelope)

    assert request.url == "http://127.0.0.1:8081/sister/inbound"
    assert request.timeout_sec == 2.0
    assert request.headers["X-Synaps-Schema"] == "ester.synaps.envelope.v1"
    assert request.json["sender"] == "ester-test"
    assert request.json["type"] == "thought_request"
    assert request.json["token"] == "shared-secret"
    assert request.json["timestamp"] == "2026-04-26T00:00:00+00:00"
    assert request.json["content_hash"] == hash_content("one bounded thought")


def test_health_never_discloses_token_value():
    config = SynapsConfig(
        node_url="http://sister.local",
        sync_token="shared-secret",
        node_id="ester-test",
    )

    record = to_record(synaps_health(config))

    assert record["state"] == "ready"
    assert record["has_token"] is True
    assert record["target_url"] == "http://sister.local/sister/inbound"
    assert record["token_sha256_prefix"]
    assert "shared-secret" not in str(record)


def test_verify_token_uses_fail_closed_statuses():
    assert verify_token("shared-secret", "shared-secret") == SynapsAuthStatus.OK
    assert verify_token("wrong", "shared-secret") == SynapsAuthStatus.INVALID_TOKEN
    assert verify_token("", "shared-secret") == SynapsAuthStatus.MISSING_TOKEN
    assert verify_token("shared-secret", "") == SynapsAuthStatus.MISSING_TOKEN


def test_parse_inbound_payload_accepts_valid_legacy_payload():
    payload = {
        "sender": "lii-test",
        "type": "thought_request",
        "content": "What risk should we watch?",
        "token": "shared-secret",
        "timestamp": "2026-04-26T00:00:00+00:00",
    }

    result = parse_inbound_payload(payload, expected_token="shared-secret")

    assert result.accepted is True
    assert result.status_code == 200
    assert result.envelope is not None
    assert result.envelope.sender == "lii-test"
    assert result.envelope.message_type == SynapsMessageType.THOUGHT_REQUEST
    assert result.envelope.content_hash == hash_content("What risk should we watch?")


def test_parse_inbound_payload_rejects_bad_token_and_hash_mismatch():
    invalid_token = parse_inbound_payload(
        {"content": "hello", "token": "wrong"},
        expected_token="shared-secret",
    )
    invalid_hash = parse_inbound_payload(
        {
            "content": "hello",
            "content_hash": hash_content("different"),
            "token": "shared-secret",
        },
        expected_token="shared-secret",
    )

    assert invalid_token.accepted is False
    assert invalid_token.auth_status == SynapsAuthStatus.INVALID_TOKEN
    assert invalid_token.status_code == 403
    assert invalid_hash.accepted is False
    assert invalid_hash.reason == "content_hash_mismatch"
    assert invalid_hash.status_code == 400


def test_forbidden_metadata_blocks_raw_private_exports():
    config = SynapsConfig(
        node_url="http://sister.local",
        sync_token="shared-secret",
        node_id="ester-test",
    )

    with pytest.raises(SynapsValidationError):
        build_envelope(config, "hello", metadata={"raw_memory": "private dump"})


def test_env_timeout_values_are_bounded_and_disabled_flag_is_respected():
    config = config_from_env(
        {
            "SISTER_NODE_URL": "http://sister.local/",
            "SISTER_SYNC_TOKEN": "shared-secret",
            "SISTER_SEND_TIMEOUT_SEC": "0",
            "SISTER_OPINION_TIMEOUT_SEC": "9999",
            "SYNAPS_ENABLED": "off",
        }
    )

    assert config.node_url == "http://sister.local"
    assert config.timeout_sec == 0.1
    assert config.opinion_timeout_sec == 300.0
    assert synaps_health(config).state == SynapsHealthState.DISABLED
    with pytest.raises(SynapsValidationError):
        prepare_outbound_request(config, build_envelope(config, "hello"))
