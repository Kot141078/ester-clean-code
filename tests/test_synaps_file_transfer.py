import ast
import base64
import json
import os
import subprocess
import sys

import pytest

from modules.synaps import (
    FILE_TRANSFER_CONFIRM_PHRASE,
    FileTransferPolicy,
    SynapsConfig,
    SynapsMessageType,
    SynapsQuarantineStore,
    SynapsValidationError,
    build_envelope,
    build_file_manifest,
    build_file_manifest_request,
    file_transfer_arm_status,
    handle_inbound_payload,
    parse_file_manifest,
    validate_file_transfer_send_gate,
)


def _config() -> SynapsConfig:
    return SynapsConfig(
        node_url="http://sister.local",
        sync_token="shared-secret",
        node_id="ester-test",
    )


def test_build_manifest_defaults_to_metadata_only_and_hides_absolute_paths(tmp_path):
    source = tmp_path / "logs" / "ester.log"
    source.parent.mkdir()
    source.write_text("status line\n", encoding="utf-8")

    manifest = build_file_manifest([source], transfer_id="transfer-1", kind="log")

    assert manifest["schema"] == "ester.synaps.file_manifest.v1"
    assert manifest["mode"] == "manifest_only"
    assert manifest["auto_ingest"] is False
    assert manifest["memory"] == "off"
    assert manifest["files"][0]["name"] == "ester.log"
    assert manifest["files"][0]["kind"] == "log"
    assert manifest["files"][0]["payload_encoding"] == "none"
    assert "payload_b64" not in manifest["files"][0]
    assert str(tmp_path) not in json.dumps(manifest)


def test_build_manifest_request_uses_file_manifest_type_and_memory_off(tmp_path):
    source = tmp_path / "report.txt"
    source.write_text("hello", encoding="utf-8")
    manifest = build_file_manifest([source], include_payload=True, transfer_id="transfer-2")

    request = build_file_manifest_request(_config(), manifest)

    assert request.url == "http://sister.local/sister/inbound"
    assert request.json["type"] == "file_manifest"
    assert request.json["metadata"]["mode"] == "synaps_file_transfer"
    assert request.json["metadata"]["memory"] == "off"
    assert request.json["metadata"]["auto_ingest"] is False
    assert request.json["metadata"]["file_count"] == 1


