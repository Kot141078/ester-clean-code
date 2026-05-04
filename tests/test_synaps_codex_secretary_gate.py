import json
import os
import subprocess
import sys

from modules.synaps import (
    CODEX_SECRETARY_GATE_CONFIRM_PHRASE,
    CodexCoordinationSelector,
    CodexSecretaryResponsePolicy,
    CodexSecretaryResponseSelectors,
    SynapsConfig,
    SynapsMessageType,
    SynapsQuarantineStore,
    build_envelope,
    build_file_manifest,
    run_codex_secretary_response_gate,
    validate_codex_secretary_gate,
)


def _config(node_id="liah-test") -> SynapsConfig:
    return SynapsConfig(node_url="http://sister.local", sync_token="shared-secret", node_id=node_id)


def _armed_env(**extra):
    env = {
        "SYNAPS_CODEX_SECRETARY_GATE": "1",
        "SYNAPS_CODEX_SECRETARY_GATE_ARMED": "1",
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
        "secretary_root": tmp_path / "secretary",
        "scanner_root": tmp_path / "scanner",
        "quarantine_root": tmp_path / "quarantine",
        "inbox_root": tmp_path / "inbox",
    }


def _selectors(marker="secretary-marker"):
    return CodexSecretaryResponseSelectors(
        next_work=CodexCoordinationSelector(
            expected_name="TO_ESTER_SECRETARY_NEXT_WORK_2026-05-04.md",
            expected_kind="codex_contract",
            expected_sender="liah-test",
            note_contains=marker,
        ),
        idle=CodexCoordinationSelector(
            expected_name="REPORT_LII_SECRETARY_IDLE_2026-05-04.md",
            expected_kind="codex_report",
            expected_sender="liah-test",
            note_contains=marker,
        ),
    )


def _quarantine_file(
    tmp_path,
    *,
    transfer_id,
    name,
    kind,
    text="# report\n",
    sender="liah-test",
    note="secretary-marker",
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


def test_secretary_gate_requires_own_gate_and_blocks_unsafe_flags():
    assert validate_codex_secretary_gate(_armed_env(), confirm=CODEX_SECRETARY_GATE_CONFIRM_PHRASE) == []

    missing = validate_codex_secretary_gate({}, confirm="")
    assert "missing_codex_secretary_gate_confirm_phrase" in missing
    assert "SYNAPS_CODEX_SECRETARY_GATE_not_enabled" in missing

    unsafe = validate_codex_secretary_gate(
        _armed_env(SYNAPS_CODEX_DAEMON_RUNNER="1"),
        confirm=CODEX_SECRETARY_GATE_CONFIRM_PHRASE,
    )
    assert "SYNAPS_CODEX_DAEMON_RUNNER_must_remain_disabled" in unsafe


def test_secretary_gate_dry_run_selects_next_work_without_writing(tmp_path):
    _quarantine_file(
        tmp_path,
        transfer_id="synaps-file-next",
        name="TO_ESTER_SECRETARY_NEXT_WORK_2026-05-04.md",
        kind="codex_contract",
    )

    payload = run_codex_secretary_response_gate(
        selectors=_selectors(),
        env=_armed_env(),
        confirm=CODEX_SECRETARY_GATE_CONFIRM_PHRASE,
        policy=CodexSecretaryResponsePolicy(max_cycles=1, sleep_sec=0),
        **_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["selected_branch"] == "next_work"
    assert payload["selected_transfer_id"] == "synaps-file-next"
    assert payload["result"]["status"] == "would_select_secretary_response"
    assert not (tmp_path / "scanner" / "seen").exists()
    assert not (tmp_path / "inbox").exists()


def test_secretary_gate_apply_marks_idle_seen_and_repeat_is_empty(tmp_path):
    _quarantine_file(
        tmp_path,
        transfer_id="synaps-file-idle",
        name="REPORT_LII_SECRETARY_IDLE_2026-05-04.md",
        kind="codex_report",
    )

    payload = run_codex_secretary_response_gate(
        selectors=_selectors(),
        env=_armed_env(),
        apply=True,
        confirm=CODEX_SECRETARY_GATE_CONFIRM_PHRASE,
        policy=CodexSecretaryResponsePolicy(max_cycles=1, sleep_sec=0),
        **_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["selected_branch"] == "idle"
    assert payload["selected_transfer_id"] == "synaps-file-idle"
    assert payload["mark_seen_result"]["status"] == "scanner_seen"
    assert payload["repeat_check"]["matched"] is False
    assert (tmp_path / "scanner" / "seen" / "synaps-file-idle.json").is_file()
    assert not (tmp_path / "inbox").exists()


def test_secretary_gate_fails_closed_when_both_responses_exist(tmp_path):
    _quarantine_file(
        tmp_path,
        transfer_id="synaps-file-next",
        name="TO_ESTER_SECRETARY_NEXT_WORK_2026-05-04.md",
        kind="codex_contract",
    )
    _quarantine_file(
        tmp_path,
        transfer_id="synaps-file-idle",
        name="REPORT_LII_SECRETARY_IDLE_2026-05-04.md",
        kind="codex_report",
    )

    payload = run_codex_secretary_response_gate(
        selectors=_selectors(),
        env=_armed_env(),
        apply=True,
        confirm=CODEX_SECRETARY_GATE_CONFIRM_PHRASE,
        policy=CodexSecretaryResponsePolicy(max_cycles=1, sleep_sec=0),
        **_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "multiple_secretary_responses"
    assert "multiple_secretary_responses" in payload["problems"]
    assert not (tmp_path / "scanner" / "seen" / "synaps-file-next.json").exists()
    assert not (tmp_path / "scanner" / "seen" / "synaps-file-idle.json").exists()


def test_secretary_gate_no_response_is_safe_in_dry_run_and_failed_in_apply(tmp_path):
    dry = run_codex_secretary_response_gate(
        selectors=_selectors(),
        env=_armed_env(),
        confirm=CODEX_SECRETARY_GATE_CONFIRM_PHRASE,
        policy=CodexSecretaryResponsePolicy(max_cycles=1, sleep_sec=0),
        **_roots(tmp_path),
    )
    apply = run_codex_secretary_response_gate(
        selectors=_selectors(),
        env=_armed_env(),
        apply=True,
        confirm=CODEX_SECRETARY_GATE_CONFIRM_PHRASE,
        policy=CodexSecretaryResponsePolicy(max_cycles=1, sleep_sec=0),
        **_roots(tmp_path),
    )

    assert dry["ok"] is True
    assert dry["result"]["status"] == "secretary_response_not_found"
    assert apply["ok"] is False
    assert apply["result"]["status"] == "secretary_response_not_found"


def test_cli_secretary_gate_apply(tmp_path):
    _quarantine_file(
        tmp_path,
        transfer_id="synaps-file-cli-idle",
        name="REPORT_LII_SECRETARY_IDLE_2026-05-04.md",
        kind="codex_report",
    )
    env = os.environ.copy()
    env.update(_armed_env())

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_secretary_gate.py",
            "--env-file",
            "",
            "--next-name",
            "TO_ESTER_SECRETARY_NEXT_WORK_2026-05-04.md",
            "--idle-name",
            "REPORT_LII_SECRETARY_IDLE_2026-05-04.md",
            "--expect-sender",
            "liah-test",
            "--note-contains",
            "secretary-marker",
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
            "--apply",
            "--confirm",
            CODEX_SECRETARY_GATE_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["selected_branch"] == "idle"
    assert payload["selected_transfer_id"] == "synaps-file-cli-idle"
