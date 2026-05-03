import json
import os
import subprocess
import sys

from modules.synaps import (
    CODEX_COORDINATION_SCANNER_CONFIRM_PHRASE,
    CODEX_COORDINATION_SCANNER_MARK_CONFIRM_PHRASE,
    CodexCoordinationScannerPolicy,
    CodexCoordinationSelector,
    SynapsConfig,
    SynapsMessageType,
    SynapsQuarantineStore,
    build_envelope,
    build_file_manifest,
    scan_codex_coordination_message,
    validate_codex_coordination_scanner_gate,
)


def _config(node_id="ester-test") -> SynapsConfig:
    return SynapsConfig(node_url="http://sister.local", sync_token="shared-secret", node_id=node_id)


def _armed_env(**extra):
    env = {
        "SYNAPS_CODEX_COORDINATION_SCANNER": "1",
        "SYNAPS_CODEX_COORDINATION_SCANNER_ARMED": "1",
        "SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX": "0",
        "SYNAPS_CODEX_DAEMON_ENQUEUE_HANDOFFS": "0",
        "SYNAPS_CODEX_DAEMON_RUNNER": "0",
        "SYNAPS_CODEX_DAEMON_RUNNER_ARMED": "0",
        "SYNAPS_CODEX_DAEMON_PERSISTENT": "0",
        "SYNAPS_CODEX_DAEMON_PERSISTENT_ARMED": "0",
        "SISTER_AUTOCHAT": "0",
    }
    env.update(extra)
    return env


def _roots(tmp_path):
    return {
        "scanner_root": tmp_path / "scanner",
        "quarantine_root": tmp_path / "quarantine",
        "inbox_root": tmp_path / "inbox",
    }


def _quarantine_coordination_file(
    tmp_path,
    *,
    transfer_id="synaps-file-coordination",
    name="expected.md",
    kind="codex_contract",
    text="# expected\nsafe body\n",
    sender="liah-test",
    note="0062 coordination",
):
    source = tmp_path / "source" / transfer_id / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(text, encoding="utf-8")
    manifest = build_file_manifest([source], include_payload=True, transfer_id=transfer_id, kind=kind, note=note)
    envelope = build_envelope(
        _config(sender),
        json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        SynapsMessageType.FILE_MANIFEST,
        message_id=f"incoming-{transfer_id}",
    )
    SynapsQuarantineStore(tmp_path / "quarantine").receive_manifest(envelope)


def test_coordination_scanner_gate_blocks_unsafe_flags():
    assert validate_codex_coordination_scanner_gate(_armed_env(), confirm=CODEX_COORDINATION_SCANNER_CONFIRM_PHRASE) == []

    problems = validate_codex_coordination_scanner_gate(
        _armed_env(SYNAPS_CODEX_DAEMON_PERSISTENT="1"),
        confirm=CODEX_COORDINATION_SCANNER_CONFIRM_PHRASE,
    )

    assert "SYNAPS_CODEX_DAEMON_PERSISTENT_must_remain_disabled" in problems


