import json
import subprocess
import sys

from modules.synaps import (
    CODEX_WORKER_PREFLIGHT_CONFIRM_PHRASE,
    CodexWorkerPreflightPolicy,
    codex_worker_preflight_arm_status,
    run_codex_worker_preflight,
    validate_codex_worker_preflight_gate,
)


def _env(**extra):
    env = {
        "SYNAPS_CODEX_WORKER_PREFLIGHT": "1",
        "SYNAPS_CODEX_WORKER_PREFLIGHT_ARMED": "1",
        "SISTER_AUTOCHAT": "0",
    }
    env.update(extra)
    return env


def _fake_codex(tmp_path, message):
    fake = tmp_path / "fake_codex.py"
    fake.write_text(
        "import sys\n"
        "out=''\n"
        "for i,a in enumerate(sys.argv):\n"
        "    if a == '--output-last-message' and i + 1 < len(sys.argv): out=sys.argv[i+1]\n"
        f"message={message!r}\n"
        "if out: open(out, 'w', encoding='utf-8').write(message)\n"
        "print(message)\n",
        encoding="utf-8",
    )
    return fake


def test_preflight_gate_requires_arm_and_read_only():
    policy = CodexWorkerPreflightPolicy(sandbox="read-only")

    assert codex_worker_preflight_arm_status(_env())["preflight"] is True
    assert validate_codex_worker_preflight_gate(_env(), CODEX_WORKER_PREFLIGHT_CONFIRM_PHRASE, policy) == []
    assert "SYNAPS_CODEX_WORKER_PREFLIGHT_ARMED_not_enabled" in validate_codex_worker_preflight_gate(
        {"SYNAPS_CODEX_WORKER_PREFLIGHT": "1", "SISTER_AUTOCHAT": "0"},
        CODEX_WORKER_PREFLIGHT_CONFIRM_PHRASE,
        policy,
    )
    assert "SYNAPS_CODEX_WORKER_PREFLIGHT_SANDBOX_must_be_read_only" in validate_codex_worker_preflight_gate(
        _env(),
        CODEX_WORKER_PREFLIGHT_CONFIRM_PHRASE,
        CodexWorkerPreflightPolicy(sandbox="workspace-write"),
    )


def test_preflight_blocks_live_and_runner_flags():
    policy = CodexWorkerPreflightPolicy(sandbox="read-only")

    for key in ("SISTER_SCHEDULE", "SISTER_CONVERSATION_WINDOW", "SISTER_FILE_TRANSFER"):
        problems = validate_codex_worker_preflight_gate(_env(**{key: "1"}), CODEX_WORKER_PREFLIGHT_CONFIRM_PHRASE, policy)
        assert "SYNAPS_live_send_flags_must_remain_disabled_for_preflight" in problems

    for key in (
        "SYNAPS_CODEX_DAEMON",
        "SYNAPS_CODEX_DAEMON_ARMED",
        "SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX",
        "SYNAPS_CODEX_DAEMON_ENQUEUE_HANDOFFS",
        "SYNAPS_CODEX_DAEMON_RUNNER",
        "SYNAPS_CODEX_DAEMON_RUNNER_ARMED",
        "SYNAPS_CODEX_RUNNER_WINDOW",
    ):
        problems = validate_codex_worker_preflight_gate(
            _env(**{key: "1"}),
            CODEX_WORKER_PREFLIGHT_CONFIRM_PHRASE,
            policy,
        )
        assert "SYNAPS_CODEX_daemon_runner_flags_must_remain_disabled_for_preflight" in problems


def test_preflight_dry_run_writes_nothing(tmp_path):
    payload = run_codex_worker_preflight(env={}, root=tmp_path / "preflight")

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert not (tmp_path / "preflight").exists()


