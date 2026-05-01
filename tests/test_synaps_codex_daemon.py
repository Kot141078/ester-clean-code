import json
import subprocess
import sys

from modules.synaps import (
    CODEX_DAEMON_BASELINE_CONFIRM_PHRASE,
    CODEX_DAEMON_CONFIRM_PHRASE,
    CODEX_MAILBOX_CONFIRM_PHRASE,
    REQUEST_STATUS_COMPLETED,
    REQUEST_STATUS_QUEUED,
    SynapsConfig,
    SynapsMessageType,
    SynapsQuarantineStore,
    build_envelope,
    build_file_manifest,
    codex_daemon_arm_status,
    inspect_codex_mailbox_transfer,
    validate_codex_daemon_gate,
    CodexDaemon,
    CodexDaemonPolicy,
    CodexRequestStore,
)


def _config() -> SynapsConfig:
    return SynapsConfig(
        node_url="http://sister.local",
        sync_token="shared-secret",
        node_id="ester-test",
    )


def _armed_env(**extra):
    env = {
        "SYNAPS_CODEX_DAEMON": "1",
        "SYNAPS_CODEX_DAEMON_ARMED": "1",
        "SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX": "1",
        "SYNAPS_CODEX_DAEMON_ENQUEUE_HANDOFFS": "1",
        "SISTER_AUTOCHAT": "0",
    }
    env.update(extra)
    return env


def _quarantine_transfer(tmp_path, *, transfer_id="synaps-file-test", kind="codex_handoff", name="task.md", text="do safe work"):
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


def _daemon(tmp_path, policy=None):
    return CodexDaemon(
        daemon_root=tmp_path / "daemon",
        quarantine_root=tmp_path / "quarantine",
        inbox_root=tmp_path / "inbox",
        receipt_ledger=tmp_path / "receipts" / "events.jsonl",
        request_root=tmp_path / "requests",
        policy=policy or CodexDaemonPolicy(workdir=str(tmp_path)),
    )


def test_mailbox_accepts_codex_handoff_kind(tmp_path):
    _quarantine_transfer(tmp_path)

    record = inspect_codex_mailbox_transfer("synaps-file-test", tmp_path / "quarantine", tmp_path / "inbox")

    assert record["ok"] is True
    assert record["files"][0]["kind"] == "codex_handoff"


def test_daemon_gate_requires_enable_arm_confirm_and_blocks_autochat():
    env = _armed_env()

    assert codex_daemon_arm_status(env)["daemon"] is True
    assert validate_codex_daemon_gate(env, CODEX_DAEMON_CONFIRM_PHRASE) == []
    assert "SISTER_AUTOCHAT_must_remain_disabled" in validate_codex_daemon_gate(
        {**env, "SISTER_AUTOCHAT": "1"},
        CODEX_DAEMON_CONFIRM_PHRASE,
    )


def test_cycle_dry_run_writes_nothing(tmp_path):
    _quarantine_transfer(tmp_path)

    payload = _daemon(tmp_path).cycle(env=_armed_env(), apply=False)

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["actions"][0]["action"] == "promote_mailbox"
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / "requests").exists()


def test_cycle_apply_promotes_and_enqueues_handoff_without_running(tmp_path):
    _quarantine_transfer(tmp_path)
    daemon = _daemon(tmp_path)

    payload = daemon.cycle(env=_armed_env(), apply=True, confirm=CODEX_DAEMON_CONFIRM_PHRASE)
    request_id = "codex-bridge-synaps-file-test"
    request = CodexRequestStore(tmp_path / "requests").inspect_request(request_id)

    assert payload["ok"] is True
    assert (tmp_path / "inbox" / "synaps-file-test").is_dir()
    assert (tmp_path / "receipts" / "events.jsonl").is_file()
    assert request["status"] == REQUEST_STATUS_QUEUED
    assert request["request"]["auto_execute"] is False
    assert request["request"]["memory"] == "off"
    assert (tmp_path / "daemon" / "inbox_seen" / "synaps-file-test.json").is_file()


def test_baseline_apply_marks_existing_handoff_and_prevents_enqueue(tmp_path):
    _quarantine_transfer(tmp_path)
    daemon = _daemon(tmp_path)

    baseline = daemon.baseline_existing(env=_armed_env(), apply=True, confirm=CODEX_DAEMON_BASELINE_CONFIRM_PHRASE)
    cycle = daemon.cycle(env=_armed_env(), apply=True, confirm=CODEX_DAEMON_CONFIRM_PHRASE)

    assert baseline["ok"] is True
    assert baseline["result"]["count"] == 1
    assert (tmp_path / "daemon" / "inbox_seen" / "synaps-file-test.json").is_file()
    assert (tmp_path / "daemon" / "promote_seen" / "synaps-file-test.json").is_file()
    assert not (tmp_path / "inbox" / "synaps-file-test").exists()
    assert not (tmp_path / "requests" / "codex-bridge-synaps-file-test").exists()
    assert cycle["actions"] == []


