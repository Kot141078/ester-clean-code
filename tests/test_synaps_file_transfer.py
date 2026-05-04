import ast
import base64
import json
import os
import subprocess
import sys

import pytest
from tools import synaps_file_transfer as transfer_cli

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


def test_cli_split_send_stops_after_first_failed_subsend(monkeypatch, tmp_path, capsys):
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
    calls = []

    def fake_send(request):
        calls.append(request)
        return {"ok": False, "status": 400, "body": {"message": "content_hash_mismatch"}}

    monkeypatch.setattr(transfer_cli, "send_prepared_request", fake_send)
    monkeypatch.setenv("SISTER_FILE_TRANSFER", "1")
    monkeypatch.setenv("SISTER_FILE_TRANSFER_ARMED", "1")
    monkeypatch.setenv("SISTER_AUTOCHAT", "0")

    rc = transfer_cli.main(
        [
            "--env-file",
            str(env_file),
            "--file",
            str(first),
            "--file",
            str(second),
            "--include-payload",
            "--split-files",
            "--send",
            "--confirm",
            FILE_TRANSFER_CONFIRM_PHRASE,
        ]
    )
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)

    assert rc == 2
    assert len(calls) == 1
    assert payload["ok"] is False
    assert payload["result"]["failed_index"] == 1
    assert len(payload["results"]) == 1
    assert "shared-secret" not in stdout


def test_cli_split_send_retries_transport_failure_then_continues(monkeypatch, tmp_path, capsys):
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
    calls = []
    sleeps = []

    def fake_send(request):
        calls.append(request)
        if len(calls) == 1:
            return {"ok": False, "status": 0, "body": {"error": "TimeoutError"}}
        return {"ok": True, "status": 200, "body": {"status": "quarantined"}}

    monkeypatch.setattr(transfer_cli, "send_prepared_request", fake_send)
    monkeypatch.setattr(transfer_cli.time, "sleep", lambda value: sleeps.append(value))
    monkeypatch.setenv("SISTER_FILE_TRANSFER", "1")
    monkeypatch.setenv("SISTER_FILE_TRANSFER_ARMED", "1")
    monkeypatch.setenv("SISTER_AUTOCHAT", "0")

    rc = transfer_cli.main(
        [
            "--env-file",
            str(env_file),
            "--file",
            str(first),
            "--file",
            str(second),
            "--include-payload",
            "--split-files",
            "--send-attempts",
            "2",
            "--send-retry-delay-sec",
            "0.1",
            "--send-delay-sec",
            "0.2",
            "--send",
            "--confirm",
            FILE_TRANSFER_CONFIRM_PHRASE,
        ]
    )
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)

    assert rc == 0
    assert len(calls) == 3
    assert payload["ok"] is True
    assert payload["send_policy"]["attempts"] == 2
    assert payload["results"][0]["attempt_count"] == 2
    assert [item["status"] for item in payload["results"][0]["attempts"]] == [0, 200]
    assert payload["results"][1]["attempt_count"] == 1
    assert sleeps == [0.1, 0.2]
    assert "shared-secret" not in stdout


def test_cli_split_send_does_not_retry_http_failure(monkeypatch, tmp_path, capsys):
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
    calls = []

    def fake_send(request):
        calls.append(request)
        return {"ok": False, "status": 400, "body": {"message": "content_hash_mismatch"}}

    monkeypatch.setattr(transfer_cli, "send_prepared_request", fake_send)
    monkeypatch.setenv("SISTER_FILE_TRANSFER", "1")
    monkeypatch.setenv("SISTER_FILE_TRANSFER_ARMED", "1")
    monkeypatch.setenv("SISTER_AUTOCHAT", "0")

    rc = transfer_cli.main(
        [
            "--env-file",
            str(env_file),
            "--file",
            str(first),
            "--file",
            str(second),
            "--include-payload",
            "--split-files",
            "--send-attempts",
            "3",
            "--send",
            "--confirm",
            FILE_TRANSFER_CONFIRM_PHRASE,
        ]
    )
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)

    assert rc == 2
    assert len(calls) == 1
    assert payload["result"]["failed_index"] == 1
    assert payload["results"][0]["attempt_count"] == 1
    assert [item["status"] for item in payload["results"][0]["attempts"]] == [400]
    assert "shared-secret" not in stdout


