import json
import os
import subprocess
import sys

from modules.synaps import (
    CODEX_PEER_ACTIVITY_CONFIRM_PHRASE,
    CodexPeerActivityPolicy,
    CodexPeerActivitySelectors,
    CodexReportSelector,
    SynapsConfig,
    SynapsMessageType,
    SynapsQuarantineStore,
    build_envelope,
    build_file_manifest,
    validate_codex_peer_activity_gate,
    watch_codex_peer_activity,
)


def _config(node_id="ester-test"):
    return SynapsConfig(node_url="http://sister.local", sync_token="shared-secret", node_id=node_id)


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


def _quarantine_report(
    tmp_path,
    *,
    transfer_id="synaps-file-report",
    name="report.md",
    text="# report\nsafe report body\n",
    sender="liah-test",
    note="",
):
    source = tmp_path / "source" / transfer_id / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(text, encoding="utf-8")
    manifest = build_file_manifest([source], include_payload=True, transfer_id=transfer_id, kind="codex_report", note=note)
    envelope = build_envelope(
        _config(sender),
        json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        SynapsMessageType.FILE_MANIFEST,
        message_id=transfer_id,
    )
    SynapsQuarantineStore(tmp_path / "quarantine").receive_manifest(envelope)
    file_record = manifest["files"][0]
    return {"sha256": file_record["sha256"], "size": file_record["size"], "transfer_id": transfer_id}


def _roots(tmp_path):
    return {
        "daemon_root": tmp_path / "daemon",
        "quarantine_root": tmp_path / "quarantine",
        "inbox_root": tmp_path / "inbox",
        "receipt_ledger": tmp_path / "receipts" / "events.jsonl",
        "request_root": tmp_path / "requests",
    }


def _selectors():
    return CodexPeerActivitySelectors(
        expected_report=CodexReportSelector(expected_name="expected.md", expected_sender="liah-test", note_contains="0107"),
        status_report=CodexReportSelector(expected_name="status.md", expected_sender="liah-test", note_contains="0107 status"),
    )


def test_peer_activity_gate_blocks_without_observe_flags():
    problems = validate_codex_peer_activity_gate({})

    assert "SYNAPS_CODEX_DAEMON_not_enabled" in problems
    assert "SYNAPS_CODEX_DAEMON_OBSERVE_REPORTS_not_enabled" in problems


def test_peer_activity_classifies_silence_without_writing(tmp_path):
    sleeps = []

    payload = watch_codex_peer_activity(
        selectors=_selectors(),
        env=_armed_env(),
        apply=True,
        confirm=CODEX_PEER_ACTIVITY_CONFIRM_PHRASE,
        policy=CodexPeerActivityPolicy(max_cycles=2, sleep_sec=0.01),
        sleep_fn=sleeps.append,
        **_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["matched"] is False
    assert payload["result"]["status"] == "peer_silent"
    assert payload["cycle_count"] == 2
    assert sleeps == [0.01]
    assert not (tmp_path / "daemon").exists()
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / "requests").exists()


def test_peer_activity_observes_expected_report(tmp_path):
    _quarantine_report(tmp_path, transfer_id="synaps-file-expected", name="expected.md", note="0107 report")

    payload = watch_codex_peer_activity(
        selectors=_selectors(),
        env=_armed_env(),
        apply=True,
        confirm=CODEX_PEER_ACTIVITY_CONFIRM_PHRASE,
        policy=CodexPeerActivityPolicy(max_cycles=2, sleep_sec=0),
        **_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["branch"] == "expected_report"
    assert payload["selected_transfer_id"] == "synaps-file-expected"
    assert payload["result"]["status"] == "expected_report_observed"
    assert (tmp_path / "daemon" / "promote_seen" / "synaps-file-expected.json").is_file()
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / "requests").exists()


def test_peer_activity_observes_status_report(tmp_path):
    _quarantine_report(tmp_path, transfer_id="synaps-file-status", name="status.md", note="0107 status idle")

    payload = watch_codex_peer_activity(
        selectors=_selectors(),
        env=_armed_env(),
        apply=True,
        confirm=CODEX_PEER_ACTIVITY_CONFIRM_PHRASE,
        policy=CodexPeerActivityPolicy(max_cycles=1, sleep_sec=0),
        **_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["branch"] == "status_report"
    assert payload["selected_transfer_id"] == "synaps-file-status"
    assert payload["result"]["status"] == "peer_status_observed"
    assert (tmp_path / "daemon" / "promote_seen" / "synaps-file-status.json").is_file()
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / "requests").exists()


def test_peer_activity_fails_closed_when_report_and_status_both_match(tmp_path):
    _quarantine_report(tmp_path, transfer_id="synaps-file-expected", name="expected.md", note="0107 report")
    _quarantine_report(tmp_path, transfer_id="synaps-file-status", name="status.md", note="0107 status idle")

    payload = watch_codex_peer_activity(
        selectors=_selectors(),
        env=_armed_env(),
        apply=True,
        confirm=CODEX_PEER_ACTIVITY_CONFIRM_PHRASE,
        policy=CodexPeerActivityPolicy(max_cycles=1, sleep_sec=0),
        **_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "peer_activity_ambiguous"
    assert "multiple_peer_activity_branches_matched" in payload["problems"]
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-expected.json").exists()
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-status.json").exists()


def test_cli_peer_activity_writes_status_artifact(tmp_path):
    env = os.environ.copy()
    env.update(_armed_env())
    status_out = tmp_path / "status" / "peer.md"

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_peer_activity.py",
            "--env-file",
            "",
            "--expect-report-name",
            "expected.md",
            "--expect-report-sender",
            "liah-test",
            "--expect-report-note-contains",
            "0107",
            "--status-name",
            "status.md",
            "--status-sender",
            "liah-test",
            "--status-note-contains",
            "0107 status",
            "--daemon-root",
            str(tmp_path / "daemon"),
            "--quarantine-root",
            str(tmp_path / "quarantine"),
            "--inbox-root",
            str(tmp_path / "inbox"),
            "--request-root",
            str(tmp_path / "requests"),
            "--max-cycles",
            "1",
            "--sleep-sec",
            "0",
            "--status-out",
            str(status_out),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["result"]["status"] == "peer_silent"
    assert "peer_silent" in status_out.read_text(encoding="utf-8")
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / "requests").exists()