def test_after_baseline_new_handoff_can_promote_and_enqueue(tmp_path):
    _quarantine_transfer(tmp_path, transfer_id="synaps-file-old")
    daemon = _daemon(tmp_path)

    daemon.baseline_existing(env=_armed_env(), apply=True, confirm=CODEX_DAEMON_BASELINE_CONFIRM_PHRASE)
    _quarantine_transfer(tmp_path, transfer_id="synaps-file-new")
    cycle = daemon.cycle(env=_armed_env(), apply=True, confirm=CODEX_DAEMON_CONFIRM_PHRASE)

    assert [action["action"] for action in cycle["actions"]] == ["promote_mailbox", "enqueue_handoff"]
    assert cycle["actions"][0]["transfer_id"] == "synaps-file-new"
    assert cycle["actions"][1]["transfer_id"] == "synaps-file-new"
    assert not (tmp_path / "requests" / "codex-bridge-synaps-file-old").exists()
    assert (tmp_path / "requests" / "codex-bridge-synaps-file-new").is_dir()


def test_baseline_marks_non_task_reports_so_promote_skips_old_reports(tmp_path):
    _quarantine_transfer(tmp_path, transfer_id="synaps-file-report", kind="codex_report", name="report.md")
    daemon = _daemon(tmp_path)

    baseline = daemon.baseline_existing(env=_armed_env(), apply=True, confirm=CODEX_DAEMON_BASELINE_CONFIRM_PHRASE)
    cycle = daemon.cycle(env=_armed_env(), apply=True, confirm=CODEX_DAEMON_CONFIRM_PHRASE)

    assert baseline["ok"] is True
    assert (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").is_file()
    assert not (tmp_path / "daemon" / "inbox_seen" / "synaps-file-report.json").exists()
    assert cycle["actions"] == []
    assert not (tmp_path / "requests").exists()


def test_baseline_apply_requires_gate(tmp_path):
    _quarantine_transfer(tmp_path)

    payload = _daemon(tmp_path).baseline_existing(
        env={"SISTER_AUTOCHAT": "0"},
        apply=True,
        confirm=CODEX_DAEMON_BASELINE_CONFIRM_PHRASE,
    )

    assert payload["ok"] is False
    assert payload["result"]["error"] == "daemon_gate_failed"
    assert not (tmp_path / "daemon").exists()


def test_cycle_apply_requires_gate(tmp_path):
    _quarantine_transfer(tmp_path)

    payload = _daemon(tmp_path).cycle(env={"SISTER_AUTOCHAT": "0"}, apply=True, confirm=CODEX_DAEMON_CONFIRM_PHRASE)

    assert payload["ok"] is False
    assert payload["result"]["error"] == "daemon_gate_failed"
    assert not (tmp_path / "inbox").exists()


def test_runner_uses_fake_codex_and_completes_request(tmp_path):
    fake = tmp_path / "fake_codex.py"
    fake.write_text(
        "import sys\n"
        "out=''\n"
        "for i,a in enumerate(sys.argv):\n"
        "    if a == '--output-last-message' and i + 1 < len(sys.argv): out=sys.argv[i+1]\n"
        "if out: open(out, 'w', encoding='utf-8').write('fake codex completed')\n"
        "print('fake stdout')\n",
        encoding="utf-8",
    )
    store = CodexRequestStore(tmp_path / "requests")
    record = store.build_request(
        request_id="req-runner",
        title="Run fake",
        task="Use fake Codex.",
        requester="test",
        origin="test",
    )
    store.create_request(record)
    policy = CodexDaemonPolicy(workdir=str(tmp_path), codex_command=f"{sys.executable} {fake}")
    daemon = _daemon(tmp_path, policy=policy)
    env = _armed_env(SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX="0", SYNAPS_CODEX_DAEMON_ENQUEUE_HANDOFFS="0", SYNAPS_CODEX_DAEMON_RUNNER="1")

    payload = daemon.cycle(env=env, apply=True, confirm=CODEX_DAEMON_CONFIRM_PHRASE)
    request = CodexRequestStore(tmp_path / "requests").inspect_request("req-runner")

    assert payload["ok"] is True
    assert payload["actions"][0]["result"]["status"] == REQUEST_STATUS_COMPLETED
    assert request["status"] == REQUEST_STATUS_COMPLETED
    assert "fake codex completed" in request["events"][-1]["summary"]["summary"]


def test_cli_status_is_dry_run(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_daemon.py",
            "status",
            "--daemon-root",
            str(tmp_path / "daemon"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["confirm_required"] == CODEX_DAEMON_CONFIRM_PHRASE


def test_cli_baseline_dry_run_writes_nothing(tmp_path):
    _quarantine_transfer(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_daemon.py",
            "baseline",
            "--daemon-root",
            str(tmp_path / "daemon"),
            "--quarantine-root",
            str(tmp_path / "quarantine"),
            "--inbox-root",
            str(tmp_path / "inbox"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["count"] == 1
    assert not (tmp_path / "daemon").exists()
