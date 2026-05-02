import json
import subprocess
import sys

from modules.synaps import (
    CODEX_RUNNER_WINDOW_CONFIRM_PHRASE,
    CODEX_WORKER_CAPABILITY_AVAILABLE,
    CodexDaemonPolicy,
    CodexRequestStore,
    codex_runner_window_arm_status,
    run_codex_runner_window,
    validate_codex_runner_window_gate,
)


def _request(store, request_id):
    record = store.build_request(
        request_id=request_id,
        title=f"Run {request_id}",
        task="Run fake read-only Codex only.",
        requester="test",
        origin="test",
    )
    store.create_request(record)


def _fake_codex(tmp_path):
    fake = tmp_path / "fake_codex.py"
    fake.write_text(
        "import sys\n"
        "out=''\n"
        "for i,a in enumerate(sys.argv):\n"
        "    if a == '--output-last-message' and i + 1 < len(sys.argv): out=sys.argv[i+1]\n"
        "if out: open(out, 'w', encoding='utf-8').write('fake runner window completed')\n"
        "print('fake stdout')\n",
        encoding="utf-8",
    )
    return fake


def _window_env(**extra):
    env = {
        "SYNAPS_CODEX_RUNNER_WINDOW": "1",
        "SYNAPS_CODEX_RUNNER_WINDOW_ARMED": "1",
        "SYNAPS_CODEX_WORKER_CAPABILITY": CODEX_WORKER_CAPABILITY_AVAILABLE,
        "SISTER_AUTOCHAT": "0",
    }
    env.update(extra)
    return env


def test_runner_window_gate_requires_arm_and_read_only():
    policy = CodexDaemonPolicy(sandbox="read-only")

    assert codex_runner_window_arm_status(_window_env())["window"] is True
    assert validate_codex_runner_window_gate(_window_env(), CODEX_RUNNER_WINDOW_CONFIRM_PHRASE, policy) == []
    assert "SYNAPS_CODEX_RUNNER_WINDOW_ARMED_not_enabled" in validate_codex_runner_window_gate(
        {"SYNAPS_CODEX_RUNNER_WINDOW": "1", "SISTER_AUTOCHAT": "0"},
        CODEX_RUNNER_WINDOW_CONFIRM_PHRASE,
        policy,
    )
    assert "SYNAPS_CODEX_WORKER_CAPABILITY_must_be_available_for_runner_window" in validate_codex_runner_window_gate(
        {"SYNAPS_CODEX_RUNNER_WINDOW": "1", "SYNAPS_CODEX_RUNNER_WINDOW_ARMED": "1", "SISTER_AUTOCHAT": "0"},
        CODEX_RUNNER_WINDOW_CONFIRM_PHRASE,
        policy,
    )
    assert "SYNAPS_CODEX_DAEMON_SANDBOX_must_be_read_only_for_runner_window" in validate_codex_runner_window_gate(
        _window_env(),
        CODEX_RUNNER_WINDOW_CONFIRM_PHRASE,
        CodexDaemonPolicy(sandbox="workspace-write"),
    )


def test_runner_window_gate_blocks_live_send_flags():
    policy = CodexDaemonPolicy(sandbox="read-only")

    for key in ("SISTER_SCHEDULE", "SISTER_CONVERSATION_WINDOW", "SISTER_FILE_TRANSFER"):
        problems = validate_codex_runner_window_gate(
            _window_env(**{key: "1"}),
            CODEX_RUNNER_WINDOW_CONFIRM_PHRASE,
            policy,
        )
        assert "SYNAPS_live_send_flags_must_remain_disabled_for_runner_window" in problems


def test_runner_window_dry_run_writes_nothing(tmp_path):
    store = CodexRequestStore(tmp_path / "requests")
    _request(store, "req-window-dry")

    payload = run_codex_runner_window(
        env={},
        request_root=tmp_path / "requests",
        daemon_root=tmp_path / "daemon",
        window_root=tmp_path / "windows",
    )

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["actions"][0]["action"] == "run_request"
    assert not (tmp_path / "windows").exists()
    assert CodexRequestStore(tmp_path / "requests").inspect_request("req-window-dry")["status"] == "queued"


def test_runner_window_apply_fails_closed_without_gate(tmp_path):
    store = CodexRequestStore(tmp_path / "requests")
    _request(store, "req-window-fail")

    payload = run_codex_runner_window(
        env={"SISTER_AUTOCHAT": "0"},
        apply=True,
        confirm=CODEX_RUNNER_WINDOW_CONFIRM_PHRASE,
        request_root=tmp_path / "requests",
        daemon_root=tmp_path / "daemon",
        window_root=tmp_path / "windows",
    )

    assert payload["ok"] is False
    assert payload["result"]["error"] == "runner_window_gate_failed"
    assert "SYNAPS_CODEX_RUNNER_WINDOW_not_enabled" in payload["result"]["problems"]
    assert not (tmp_path / "windows").exists()
    assert CodexRequestStore(tmp_path / "requests").inspect_request("req-window-fail")["status"] == "queued"


def test_runner_window_runs_one_fake_read_only_request(tmp_path):
    fake = _fake_codex(tmp_path)
    store = CodexRequestStore(tmp_path / "requests")
    _request(store, "req-window-a")
    _request(store, "req-window-b")
    policy = CodexDaemonPolicy(workdir=str(tmp_path), codex_command=f"{sys.executable} {fake}", sandbox="read-only")

    payload = run_codex_runner_window(
        env=_window_env(),
        apply=True,
        confirm=CODEX_RUNNER_WINDOW_CONFIRM_PHRASE,
        request_root=tmp_path / "requests",
        daemon_root=tmp_path / "daemon",
        window_root=tmp_path / "windows",
        policy=policy,
        window_id="window-test",
    )

    first = CodexRequestStore(tmp_path / "requests").inspect_request("req-window-a")
    second = CodexRequestStore(tmp_path / "requests").inspect_request("req-window-b")
    events = (tmp_path / "windows" / "window-test" / "events.jsonl").read_text(encoding="utf-8").splitlines()

    assert payload["ok"] is True
    assert len(payload["actions"]) == 1
    assert first["status"] == "completed"
    assert second["status"] == "queued"
    assert len(events) == 2
    assert json.loads(events[0])["event"] == "opened"
    assert json.loads(events[1])["event"] == "closed"


def test_cli_runner_window_fail_closed_without_apply_gate(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_runner_window.py",
            "--env-file",
            str(tmp_path / "missing.env"),
            "--window-root",
            str(tmp_path / "windows"),
            "--daemon-root",
            str(tmp_path / "daemon"),
            "--request-root",
            str(tmp_path / "requests"),
            "--apply",
            "--confirm",
            CODEX_RUNNER_WINDOW_CONFIRM_PHRASE,
        ],
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 2
    assert payload["result"]["error"] == "runner_window_gate_failed"
    assert not (tmp_path / "windows").exists()
