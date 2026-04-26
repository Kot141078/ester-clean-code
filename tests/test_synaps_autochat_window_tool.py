import json
import subprocess
import sys

from modules.synaps import SynapsConfig
from tools.synaps_autochat_window import (
    CONFIRM_PHRASE,
    arm_status,
    build_window_request,
    validate_send_gate,
)


def test_window_request_uses_oneshot_memory_off_metadata():
    config = SynapsConfig(
        node_url="http://sister.local",
        sync_token="shared-secret",
        node_id="ester-test",
    )

    request = build_window_request(config, content="bounded hello")

    assert request.url == "http://sister.local/sister/inbound"
    assert request.json["type"] == "thought_request"
    assert request.json["content"] == "bounded hello"
    assert request.json["metadata"]["autochat_window"] == "oneshot"
    assert request.json["metadata"]["memory"] == "off"
    assert request.json["metadata"]["operator_window"] is True


def test_send_gate_requires_confirm_and_all_three_arm_flags():
    env = {
        "SISTER_AUTOCHAT": "1",
        "SISTER_AUTOCHAT_ARMED": "1",
        "SISTER_AUTOCHAT_ONESHOT": "1",
    }

    assert arm_status(env) == {"autochat": True, "armed": True, "oneshot": True}
    assert validate_send_gate(env, CONFIRM_PHRASE) == []
    assert "missing_confirm_phrase" in validate_send_gate(env, "")
    assert "SISTER_AUTOCHAT_ARMED_not_enabled" in validate_send_gate(
        {"SISTER_AUTOCHAT": "1", "SISTER_AUTOCHAT_ONESHOT": "1"},
        CONFIRM_PHRASE,
    )


def test_cli_dry_run_redacts_token_and_does_not_require_arm_flags(tmp_path):
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
            "tools/synaps_autochat_window.py",
            "--env-file",
            str(env_file),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["arm_status"] == {"autochat": False, "armed": False, "oneshot": False}
    assert payload["request"]["json"]["metadata"]["memory"] == "off"
    assert "shared-secret" not in result.stdout


def test_cli_send_fails_closed_without_arm_flags_or_confirm(tmp_path):
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
            "tools/synaps_autochat_window.py",
            "--env-file",
            str(env_file),
            "--send",
        ],
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 2
    assert payload["ok"] is False
    assert payload["result"]["body"]["error"] == "send_gate_failed"
    assert "SISTER_AUTOCHAT_ARMED_not_enabled" in payload["result"]["body"]["problems"]
    assert "shared-secret" not in result.stdout
