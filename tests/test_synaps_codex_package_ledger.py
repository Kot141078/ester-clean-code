import json
import subprocess
import sys

from modules.synaps import (
    CODEX_PACKAGE_LEDGER_CONFIRM_PHRASE,
    CodexPackageExpectedReport,
    build_codex_package_ledger,
    render_codex_package_ledger_markdown,
    validate_codex_package_ledger_write_gate,
    write_codex_package_ledger,
)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _send_output(*, ok=True, transfer_id="synaps-file-one", status=200):
    return {
        "ok": ok,
        "dry_run": False,
        "transfer": {
            "transfer_id": transfer_id,
            "mode": "inline_quarantine",
            "file_count": 1,
            "total_bytes": 123,
            "manifest_count": 1,
            "memory": "off",
            "auto_ingest": False,
        },
        "result": {"ok": ok, "status": status, "body": {"file_transfer": {"written_count": 1}}},
    }


def _chunk_output():
    return {
        "ok": True,
        "dry_run": False,
        "chunked": {
            "schema": "ester.synaps.file_transfer_chunks.v1",
            "transfer_id": "synaps-chunks-one",
            "source_name": "patch.patch",
            "source_sha256": "abc",
            "source_size": 4096,
            "requested_chunk_bytes": 1200,
            "chunk_bytes": 4096,
            "chunk_count": 1,
            "index_size": 900,
            "auto_chunk_bytes": True,
        },
        "transfer": {"manifest_count": 2},
        "transfers": [
            {"transfer_id": "synaps-file-index", "mode": "inline_quarantine", "file_count": 1, "total_bytes": 900},
            {"transfer_id": "synaps-file-part", "mode": "inline_quarantine", "file_count": 1, "total_bytes": 4096},
        ],
        "results": [{"ok": True, "status": 200}, {"ok": True, "status": 200}],
    }


def test_package_ledger_builds_from_single_and_chunk_outputs(tmp_path):
    first = _write_json(tmp_path / "send-one.json", _send_output())
    chunks = _write_json(tmp_path / "send-chunks.json", _chunk_output())
    peer = _write_json(tmp_path / "peer.json", {"ok": True, "matched": False, "cycle_count": 1, "result": {"status": "peer_silent"}})

    ledger = build_codex_package_ledger(
        front_id="0108 package",
        transfer_output_paths=[first, chunks],
        expected_report=CodexPackageExpectedReport(name="REPORT.md", note_contains="0108"),
        peer_activity_path=peer,
    )

    assert ledger["ok"] is True
    assert ledger["front_id"] == "0108_package"
    assert ledger["status"] == "waiting_peer_silent"
    assert ledger["transfer_output_count"] == 2
    assert ledger["transfer_record_count"] == 3
    assert ledger["transfer_outputs"][1]["chunked"]["chunk_bytes"] == 4096
    assert ledger["transfers"][0]["transfer_id"] == "synaps-file-one"


def test_package_ledger_classifies_send_failure(tmp_path):
    first = _write_json(tmp_path / "send-one.json", _send_output(ok=False, status=500))

    ledger = build_codex_package_ledger(front_id="0108", transfer_output_paths=[first])

    assert ledger["ok"] is False
    assert ledger["status"] == "send_failed"


def test_package_ledger_write_requires_confirm(tmp_path):
    ledger = build_codex_package_ledger(front_id="0108", transfer_output_paths=[])
    result = write_codex_package_ledger(
        ledger=ledger,
        out_json=tmp_path / "ledger.json",
        out_md=tmp_path / "ledger.md",
        apply=True,
        confirm="",
    )

    assert result["ok"] is False
    assert result["result"]["status"] == "gate_failed"
    assert not (tmp_path / "ledger.json").exists()
    assert not (tmp_path / "ledger.md").exists()


def test_package_ledger_write_creates_json_and_markdown(tmp_path):
    ledger = build_codex_package_ledger(front_id="0108", transfer_output_paths=[])
    result = write_codex_package_ledger(
        ledger=ledger,
        out_json=tmp_path / "ledger.json",
        out_md=tmp_path / "ledger.md",
        apply=True,
        confirm=CODEX_PACKAGE_LEDGER_CONFIRM_PHRASE,
    )

    assert result["ok"] is True
    assert result["result"]["status"] == "ledger_written"
    assert json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))["front_id"] == "0108"
    assert "SYNAPS Codex Package Ledger" in (tmp_path / "ledger.md").read_text(encoding="utf-8")


def test_package_ledger_markdown_lists_transfers(tmp_path):
    first = _write_json(tmp_path / "send-one.json", _send_output())
    ledger = build_codex_package_ledger(front_id="0108", transfer_output_paths=[first])

    markdown = render_codex_package_ledger_markdown(ledger)

    assert "synaps-file-one" in markdown
    assert "Safety: ledger only" in markdown


def test_cli_package_ledger_write(tmp_path):
    first = _write_json(tmp_path / "send-one.json", _send_output())
    out_json = tmp_path / "out" / "ledger.json"
    out_md = tmp_path / "out" / "ledger.md"

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_package_ledger.py",
            "--front-id",
            "0108",
            "--transfer-output",
            str(first),
            "--expected-report-name",
            "REPORT.md",
            "--expected-report-note-contains",
            "0108",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--write",
            "--confirm",
            CODEX_PACKAGE_LEDGER_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["ledger"]["status"] == "sent_waiting_report"
    assert out_json.is_file()
    assert out_md.is_file()


def test_package_ledger_write_gate_allows_dry_run():
    assert validate_codex_package_ledger_write_gate() == []