def test_coordination_scanner_dry_run_waits_bounded_cycles_without_writing(tmp_path):
    sleeps = []

    payload = scan_codex_coordination_message(
        selector=CodexCoordinationSelector(expected_name="expected.md", expected_kind="codex_contract"),
        env=_armed_env(),
        confirm=CODEX_COORDINATION_SCANNER_CONFIRM_PHRASE,
        policy=CodexCoordinationScannerPolicy(max_cycles=2, sleep_sec=0.01),
        sleep_fn=sleeps.append,
        **_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["matched"] is False
    assert payload["cycle_count"] == 2
    assert payload["result"]["status"] == "not_found"
    assert sleeps == [0.01]
    assert not (tmp_path / "scanner").exists()
    assert not (tmp_path / "inbox").exists()


def test_coordination_scanner_detects_delayed_contract_without_writing(tmp_path):
    sleeps = []

    def delayed_contract_sleep(seconds):
        sleeps.append(seconds)
        _quarantine_coordination_file(tmp_path, transfer_id="synaps-file-delayed", name="expected.md", note="0062 delayed")

    payload = scan_codex_coordination_message(
        selector=CodexCoordinationSelector(expected_name="expected.md", expected_kind="codex_contract", note_contains="0062"),
        env=_armed_env(),
        confirm=CODEX_COORDINATION_SCANNER_CONFIRM_PHRASE,
        policy=CodexCoordinationScannerPolicy(max_cycles=2, sleep_sec=0.01),
        sleep_fn=delayed_contract_sleep,
        **_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["matched"] is True
    assert payload["cycle_count"] == 2
    assert payload["selected_transfer_id"] == "synaps-file-delayed"
    assert payload["cycles"][0]["candidate_count"] == 0
    assert payload["cycles"][1]["candidate_count"] == 1
    assert sleeps == [0.01]
    assert not (tmp_path / "scanner").exists()
    assert not (tmp_path / "inbox").exists()


def test_coordination_scanner_mark_seen_and_repeat_skips_seen(tmp_path):
    _quarantine_coordination_file(tmp_path, transfer_id="synaps-file-target", name="expected.md", sender="liah-test", note="0062 mark")

    payload = scan_codex_coordination_message(
        selector=CodexCoordinationSelector(expected_name="expected.md", expected_kind="codex_contract", expected_sender="liah-test"),
        env=_armed_env(),
        mark_seen=True,
        confirm=CODEX_COORDINATION_SCANNER_MARK_CONFIRM_PHRASE,
        policy=CodexCoordinationScannerPolicy(max_cycles=1, sleep_sec=0),
        **_roots(tmp_path),
    )
    repeat = scan_codex_coordination_message(
        selector=CodexCoordinationSelector(expected_name="expected.md", expected_kind="codex_contract", expected_sender="liah-test"),
        env=_armed_env(),
        confirm=CODEX_COORDINATION_SCANNER_CONFIRM_PHRASE,
        policy=CodexCoordinationScannerPolicy(max_cycles=1, sleep_sec=0),
        **_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["result"]["status"] == "scanner_seen"
    assert (tmp_path / "scanner" / "seen" / "synaps-file-target.json").is_file()
    assert not (tmp_path / "inbox").exists()
    assert repeat["ok"] is True
    assert repeat["matched"] is False
    assert repeat["cycles"][0]["candidate_count"] == 0


def test_coordination_scanner_fails_closed_on_multiple_candidates(tmp_path):
    _quarantine_coordination_file(tmp_path, transfer_id="synaps-file-a", name="expected.md", note="0062 duplicate")
    _quarantine_coordination_file(tmp_path, transfer_id="synaps-file-b", name="expected.md", note="0062 duplicate")

    payload = scan_codex_coordination_message(
        selector=CodexCoordinationSelector(expected_name="expected.md", expected_kind="codex_contract", note_contains="0062"),
        env=_armed_env(),
        mark_seen=True,
        confirm=CODEX_COORDINATION_SCANNER_MARK_CONFIRM_PHRASE,
        policy=CodexCoordinationScannerPolicy(max_cycles=1, sleep_sec=0),
        **_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "selector_mismatch"
    assert "expected_zero_or_one_coordination_candidate:2" in payload["problems"]
    assert not (tmp_path / "scanner" / "seen" / "synaps-file-a.json").exists()
    assert not (tmp_path / "scanner" / "seen" / "synaps-file-b.json").exists()
    assert not (tmp_path / "inbox").exists()


def test_cli_coordination_scanner_mark_seen(tmp_path):
    _quarantine_coordination_file(tmp_path, transfer_id="synaps-file-cli", name="expected.md", sender="liah-test")
    env = os.environ.copy()
    env.update(_armed_env())

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_coordination_scanner.py",
            "--env-file",
            "",
            "--expect-name",
            "expected.md",
            "--expect-kind",
            "codex_contract",
            "--expect-sender",
            "liah-test",
            "--scanner-root",
            str(tmp_path / "scanner"),
            "--quarantine-root",
            str(tmp_path / "quarantine"),
            "--inbox-root",
            str(tmp_path / "inbox"),
            "--max-cycles",
            "1",
            "--sleep-sec",
            "0",
            "--mark-seen",
            "--confirm",
            CODEX_COORDINATION_SCANNER_MARK_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["selected_transfer_id"] == "synaps-file-cli"
    assert payload["result"]["status"] == "scanner_seen"
    assert (tmp_path / "scanner" / "seen" / "synaps-file-cli.json").is_file()
