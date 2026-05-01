import json
import subprocess
import sys

from modules.synaps import (
    CODEX_MAILBOX_CONFIRM_PHRASE,
    CODEX_MAILBOX_RECEIPT_SCHEMA,
    SynapsConfig,
    SynapsMessageType,
    SynapsQuarantineStore,
    build_envelope,
    build_file_manifest,
    inspect_codex_mailbox_transfer,
    list_codex_mailbox_transfers,
    promote_codex_mailbox_transfer,
)


def _config() -> SynapsConfig:
    return SynapsConfig(
        node_url="http://sister.local",
        sync_token="shared-secret",
        node_id="ester-test",
    )


def _quarantine_transfer(tmp_path, *, transfer_id="transfer-1", kind="codex_contract", name="task.md", text="hello"):
    source = tmp_path / "source" / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(text, encoding="utf-8")
    manifest = build_file_manifest([source], include_payload=True, transfer_id=transfer_id, kind=kind)
    envelope = build_envelope(
        _config(),
        json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        SynapsMessageType.FILE_MANIFEST,
        message_id="incoming-1",
    )
    SynapsQuarantineStore(tmp_path / "quarantine").receive_manifest(envelope)
    return source


def test_inspect_accepts_codex_transfer_and_verifies_file_hash(tmp_path):
    source = _quarantine_transfer(tmp_path)

    record = inspect_codex_mailbox_transfer("transfer-1", tmp_path / "quarantine", tmp_path / "inbox")

    assert record["ok"] is True
    assert record["status"] == "ready"
    assert record["auto_execute"] is False
    assert record["auto_ingest"] is False
    assert record["memory"] == "off"
    assert record["files"][0]["kind"] == "codex_contract"
    assert record["files"][0]["actual_sha256"] == record["files"][0]["sha256"]
    assert source.name in record["files"][0]["path"]


def test_inspect_rejects_non_codex_kind(tmp_path):
    _quarantine_transfer(tmp_path, kind="log")

    record = inspect_codex_mailbox_transfer("transfer-1", tmp_path / "quarantine", tmp_path / "inbox")

    assert record["ok"] is False
    assert "kind_not_allowed:log" in record["problems"]


def test_promote_defaults_to_dry_run_and_writes_nothing(tmp_path):
    _quarantine_transfer(tmp_path)

    result = promote_codex_mailbox_transfer(
        "transfer-1",
        tmp_path / "quarantine",
        tmp_path / "inbox",
        tmp_path / "receipts" / "events.jsonl",
    )

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["result"]["status"] == "would_promote"
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / "receipts").exists()


def test_promote_requires_confirm_for_apply(tmp_path):
    _quarantine_transfer(tmp_path)

    result = promote_codex_mailbox_transfer(
        "transfer-1",
        tmp_path / "quarantine",
        tmp_path / "inbox",
        tmp_path / "receipts" / "events.jsonl",
        apply=True,
    )

    assert result["ok"] is False
    assert result["result"]["error"] == "promote_gate_failed"
    assert not (tmp_path / "inbox").exists()


def test_promote_apply_copies_to_inbox_and_appends_receipt(tmp_path):
    _quarantine_transfer(tmp_path, text="bridge task")
    ledger = tmp_path / "receipts" / "events.jsonl"

    result = promote_codex_mailbox_transfer(
        "transfer-1",
        tmp_path / "quarantine",
        tmp_path / "inbox",
        ledger,
        apply=True,
        confirm=CODEX_MAILBOX_CONFIRM_PHRASE,
        operator="test-operator",
    )

    inbox_file = tmp_path / "inbox" / "transfer-1" / "files" / "task.md"
    receipt = json.loads((tmp_path / "inbox" / "transfer-1" / "receipt.json").read_text(encoding="utf-8"))
    ledger_rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]

    assert result["ok"] is True
    assert result["dry_run"] is False
    assert inbox_file.read_text(encoding="utf-8") == "bridge task"
    assert receipt["schema"] == CODEX_MAILBOX_RECEIPT_SCHEMA
    assert receipt["auto_execute"] is False
    assert receipt["memory"] == "off"
    assert ledger_rows == [receipt]


def test_list_summarizes_ready_codex_transfers(tmp_path):
    _quarantine_transfer(tmp_path, transfer_id="transfer-a", kind="codex_report")

    listing = list_codex_mailbox_transfers(tmp_path / "quarantine", tmp_path / "inbox")

    assert listing["ok"] is True
    assert listing["count"] == 1
    assert listing["transfers"][0]["transfer_id"] == "transfer-a"
    assert listing["transfers"][0]["kinds"] == ["codex_report"]


def test_cli_promote_dry_run_is_default(tmp_path):
    _quarantine_transfer(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_mailbox.py",
            "promote",
            "--transfer-id",
            "transfer-1",
            "--quarantine-root",
            str(tmp_path / "quarantine"),
            "--inbox-root",
            str(tmp_path / "inbox"),
            "--receipt-ledger",
            str(tmp_path / "receipts" / "events.jsonl"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["result"]["status"] == "would_promote"
    assert not (tmp_path / "inbox").exists()
