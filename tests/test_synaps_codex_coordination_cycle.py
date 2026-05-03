import json
import os
import subprocess
import sys

from modules.synaps import (
    CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE,
    CODEX_COORDINATION_CYCLE_SCHEMA,
    CodexCoordinationCyclePolicy,
    CodexCoordinationSelector,
    CodexCoordinationSendSpec,
    CodexReportSelector,
    SynapsConfig,
    SynapsMessageType,
    SynapsQuarantineStore,
    build_envelope,
    build_file_manifest,
    run_codex_coordination_cycle_phase,
    validate_codex_coordination_cycle_gate,
)


def _config(node_id="ester-test") -> SynapsConfig:
    return SynapsConfig(node_url="http://sister.local", sync_token="shared-secret", node_id=node_id)


def _cycle_env(**extra):
    env = {
        "SYNAPS_CODEX_COORDINATION_CYCLE": "1",
        "SYNAPS_CODEX_COORDINATION_CYCLE_ARMED": "1",
        "SYNAPS_CODEX_COORDINATION_SCANNER": "1",
        "SYNAPS_CODEX_COORDINATION_SCANNER_ARMED": "1",
        "SYNAPS_CODEX_DAEMON": "1",
        "SYNAPS_CODEX_DAEMON_ARMED": "1",
        "SYNAPS_CODEX_DAEMON_OBSERVE_REPORTS": "1",
        "SYNAPS_CODEX_DAEMON_OBSERVE_REPORTS_ARMED": "1",
        "SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX": "0",
        "SYNAPS_CODEX_DAEMON_ENQUEUE_HANDOFFS": "0",
        "SYNAPS_CODEX_DAEMON_RUNNER": "0",
        "SYNAPS_CODEX_DAEMON_RUNNER_ARMED": "0",
        "SYNAPS_CODEX_DAEMON_PERSISTENT": "0",
        "SYNAPS_CODEX_DAEMON_PERSISTENT_ARMED": "0",
        "SISTER_AUTOCHAT": "0",
        "SISTER_NODE_URL": "http://sister.local",
        "SISTER_SYNC_TOKEN": "shared-secret",
        "ESTER_NODE_ID": "ester-test",
    }
    env.update(extra)
    return env


def _roots(tmp_path):
    return {
        "cycle_root": tmp_path / "cycle",
        "scanner_root": tmp_path / "scanner",
        "quarantine_root": tmp_path / "quarantine",
        "inbox_root": tmp_path / "inbox",
        "daemon_root": tmp_path / "daemon",
        "receipt_ledger": tmp_path / "receipts" / "events.jsonl",
        "request_root": tmp_path / "requests",
        "postcheck_roots": [tmp_path / "memory", tmp_path / "passport", tmp_path / "rag"],
    }


