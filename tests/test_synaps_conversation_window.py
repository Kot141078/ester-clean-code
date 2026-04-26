import ast
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from modules.synaps import SynapsConfig
from modules.synaps.window import (
    CONVERSATION_WINDOW_CONFIRM_PHRASE,
    ConversationWindowPolicy,
    ConversationWindowStore,
    build_conversation_turn_request,
    conversation_window_arm_status,
    validate_conversation_send_gate,
)


def test_policy_caps_window_to_fifteen_minutes_and_ten_messages():
    policy = ConversationWindowPolicy.from_env(
        {
            "SISTER_CONVERSATION_WINDOW_MAX_DURATION_SEC": "3600",
            "SISTER_CONVERSATION_WINDOW_MAX_MESSAGES": "99",
            "SISTER_CONVERSATION_WINDOW_COOLDOWN_SEC": "60",
        }
    )

    assert policy.max_duration_sec == 900
    assert policy.max_messages == 10
    assert policy.cooldown_sec == 3600


def test_store_blocks_second_window_inside_hour(tmp_path):
    store = ConversationWindowStore(tmp_path)
    policy = ConversationWindowPolicy()
    now = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)

    opened = store.open_window(policy, "status", now=now, window_id="w1")
    gate = store.can_open(policy, now=now + timedelta(minutes=30))

    assert opened["window_id"] == "w1"
    assert gate.ok is False
    assert gate.problems == ("conversation_window_cooldown_active",)
    assert gate.last_window_id == "w1"


def test_store_allows_retry_after_no_http_send_failure(tmp_path):
    store = ConversationWindowStore(tmp_path)
    policy = ConversationWindowPolicy()
    now = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)

    store.open_window(policy, "status", now=now, window_id="w1")
    store.record_turn("w1", direction="outbound", message_index=1, content="status", status="prepared", policy=policy)
    store.record_turn(
        "w1",
        direction="inbound",
        message_index=2,
        content='{"error": "NetworkDenyError"}',
        status="0",
        policy=policy,
        extra={"ok": False},
    )
    store.close_window("w1", "send_failed_no_http", policy, message_count=2)

    assert store.can_open(policy, now=now + timedelta(minutes=1)).ok is True


def test_turn_request_uses_memory_off_and_window_metadata():
    config = SynapsConfig(
        node_url="http://sister.local",
        sync_token="shared-secret",
        node_id="ester-test",
    )
    policy = ConversationWindowPolicy(max_messages=10)

    request = build_conversation_turn_request(config, policy, window_id="w1", content="hello")

    assert request.url == "http://sister.local/sister/inbound"
    assert request.json["type"] == "thought_request"
    assert request.json["metadata"]["memory"] == "off"
    assert request.json["metadata"]["conversation_window"] == "hourly"
    assert request.json["metadata"]["autochat_window"] == "bounded"
    assert request.json["metadata"]["files"] == "manifest_only"
    assert request.json["metadata"]["max_messages"] == 10


def test_send_gate_requires_window_flags_and_legacy_autochat_disabled(tmp_path):
    store = ConversationWindowStore(tmp_path)
    policy = ConversationWindowPolicy()
    env = {
        "SISTER_CONVERSATION_WINDOW": "1",
        "SISTER_CONVERSATION_WINDOW_ARMED": "1",
        "SISTER_AUTOCHAT": "0",
    }

    assert conversation_window_arm_status(env) == {"window": True, "armed": True, "legacy_autochat": False}
    assert validate_conversation_send_gate(env, CONVERSATION_WINDOW_CONFIRM_PHRASE, store, policy) == []
    assert "SISTER_AUTOCHAT_must_remain_disabled" in validate_conversation_send_gate(
        {**env, "SISTER_AUTOCHAT": "1"},
        CONVERSATION_WINDOW_CONFIRM_PHRASE,
        store,
        policy,
    )


def test_cli_dry_run_redacts_token_and_has_safe_limits(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "SISTER_NODE_URL=http://sister.local",
                "SISTER_SYNC_TOKEN=shared-secret",
                "ESTER_NODE_ID=ester-test",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_conversation_window.py",
            "--env-file",
            str(env_file),
            "--ledger-root",
            str(tmp_path / "ledger"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["policy"]["max_duration_sec"] == 900
    assert payload["policy"]["max_messages"] == 10
    assert payload["request"]["json"]["metadata"]["memory"] == "off"
    assert "shared-secret" not in result.stdout
    assert not (tmp_path / "ledger").exists()


def test_cli_send_fails_closed_without_window_confirm_or_flags(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "SISTER_NODE_URL=http://sister.local",
                "SISTER_SYNC_TOKEN=shared-secret",
                "ESTER_NODE_ID=ester-test",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_conversation_window.py",
            "--env-file",
            str(env_file),
            "--ledger-root",
            str(tmp_path / "ledger"),
            "--send",
        ],
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 2
    assert payload["ok"] is False
    assert payload["result"]["body"]["error"] == "send_gate_failed"
    assert "missing_confirm_phrase" in payload["result"]["body"]["problems"]
    assert "SISTER_CONVERSATION_WINDOW_not_enabled" in payload["result"]["body"]["problems"]
    assert "shared-secret" not in result.stdout
    assert not (tmp_path / "ledger").exists()


def test_cli_bootstraps_env_before_modules_imports():
    source = open("tools/synaps_conversation_window.py", encoding="utf-8").read()
    tree = ast.parse(source)
    unsafe_top_level_imports = [
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and (str(node.module or "").startswith("modules.") or str(node.module or "").startswith("tools."))
    ]

    assert unsafe_top_level_imports == []
    assert source.index("bootstrap_env_from_argv(raw_argv)") < source.index("from modules.synaps import")
