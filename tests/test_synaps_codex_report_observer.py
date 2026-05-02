import json
import os
import subprocess
import sys

from modules.synaps import (
    CODEX_REPORT_OBSERVER_CONFIRM_PHRASE,
    SynapsConfig,
    SynapsMessageType,
    SynapsQuarantineStore,
    build_envelope,
    build_file_manifest,
    observe_expected_codex_report,
    validate_codex_report_observer_gate,
)


def _config() -> SynapsConfig:
    return SynapsConfig(node_url="http://sister.local", sync_token="shared-secret", node_id="ester-test")


def _armed_env(**extra):
    env = {
        "SYNAPS_CODEX_DAEMON": "1",
        "SYNAPS_CODEX_DAEMON_ARMED": "1",
        "SYNAPS_CODEX_DAEMON_OBSERVE_REPORTS": "1",
        "SYNAPS_CODEX_DAEMON_OBSERVE_REPORTS_ARMED": "1",
        "SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX": "0",
        "SYNAPS_CODEX_DAEMON_ENQUEUE_HANDOFFS": "0",
        "SYNAPS_CODEX_DAEMON_RUNNER": "0",
        "SYNAPS_CODEX_DAEMON_RUNNER_ARMED": "0",
        "SISTER_AUTOCHAT": "0",
    }
    env.update(extra)
    return env


def _quarantine_report(tmp_path, *, transfer_id="synaps-file-report"):
    source = tmp_path / "source" / "report.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# report\nsafe report body\n", encoding="utf-8")
    manifest = build_file_manifest([source], include_payload=True, transfer_id=transfer_id, kind="codex_report")
    envelope = build_envelope(
        _config(),
        json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        SynapsMessageType.FILE_MANIFEST,
        message_id="incoming-report",
    )
    SynapsQuarantineStore(tmp_path / "quarantine").receive_manifest(envelope)


def _observer_roots(tmp_path):
    return {
        "daemon_root": tmp_path / "daemon",
        "quarantine_root": tmp_path / "quarantine",
        "inbox_root": tmp_path / "inbox",
        "receipt_ledger": tmp_path / "receipts" / "events.jsonl",
        "request_root": tmp_path / "requests",
    }


def test_report_observer_gate_blocks_unsafe_flags():
    assert validate_codex_report_observer_gate(_armed_env()) == []
    problems = validate_codex_report_observer_gate(_armed_env(SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX="1"))

    assert "SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX_must_remain_disabled" in problems


def test_report_observer_dry_run_matches_without_writing(tmp_path):
    _quarantine_report(tmp_path)

    payload = observe_expected_codex_report(
        expected_transfer_id="synaps-file-report",
        env=_armed_env(),
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["matched"] is True
    assert payload["preview"]["actions"][0]["transfer_id"] == "synaps-file-report"
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").exists()


def test_report_observer_apply_requires_confirm(tmp_path):
    _quarantine_report(tmp_path)

    payload = observe_expected_codex_report(
        expected_transfer_id="synaps-file-report",
        env=_armed_env(),
        apply=True,
        confirm="",
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "gate_failed"
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").exists()


def test_report_observer_apply_fails_closed_on_transfer_mismatch(tmp_path):
    _quarantine_report(tmp_path)

    payload = observe_expected_codex_report(
        expected_transfer_id="synaps-file-other",
        env=_armed_env(),
        apply=True,
        confirm=CODEX_REPORT_OBSERVER_CONFIRM_PHRASE,
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "expected_transfer_mismatch"
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").exists()


def test_report_observer_apply_marks_expected_report_only(tmp_path):
    _quarantine_report(tmp_path)

    payload = observe_expected_codex_report(
        expected_transfer_id="synaps-file-report",
        env=_armed_env(),
        apply=True,
        confirm=CODEX_REPORT_OBSERVER_CONFIRM_PHRASE,
        **_observer_roots(tmp_path),
    )
    repeat = observe_expected_codex_report(
        expected_transfer_id="synaps-file-report",
        env=_armed_env(),
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["result"]["status"] == "report_observed"
    assert (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").is_file()
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / "requests").exists()
    assert repeat["matched"] is False
    assert repeat["preview"]["actions"] == []


def test_cli_report_observer_apply(tmp_path):
    _quarantine_report(tmp_path)
    env = os.environ.copy()
    env.update(_armed_env())

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_report_observer.py",
            "--env-file",
            "",
            "--expect-transfer-id",
            "synaps-file-report",
            "--daemon-root",
            str(tmp_path / "daemon"),
            "--quarantine-root",
            str(tmp_path / "quarantine"),
            "--inbox-root",
            str(tmp_path / "inbox"),
            "--request-root",
            str(tmp_path / "requests"),
            "--apply",
            "--confirm",
            CODEX_REPORT_OBSERVER_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["result"]["status"] == "report_observed"
    assert (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").is_file()