def test_cli_split_send_exhausts_transport_retries_before_stopping(monkeypatch, tmp_path, capsys):
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
    calls = []

    def fake_send(request):
        calls.append(request)
        return {"ok": False, "status": 0, "body": {"error": "TimeoutError"}}

    monkeypatch.setattr(transfer_cli, "send_prepared_request", fake_send)
    monkeypatch.setattr(transfer_cli.time, "sleep", lambda value: None)
    monkeypatch.setenv("SISTER_FILE_TRANSFER", "1")
    monkeypatch.setenv("SISTER_FILE_TRANSFER_ARMED", "1")
    monkeypatch.setenv("SISTER_AUTOCHAT", "0")

    rc = transfer_cli.main(
        [
            "--env-file",
            str(env_file),
            "--file",
            str(first),
            "--file",
            str(second),
            "--include-payload",
            "--split-files",
            "--send-attempts",
            "3",
            "--send",
            "--confirm",
            FILE_TRANSFER_CONFIRM_PHRASE,
        ]
    )
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)

    assert rc == 2
    assert len(calls) == 3
    assert payload["result"]["failed_index"] == 1
    assert len(payload["results"]) == 1
    assert payload["results"][0]["attempt_count"] == 3
    assert [item["status"] for item in payload["results"][0]["attempts"]] == [0, 0, 0]
    assert "shared-secret" not in stdout


def test_cli_chunk_files_dry_run_creates_index_and_chunks(tmp_path):
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
    source = tmp_path / "large.patch"
    source.write_text("a" * 600, encoding="utf-8")
    raw_payload = base64.b64encode(source.read_bytes()).decode("ascii")
    out_dir = tmp_path / "chunks-out"

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_file_transfer.py",
            "--env-file",
            str(env_file),
            "--file",
            str(source),
            "--kind",
            "codex_contract",
            "--note",
            "chunk smoke",
            "--chunk-files",
            "--chunk-bytes",
            "256",
            "--chunk-out-dir",
            str(out_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    index = json.loads((out_dir / "large.patch.chunk-index.json").read_text(encoding="utf-8"))

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["chunked"]["chunk_count"] == 3
    assert payload["transfer"]["split_files"] is True
    assert payload["transfer"]["manifest_count"] == 4
    assert index["source_size"] == 600
    assert index["chunk_count"] == 3
    assert (out_dir / "chunks" / "large.patch.part001of003").stat().st_size == 256
    assert raw_payload not in result.stdout
    assert "shared-secret" not in result.stdout


def test_cli_auto_chunk_bytes_avoids_large_chunk_index(tmp_path):
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
    source = tmp_path / "large.patch"
    source.write_text("a" * 28646, encoding="utf-8")
    out_dir = tmp_path / "chunks-out"

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_file_transfer.py",
            "--env-file",
            str(env_file),
            "--file",
            str(source),
            "--kind",
            "codex_contract",
            "--note",
            "auto chunk smoke",
            "--chunk-files",
            "--chunk-bytes",
            "1200",
            "--auto-chunk-bytes",
            "--chunk-index-target-bytes",
            "4096",
            "--chunk-out-dir",
            str(out_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    index_path = out_dir / "large.patch.chunk-index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))

    assert payload["ok"] is True
    assert payload["chunked"]["auto_chunk_bytes"] is True
    assert payload["chunked"]["requested_chunk_bytes"] == 1200
    assert payload["chunked"]["chunk_bytes"] == 3000
    assert payload["chunked"]["chunk_count"] == 10
    assert payload["chunked"]["index_size"] <= 4096
    assert payload["chunked"]["index_size"] <= payload["chunked"]["chunk_index_effective_target_bytes"]
    assert index["chunk_bytes"] == 3000
    assert index["chunk_count"] == 10
    assert index_path.stat().st_size <= 4096
    assert "shared-secret" not in result.stdout


def test_cli_auto_chunk_bytes_uses_realistic_index_id_headroom(tmp_path):
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
    source = tmp_path / "0001-feat-add-codex-gate-dashboard.patch"
    source.write_text("a" * 17175, encoding="utf-8")
    out_dir = tmp_path / "chunks-out"

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_file_transfer.py",
            "--env-file",
            str(env_file),
            "--file",
            str(source),
            "--kind",
            "codex_contract",
            "--note",
            "realistic index headroom",
            "--chunk-files",
            "--chunk-bytes",
            "1200",
            "--auto-chunk-bytes",
            "--chunk-index-target-bytes",
            "4096",
            "--chunk-out-dir",
            str(out_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["chunked"]["index_size"] <= payload["chunked"]["chunk_index_effective_target_bytes"]
    assert payload["chunked"]["index_size"] <= 4096
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
