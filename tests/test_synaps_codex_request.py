import ast
import json
import subprocess
import sys

from modules.synaps import (
    CODEX_REQUEST_CLAIM_CONFIRM_PHRASE,
    CODEX_REQUEST_COMPLETE_CONFIRM_PHRASE,
    CODEX_REQUEST_CREATE_CONFIRM_PHRASE,
    REQUEST_STATUS_BLOCKED,
    REQUEST_STATUS_CLAIMED,
    REQUEST_STATUS_COMPLETED,
    REQUEST_STATUS_QUEUED,
    CodexRequestPolicy,
    CodexRequestStore,
    codex_request_arm_status,
    validate_codex_request_gate,
)


def _env_file(tmp_path, lines):
    path = tmp_path / ".env"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _armed_env():
    return {
        "SYNAPS_CODEX_REQUESTS": "1",
        "SYNAPS_CODEX_REQUESTS_ARMED": "1",
        "SISTER_AUTOCHAT": "0",
    }


def test_policy_caps_request_limits():
    policy = CodexRequestPolicy.from_env(
        {
            "SYNAPS_CODEX_REQUEST_MAX_TITLE_CHARS": "999",
            "SYNAPS_CODEX_REQUEST_MAX_TASK_CHARS": "999999",
            "SYNAPS_CODEX_REQUEST_MAX_TAGS": "99",
            "SYNAPS_CODEX_REQUEST_MAX_TRANSFERS": "99",
        }
    )

    assert policy.max_title_chars == 240
    assert policy.max_task_chars == 8000
    assert policy.max_tags == 16
    assert policy.max_related_transfers == 24


def test_gate_requires_arm_confirm_and_honors_kill_switch():
    env = _armed_env()

    assert codex_request_arm_status(env)["requests"] is True
    assert validate_codex_request_gate(env, CODEX_REQUEST_CREATE_CONFIRM_PHRASE, CODEX_REQUEST_CREATE_CONFIRM_PHRASE) == []
    assert "SYNAPS_CODEX_REQUESTS_KILL_SWITCH_enabled" in validate_codex_request_gate(
        {**env, "SYNAPS_CODEX_REQUESTS_KILL_SWITCH": "1"},
        CODEX_REQUEST_CREATE_CONFIRM_PHRASE,
        CODEX_REQUEST_CREATE_CONFIRM_PHRASE,
    )


def test_store_create_claim_complete_request(tmp_path):
    store = CodexRequestStore(tmp_path)
    record = store.build_request(
        request_id="req-1",
        title="Review scheduler",
        task="Check dry-run behavior only.",
        requester="ester",
        origin="ester_runtime",
        priority="high",
        tags=["synaps", "codex"],
        related_transfer_ids=["synaps-file-abc"],
    )

    created = store.create_request(record)
    claimed = store.claim_request("req-1", operator="codex-ester")
    completed = store.complete_request("req-1", operator="codex-ester", summary="done")

    assert created["status"] == REQUEST_STATUS_QUEUED
    assert claimed["status"] == REQUEST_STATUS_CLAIMED
    assert completed["status"] == REQUEST_STATUS_COMPLETED
    assert completed["request"]["auto_execute"] is False
    assert completed["request"]["memory"] == "off"
    assert (tmp_path / "events.jsonl").is_file()


def test_store_blocks_bad_transfer_id_and_secret_like_task(tmp_path):
    store = CodexRequestStore(tmp_path)

    try:
        store.build_request(
            title="bad",
            task="safe",
            requester="ester",
            origin="test",
            related_transfer_ids=["not-transfer"],
        )
    except Exception as exc:
        assert "synaps-file-" in str(exc)
    else:
        raise AssertionError("bad transfer id accepted")

    try:
        store.build_request(title="bad", task="SISTER_SYNC_TOKEN=secret", requester="ester", origin="test")
    except Exception as exc:
        assert "secret-like" in str(exc)
    else:
        raise AssertionError("secret-like task accepted")


def test_cli_create_dry_run_writes_nothing(tmp_path):
    env_file = _env_file(tmp_path, ["SYNAPS_CODEX_REQUESTS=1", "SYNAPS_CODEX_REQUESTS_ARMED=1", "SISTER_AUTOCHAT=0"])
    root = tmp_path / "requests"

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_request.py",
            "create",
            "--env-file",
            str(env_file),
            "--root",
            str(root),
            "--title",
            "Check logs",
            "--task",
            "Inspect the scheduler dry-run report only.",
            "--requester",
            "ester",
            "--origin",
            "ester_runtime",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["request"]["auto_execute"] is False
    assert not root.exists()


def test_cli_create_apply_requires_gate(tmp_path):
    env_file = _env_file(tmp_path, ["SISTER_AUTOCHAT=0"])
    root = tmp_path / "requests"

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_request.py",
            "create",
            "--env-file",
            str(env_file),
            "--root",
            str(root),
            "--title",
            "Check logs",
            "--task",
            "Inspect only.",
            "--apply",
            "--confirm",
            CODEX_REQUEST_CREATE_CONFIRM_PHRASE,
        ],
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 2
    assert payload["result"]["error"] == "request_gate_failed"
    assert "SYNAPS_CODEX_REQUESTS_not_enabled" in payload["result"]["problems"]
    assert not root.exists()


def test_cli_create_claim_complete_apply(tmp_path):
    env_file = _env_file(tmp_path, ["SYNAPS_CODEX_REQUESTS=1", "SYNAPS_CODEX_REQUESTS_ARMED=1", "SISTER_AUTOCHAT=0"])
    root = tmp_path / "requests"

    create = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_request.py",
            "create",
            "--env-file",
            str(env_file),
            "--root",
            str(root),
            "--request-id",
            "req-cli",
            "--title",
            "Check logs",
            "--task",
            "Inspect only.",
            "--apply",
            "--confirm",
            CODEX_REQUEST_CREATE_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    claim = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_request.py",
            "claim",
            "--env-file",
            str(env_file),
            "--root",
            str(root),
            "--request-id",
            "req-cli",
            "--operator",
            "codex",
            "--apply",
            "--confirm",
            CODEX_REQUEST_CLAIM_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    complete = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_request.py",
            "complete",
            "--env-file",
            str(env_file),
            "--root",
            str(root),
            "--request-id",
            "req-cli",
            "--operator",
            "codex",
            "--summary",
            "No action taken.",
            "--result-status",
            "blocked",
            "--apply",
            "--confirm",
            CODEX_REQUEST_COMPLETE_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(create.stdout)["result"]["status"] == REQUEST_STATUS_QUEUED
    assert json.loads(claim.stdout)["result"]["status"] == REQUEST_STATUS_CLAIMED
    assert json.loads(complete.stdout)["result"]["status"] == REQUEST_STATUS_BLOCKED


def test_cli_bootstraps_env_before_modules_imports():
    source = open("tools/synaps_codex_request.py", encoding="utf-8").read()
    tree = ast.parse(source)
    unsafe_top_level_imports = [
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and (str(node.module or "").startswith("modules.") or str(node.module or "").startswith("tools."))
    ]
    main_start = source.index("def main(")
    main_synaps_import = source.index("from modules.synaps import (", main_start)

    assert unsafe_top_level_imports == []
    assert source.index("bootstrap_env_from_argv(raw_argv)", main_start) < main_synaps_import