def test_multi_file_manifest_request_round_trips_through_inbound_parser(tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("alpha", encoding="utf-8")
    second.write_text("beta", encoding="utf-8")
    manifest = build_file_manifest([first, second], include_payload=True, transfer_id="transfer-multi")

    request = build_file_manifest_request(_config(), manifest)
    response = handle_inbound_payload(
        request.json,
        _config(),
        file_manifest_handler=lambda incoming: SynapsQuarantineStore(tmp_path / "quarantine").receive_manifest(incoming),
    )

    assert response.status_code == 200
    assert response.body["status"] == "quarantined"
    assert response.body["file_transfer"]["file_count"] == 2
    assert response.body["file_transfer"]["written_count"] == 2


def test_file_transfer_gate_requires_explicit_arm_and_no_autochat():
    env = {
        "SISTER_FILE_TRANSFER": "1",
        "SISTER_FILE_TRANSFER_ARMED": "1",
        "SISTER_AUTOCHAT": "0",
    }

    assert file_transfer_arm_status(env)["file_transfer"] is True
    assert validate_file_transfer_send_gate(env, FILE_TRANSFER_CONFIRM_PHRASE) == []

    problems = validate_file_transfer_send_gate(
        {**env, "SISTER_AUTOCHAT": "1", "SISTER_CONVERSATION_WINDOW": "1"},
        FILE_TRANSFER_CONFIRM_PHRASE,
    )

    assert "SISTER_AUTOCHAT_must_remain_disabled" in problems
    assert "SISTER_CONVERSATION_WINDOW_must_remain_disabled" in problems


def test_quarantine_store_writes_payload_without_auto_ingest(tmp_path):
    source = tmp_path / "safe.txt"
    source.write_text("quarantine me", encoding="utf-8")
    manifest = build_file_manifest([source], include_payload=True, transfer_id="transfer-3")
    envelope = build_envelope(
        _config(),
        json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        SynapsMessageType.FILE_MANIFEST,
        message_id="incoming-file-1",
    )

    result = SynapsQuarantineStore(tmp_path / "quarantine").receive_manifest(envelope)
    stored_manifest = json.loads((tmp_path / "quarantine" / "transfer-3" / "manifest.json").read_text(encoding="utf-8"))

    assert result["status"] == "quarantined"
    assert result["written_count"] == 1
    assert (tmp_path / "quarantine" / "transfer-3" / "files" / "safe.txt").read_text(encoding="utf-8") == "quarantine me"
    assert stored_manifest["auto_ingest"] is False
    assert stored_manifest["memory"] == "off"
    assert stored_manifest["files"][0]["payload_b64"] == "<quarantined>"


def test_quarantine_rejects_path_traversal(tmp_path):
    payload = base64.b64encode(b"evil").decode("ascii")
    manifest = {
        "schema": "ester.synaps.file_manifest.v1",
        "transfer_id": "bad",
        "auto_ingest": False,
        "memory": "off",
        "files": [
            {
                "name": "../escape.txt",
                "size": 4,
                "sha256": "b5c1fb2efc6d6b4674c2fdcc48ce01b43a3b7c03763c0c3355de0099ee0f8c73",
                "payload_encoding": "base64",
                "payload_b64": payload,
            }
        ],
    }

    with pytest.raises(SynapsValidationError):
        parse_file_manifest(json.dumps(manifest), FileTransferPolicy())


def test_adapter_quarantines_file_manifest_with_injected_handler(tmp_path):
    source = tmp_path / "handoff.txt"
    source.write_text("hello sister", encoding="utf-8")
    manifest = build_file_manifest([source], include_payload=True, transfer_id="transfer-4")
    envelope = build_envelope(
        _config(),
        json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        SynapsMessageType.FILE_MANIFEST,
        message_id="incoming-file-2",
    )
    payload = build_file_manifest_request(_config(), manifest).json
    payload["message_id"] = envelope.message_id

    response = handle_inbound_payload(
        payload,
        _config(),
        file_manifest_handler=lambda incoming: SynapsQuarantineStore(tmp_path / "quarantine").receive_manifest(incoming),
    )

    assert response.status_code == 200
    assert response.reason == "file_manifest"
    assert response.body["status"] == "quarantined"
    assert response.body["file_transfer"]["written_count"] == 1
    assert "shared-secret" not in str(response.body)


def test_cli_dry_run_redacts_token_and_embedded_payload(tmp_path):
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
    source = tmp_path / "report.txt"
    source.write_text("secret-transfer-payload", encoding="utf-8")
    raw_payload = base64.b64encode(source.read_bytes()).decode("ascii")

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_file_transfer.py",
            "--env-file",
            str(env_file),
            "--file",
            str(source),
            "--include-payload",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["transfer"]["mode"] == "inline_quarantine"
    assert "shared-secret" not in result.stdout
    assert raw_payload not in result.stdout
    assert "<redacted base64 len=" in result.stdout


def test_cli_split_files_dry_run_builds_single_file_manifests_and_redacts_payloads(tmp_path):
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
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("alpha", encoding="utf-8")
    second.write_text("beta", encoding="utf-8")
    first_payload = base64.b64encode(first.read_bytes()).decode("ascii")
    second_payload = base64.b64encode(second.read_bytes()).decode("ascii")

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_file_transfer.py",
            "--env-file",
            str(env_file),
            "--file",
            str(first),
            "--file",
            str(second),
            "--include-payload",
            "--split-files",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["transfer"]["split_files"] is True
    assert payload["transfer"]["manifest_count"] == 2
    assert len(payload["transfers"]) == 2
    assert all(item["file_count"] == 1 for item in payload["transfers"])
    assert first_payload not in result.stdout
    assert second_payload not in result.stdout
    assert "shared-secret" not in result.stdout


def test_cli_live_multi_file_send_fails_closed_without_split_or_override(tmp_path):
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
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("alpha", encoding="utf-8")
    second.write_text("beta", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_file_transfer.py",
            "--env-file",
            str(env_file),
            "--file",
            str(first),
            "--file",
            str(second),
            "--include-payload",
            "--send",
            "--confirm",
            FILE_TRANSFER_CONFIRM_PHRASE,
        ],
        env={
            **os.environ,
            "SISTER_FILE_TRANSFER": "1",
            "SISTER_FILE_TRANSFER_ARMED": "1",
            "SISTER_AUTOCHAT": "0",
        },
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 2
    assert payload["ok"] is False
    assert payload["result"]["body"]["error"] == "send_gate_failed"
    assert "multi_file_envelope_blocked_use_split_files_or_explicit_override" in payload["result"]["body"]["problems"]
    assert "shared-secret" not in result.stdout


def test_cli_send_fails_closed_without_file_transfer_flags(tmp_path):
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
    source = tmp_path / "report.txt"
    source.write_text("hello", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_file_transfer.py",
            "--env-file",
            str(env_file),
            "--file",
            str(source),
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
    assert "SISTER_FILE_TRANSFER_not_enabled" in payload["result"]["body"]["problems"]
    assert "shared-secret" not in result.stdout


def test_cli_bootstraps_env_before_modules_imports():
    source = open("tools/synaps_file_transfer.py", encoding="utf-8").read()
    tree = ast.parse(source)
    unsafe_top_level_imports = [
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and (str(node.module or "").startswith("modules.") or str(node.module or "").startswith("tools."))
    ]

    main_start = source.index("def main(")
    main_synaps_import = source.index("from modules.synaps import (", main_start)

    assert unsafe_top_level_imports == []
    assert source.index("bootstrap_env_from_argv(raw_argv)", main_start) < main_synaps_import