def test_preflight_apply_fails_closed_without_gate(tmp_path):
    payload = run_codex_worker_preflight(
        env={"SISTER_AUTOCHAT": "0"},
        apply=True,
        confirm=CODEX_WORKER_PREFLIGHT_CONFIRM_PHRASE,
        root=tmp_path / "preflight",
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "gate_failed"
    assert not (tmp_path / "preflight").exists()


def test_preflight_apply_fails_closed_for_duplicate_id(tmp_path):
    root = tmp_path / "preflight"
    fake = _fake_codex(tmp_path, "inspected target\nCODEX_WORKER_PREFLIGHT_AVAILABLE")
    policy = CodexWorkerPreflightPolicy(workdir=str(tmp_path), codex_command=f"{sys.executable} {fake}", sandbox="read-only")

    first = run_codex_worker_preflight(
        env=_env(),
        apply=True,
        confirm=CODEX_WORKER_PREFLIGHT_CONFIRM_PHRASE,
        root=root,
        policy=policy,
        preflight_id="duplicate-preflight",
    )
    second = run_codex_worker_preflight(
        env=_env(),
        apply=True,
        confirm=CODEX_WORKER_PREFLIGHT_CONFIRM_PHRASE,
        root=root,
        policy=policy,
        preflight_id="duplicate-preflight",
    )

    assert first["ok"] is True
    assert second["ok"] is False
    assert second["result"]["status"] == "preflight_id_exists"


def test_preflight_classifies_available_fake_worker(tmp_path):
    fake = _fake_codex(tmp_path, "inspected target\nCODEX_WORKER_PREFLIGHT_AVAILABLE")
    policy = CodexWorkerPreflightPolicy(workdir=str(tmp_path), codex_command=f"{sys.executable} {fake}", sandbox="read-only")

    payload = run_codex_worker_preflight(
        env=_env(),
        apply=True,
        confirm=CODEX_WORKER_PREFLIGHT_CONFIRM_PHRASE,
        root=tmp_path / "preflight",
        policy=policy,
        preflight_id="preflight-ok",
    )

    assert payload["ok"] is True
    assert payload["result"]["status"] == "available"
    assert (tmp_path / "preflight" / "preflight-ok" / "result.json").is_file()


def test_preflight_classifies_bwrap_block_fake_worker(tmp_path):
    fake = _fake_codex(tmp_path, "bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted")
    policy = CodexWorkerPreflightPolicy(workdir=str(tmp_path), codex_command=f"{sys.executable} {fake}", sandbox="read-only")

    payload = run_codex_worker_preflight(
        env=_env(),
        apply=True,
        confirm=CODEX_WORKER_PREFLIGHT_CONFIRM_PHRASE,
        root=tmp_path / "preflight",
        policy=policy,
        preflight_id="preflight-blocked",
    )

    assert payload["ok"] is True
    assert payload["result"]["status"] == "worker_sandbox_blocked"
    assert payload["result"]["blocked_reason"] == "worker_sandbox_blocked"


def test_preflight_does_not_block_on_quoted_bwrap_marker_from_file_content(tmp_path):
    fake = tmp_path / "fake_codex_quoted_marker.py"
    fake.write_text(
        "import sys\n"
        "out=''\n"
        "for i,a in enumerate(sys.argv):\n"
        "    if a == '--output-last-message' and i + 1 < len(sys.argv): out=sys.argv[i+1]\n"
        "message='inspected target\\nCODEX_WORKER_PREFLIGHT_AVAILABLE'\n"
        "stderr='    \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\",\\n'\n"
        "if out: open(out, 'w', encoding='utf-8').write(message)\n"
        "print(message)\n"
        "print(stderr, file=sys.stderr)\n",
        encoding="utf-8",
    )
    policy = CodexWorkerPreflightPolicy(workdir=str(tmp_path), codex_command=f"{sys.executable} {fake}", sandbox="read-only")

    payload = run_codex_worker_preflight(
        env=_env(),
        apply=True,
        confirm=CODEX_WORKER_PREFLIGHT_CONFIRM_PHRASE,
        root=tmp_path / "preflight",
        policy=policy,
        preflight_id="preflight-quoted-marker",
    )

    assert payload["ok"] is True
    assert payload["result"]["status"] == "available"
    assert payload["result"]["blocked_reason"] == ""


def test_preflight_classifies_markdown_bwrap_blocked_sentinel(tmp_path):
    fake = tmp_path / "fake_codex_markdown_blocked.py"
    fake.write_text(
        "import sys\n"
        "out=''\n"
        "for i,a in enumerate(sys.argv):\n"
        "    if a == '--output-last-message' and i + 1 < len(sys.argv): out=sys.argv[i+1]\n"
        "message='Could not inspect target.\\n`bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`\\n\\nCODEX_WORKER_PREFLIGHT_BLOCKED'\n"
        "if out: open(out, 'w', encoding='utf-8').write(message)\n"
        "print(message)\n",
        encoding="utf-8",
    )
    policy = CodexWorkerPreflightPolicy(workdir=str(tmp_path), codex_command=f"{sys.executable} {fake}", sandbox="read-only")

    payload = run_codex_worker_preflight(
        env=_env(),
        apply=True,
        confirm=CODEX_WORKER_PREFLIGHT_CONFIRM_PHRASE,
        root=tmp_path / "preflight",
        policy=policy,
        preflight_id="preflight-markdown-bwrap-blocked",
    )

    assert payload["ok"] is True
    assert payload["result"]["status"] == "worker_sandbox_blocked"
    assert payload["result"]["blocked_reason"] == "worker_sandbox_blocked"


def test_cli_preflight_dry_run_writes_nothing(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_worker_preflight.py",
            "--env-file",
            str(tmp_path / "missing.env"),
            "--root",
            str(tmp_path / "preflight"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert not (tmp_path / "preflight").exists()