def _quarantine_file(
    tmp_path,
    *,
    transfer_id="synaps-file-cycle",
    name="expected.md",
    kind="codex_contract",
    text="# expected\nsafe body\n",
    sender="liah-test",
    note="0066 cycle",
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
    file_record = manifest["files"][0]
    return {"sha256": file_record["sha256"], "size": file_record["size"], "transfer_id": transfer_id}


def test_coordination_cycle_gate_blocks_unsafe_flags():
    assert validate_codex_coordination_cycle_gate(
        _cycle_env(),
        phase="wait_contract",
        confirm=CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE,
    ) == []

    problems = validate_codex_coordination_cycle_gate(
        _cycle_env(SISTER_AUTOCHAT="1", SYNAPS_CODEX_DAEMON_RUNNER="1"),
        phase="wait_contract",
        confirm=CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE,
    )

    assert "SISTER_AUTOCHAT_must_remain_disabled" in problems
    assert "SYNAPS_CODEX_DAEMON_RUNNER_must_remain_disabled" in problems


def test_coordination_cycle_send_file_dry_run_redacts_payload(tmp_path):
    source = tmp_path / "handoffs" / "contract.md"
    source.parent.mkdir()
    source.write_text("# contract\nsecret-free\n", encoding="utf-8")

    payload = run_codex_coordination_cycle_phase(
        phase="send_file",
        nonce="nonce-0066",
        env=_cycle_env(),
        env_file="",
        send_spec=CodexCoordinationSendSpec(
            file_path=str(source),
            base_dir=str(source.parent),
            kind="codex_contract",
            note="0066 send",
            include_payload=True,
        ),
        confirm=CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE,
        **_roots(tmp_path),
    )

    dumped = json.dumps(payload, ensure_ascii=False)
    assert payload["ok"] is True
    assert payload["schema"] == CODEX_COORDINATION_CYCLE_SCHEMA
    assert payload["phase_results"][0]["transfer"]["file_count"] == 1
    assert "payload_b64" not in dumped
    assert '"token"' not in dumped
    assert (tmp_path / "cycle" / "events.jsonl").is_file()


def test_coordination_cycle_send_rejects_path_escape(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("# outside\n", encoding="utf-8")

    payload = run_codex_coordination_cycle_phase(
        phase="send_file",
        nonce="nonce-escape",
        env=_cycle_env(),
        env_file="",
        send_spec=CodexCoordinationSendSpec(file_path=str(outside), base_dir=str(base), kind="codex_contract"),
        confirm=CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE,
        **_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert "file escapes base-dir" in payload["problems"]


def test_coordination_cycle_live_wait_contract_requires_hash_and_size(tmp_path):
    _quarantine_file(tmp_path, name="expected.md", kind="codex_contract", note="0066 exact")

    payload = run_codex_coordination_cycle_phase(
        phase="wait_contract",
        nonce="nonce-missing-exact",
        env=_cycle_env(),
        env_file="",
        selector=CodexCoordinationSelector(expected_name="expected.md", expected_kind="codex_contract", note_contains="0066"),
        apply=True,
        confirm=CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE,
        policy=CodexCoordinationCyclePolicy(max_cycles=1, sleep_sec=0),
        **_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert "expected_sha256_required_for_live_wait" in payload["problems"]
    assert "expected_size_required_for_live_wait" in payload["problems"]
    assert not (tmp_path / "scanner" / "seen").exists()


def test_coordination_cycle_wait_contract_marks_and_repeat_checks(tmp_path):
    record = _quarantine_file(tmp_path, transfer_id="synaps-file-contract", name="expected.md", kind="codex_contract", note="0066 mark")

    payload = run_codex_coordination_cycle_phase(
        phase="wait_contract",
        nonce="nonce-contract",
        env=_cycle_env(),
        env_file="",
        selector=CodexCoordinationSelector(
            expected_name="expected.md",
            expected_kind="codex_contract",
            note_contains="0066",
            expected_sha256=record["sha256"],
            expected_size=record["size"],
        ),
        apply=True,
        confirm=CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE,
        policy=CodexCoordinationCyclePolicy(max_cycles=1, sleep_sec=0),
        **_roots(tmp_path),
    )

    phase = payload["phase_results"][0]
    assert payload["ok"] is True
    assert phase["result"]["status"] == "scanner_seen"
    assert phase["repeat_check"]["candidate_count"] == 0
    assert (tmp_path / "scanner" / "seen" / "synaps-file-contract.json").is_file()
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / "requests").exists()


def test_coordination_cycle_lock_blocks_concurrent_mutating_run(tmp_path):
    record = _quarantine_file(tmp_path, transfer_id="synaps-file-locked", name="expected.md", kind="codex_contract", note="0066 lock")
    lock = tmp_path / "cycle" / "locks" / "nonce-lock__operator.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("busy", encoding="utf-8")

    payload = run_codex_coordination_cycle_phase(
        phase="wait_contract",
        nonce="nonce-lock",
        operator="operator",
        env=_cycle_env(),
        env_file="",
        selector=CodexCoordinationSelector(
            expected_name="expected.md",
            expected_kind="codex_contract",
            note_contains="0066",
            expected_sha256=record["sha256"],
            expected_size=record["size"],
        ),
        apply=True,
        confirm=CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE,
        policy=CodexCoordinationCyclePolicy(max_cycles=1, sleep_sec=0),
        **_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert "coordination_cycle_lock_exists" in payload["problems"]
    assert not (tmp_path / "scanner" / "seen" / "synaps-file-locked.json").exists()


def test_coordination_cycle_detects_env_file_mtime_change(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SISTER_AUTOCHAT=0\n", encoding="utf-8")

    def touch_env(_seconds):
        env_file.write_text("SISTER_AUTOCHAT=0\n# changed\n", encoding="utf-8")

    payload = run_codex_coordination_cycle_phase(
        phase="wait_contract",
        nonce="nonce-env",
        env=_cycle_env(),
        env_file=env_file,
        selector=CodexCoordinationSelector(expected_name="missing.md", expected_kind="codex_contract"),
        confirm=CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE,
        policy=CodexCoordinationCyclePolicy(max_cycles=2, sleep_sec=0.01),
        sleep_fn=touch_env,
        **_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert "env_file_changed_during_cycle" in payload["problems"]


def test_coordination_cycle_postcheck_blocks_marker_in_memory(tmp_path):
    source = tmp_path / "handoffs" / "contract.md"
    source.parent.mkdir()
    source.write_text("# contract\n", encoding="utf-8")
    memory = tmp_path / "memory"
    memory.mkdir()
    (memory / "leak.txt").write_text("nonce-postcheck", encoding="utf-8")

    payload = run_codex_coordination_cycle_phase(
        phase="send_file",
        nonce="nonce-postcheck",
        env=_cycle_env(),
        env_file="",
        send_spec=CodexCoordinationSendSpec(file_path=str(source), base_dir=str(source.parent), kind="codex_contract"),
        confirm=CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE,
        **_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert "postcheck_marker_found" in payload["problems"]


def test_coordination_cycle_wait_report_observes_and_repeat_checks(tmp_path):
    record = _quarantine_file(tmp_path, transfer_id="synaps-file-report", name="report.md", kind="codex_report", note="0066 report")

    payload = run_codex_coordination_cycle_phase(
        phase="wait_report",
        nonce="nonce-report",
        env=_cycle_env(),
        env_file="",
        selector=CodexReportSelector(
            expected_name="report.md",
            note_contains="0066",
            expected_sha256=record["sha256"],
            expected_size=record["size"],
        ),
        apply=True,
        confirm=CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE,
        policy=CodexCoordinationCyclePolicy(max_cycles=1, sleep_sec=0),
        **_roots(tmp_path),
    )

    phase = payload["phase_results"][0]
    assert payload["ok"] is True
    assert phase["result"]["status"] == "report_observed"
    assert phase["repeat_check"]["candidate_count"] == 0
    assert (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").is_file()
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / "requests").exists()


def test_cli_coordination_cycle_send_file_dry_run(tmp_path):
    source = tmp_path / "handoffs" / "contract.md"
    source.parent.mkdir()
    source.write_text("# contract\n", encoding="utf-8")
    env = os.environ.copy()
    env.update(_cycle_env())

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_coordination_cycle.py",
            "--env-file",
            "",
            "--phase",
            "send_file",
            "--nonce",
            "nonce-cli",
            "--cycle-root",
            str(tmp_path / "cycle"),
            "--file",
            str(source),
            "--base-dir",
            str(source.parent),
            "--kind",
            "codex_contract",
            "--note",
            "0066 cli",
            "--include-payload",
            "--confirm",
            CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["phase"] == "send_file"
    assert "payload_b64" not in result.stdout
