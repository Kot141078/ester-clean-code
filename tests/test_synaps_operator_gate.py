import ast
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

from modules.synaps import (
    ACTION_FILE_TRANSFER,
    FILE_TRANSFER_CONFIRM_PHRASE,
    OPERATOR_GATE_CONFIRM_PHRASE,
    OperatorGatePolicy,
    OperatorGateStore,
    operator_gate_arm_status,
    validate_operator_gate_send_gate,
)
from modules.synaps.window import CONVERSATION_WINDOW_CONFIRM_PHRASE


def _env_file(tmp_path, lines):
    path = tmp_path / ".env"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_operator_policy_caps_scheduler_limits():
    policy = OperatorGatePolicy.from_env(
        {
            "SISTER_OPERATOR_GATE_MAX_ACTIONS_PER_TICK": "99",
            "SISTER_CONVERSATION_WINDOW_MAX_DURATION_SEC": "3600",
            "SISTER_CONVERSATION_WINDOW_MAX_MESSAGES": "99",
            "SISTER_CONVERSATION_WINDOW_COOLDOWN_SEC": "60",
            "SISTER_FILE_TRANSFER_COOLDOWN_SEC": "60",
            "SISTER_FILE_TRANSFER_MAX_FILE_BYTES": "9999999",
            "SISTER_FILE_TRANSFER_MAX_TOTAL_BYTES": "9999999",
        }
    )

    assert policy.max_actions_per_tick == 1
    assert policy.max_duration_sec == 900
    assert policy.max_messages == 10
    assert policy.conversation_cooldown_sec == 3600
    assert policy.file_transfer_cooldown_sec == 3600
    assert policy.max_file_bytes == 256 * 1024
    assert policy.max_total_bytes == 512 * 1024


def test_operator_gate_requires_outer_arm_and_honors_kill_switch(tmp_path):
    env = {"SISTER_OPERATOR_GATE": "1", "SISTER_OPERATOR_GATE_ARMED": "1", "SISTER_AUTOCHAT": "0"}
    store = OperatorGateStore(tmp_path)
    policy = OperatorGatePolicy()

    assert operator_gate_arm_status(env)["operator_gate"] is True
    assert validate_operator_gate_send_gate(env, OPERATOR_GATE_CONFIRM_PHRASE, ["conversation"], store, policy) == []

    problems = validate_operator_gate_send_gate(
        {**env, "SISTER_OPERATOR_KILL_SWITCH": "1"},
        OPERATOR_GATE_CONFIRM_PHRASE,
        ["conversation"],
        store,
        policy,
    )

    assert "SISTER_OPERATOR_KILL_SWITCH_enabled" in problems


def test_operator_store_blocks_file_transfer_inside_cooldown(tmp_path):
    store = OperatorGateStore(tmp_path)
    policy = OperatorGatePolicy(file_transfer_cooldown_sec=3600)
    now = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)

    store.record_action_result(
        action=ACTION_FILE_TRANSFER,
        action_id="transfer-1",
        ok=True,
        status=200,
        now=now,
    )

    blocked = store.can_run_file_transfer(policy, now=now + timedelta(minutes=30))
    allowed = store.can_run_file_transfer(policy, now=now + timedelta(hours=2))

    assert blocked.ok is False
    assert blocked.problems == ("file_transfer_cooldown_active",)
    assert allowed.ok is True


def test_cli_dry_run_conversation_redacts_token_and_writes_no_ledger(tmp_path):
    env_file = _env_file(
        tmp_path,
        [
            "SISTER_NODE_URL=http://sister.local",
            "SISTER_SYNC_TOKEN=shared-secret",
            "ESTER_NODE_ID=ester-test",
        ],
    )
    ledger_root = tmp_path / "operator"

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_operator_gate.py",
            "--env-file",
            str(env_file),
            "--ledger-root",
            str(ledger_root),
            "--conversation-ledger-root",
            str(tmp_path / "conversation"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["actions"][0]["action"] == "conversation"
    assert payload["actions"][0]["planned"]["max_messages"] == 10
    assert "shared-secret" not in result.stdout
    assert not ledger_root.exists()


def test_cli_send_fails_closed_without_outer_gate(tmp_path):
    env_file = _env_file(
        tmp_path,
        [
            "SISTER_NODE_URL=http://sister.local",
            "SISTER_SYNC_TOKEN=shared-secret",
            "ESTER_NODE_ID=ester-test",
            "SISTER_CONVERSATION_WINDOW=1",
            "SISTER_CONVERSATION_WINDOW_ARMED=1",
            "SISTER_AUTOCHAT=0",
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_operator_gate.py",
            "--env-file",
            str(env_file),
            "--ledger-root",
            str(tmp_path / "operator"),
            "--conversation-ledger-root",
            str(tmp_path / "conversation"),
            "--send",
            "--confirm-conversation",
            CONVERSATION_WINDOW_CONFIRM_PHRASE,
        ],
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 2
    assert payload["ok"] is False
    assert payload["result"]["body"]["error"] == "send_gate_failed"
    assert "missing_operator_confirm_phrase" in payload["result"]["body"]["problems"]
    assert "SISTER_OPERATOR_GATE_not_enabled" in payload["result"]["body"]["problems"]
    assert "shared-secret" not in result.stdout


def test_cli_successful_conversation_send_writes_operator_and_window_ledgers(tmp_path, monkeypatch, capsys):
    env_file = _env_file(
        tmp_path,
        [
            "SISTER_NODE_URL=http://sister.local",
            "SISTER_SYNC_TOKEN=shared-secret",
            "ESTER_NODE_ID=ester-test",
            "SISTER_OPERATOR_GATE=1",
            "SISTER_OPERATOR_GATE_ARMED=1",
            "SISTER_CONVERSATION_WINDOW=1",
            "SISTER_CONVERSATION_WINDOW_ARMED=1",
            "SISTER_AUTOCHAT=0",
        ],
    )
    operator_root = tmp_path / "operator"
    conversation_root = tmp_path / "conversation"

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def read(self, _limit=-1):
            return json.dumps({"status": "success", "content": "ready"}).encode("utf-8")

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    for key in (
        "SISTER_NODE_URL",
        "SISTER_SYNC_TOKEN",
        "ESTER_NODE_ID",
        "SISTER_OPERATOR_GATE",
        "SISTER_OPERATOR_GATE_ARMED",
        "SISTER_CONVERSATION_WINDOW",
        "SISTER_CONVERSATION_WINDOW_ARMED",
        "SISTER_AUTOCHAT",
    ):
        monkeypatch.delenv(key, raising=False)

    import importlib.util

    spec = importlib.util.spec_from_file_location("synaps_operator_gate_under_test", "tools/synaps_operator_gate.py")
    assert spec and spec.loader
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)

    try:
        exit_code = tool.main(
            [
                "--env-file",
                str(env_file),
                "--ledger-root",
                str(operator_root),
                "--conversation-ledger-root",
                str(conversation_root),
                "--send",
                "--confirm",
                OPERATOR_GATE_CONFIRM_PHRASE,
                "--confirm-conversation",
                CONVERSATION_WINDOW_CONFIRM_PHRASE,
            ]
        )
    finally:
        for key in (
            "SISTER_NODE_URL",
            "SISTER_SYNC_TOKEN",
            "ESTER_NODE_ID",
            "SISTER_OPERATOR_GATE",
            "SISTER_OPERATOR_GATE_ARMED",
            "SISTER_CONVERSATION_WINDOW",
            "SISTER_CONVERSATION_WINDOW_ARMED",
            "SISTER_AUTOCHAT",
        ):
            os.environ.pop(key, None)
    payload = json.loads(capsys.readouterr().out)
    operator_events = [json.loads(line) for line in (operator_root / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    conversation_events = [
        json.loads(line)
        for line in (conversation_root / payload["result"]["window_id"] / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    assert exit_code == 0
    assert payload["ok"] is True
    assert operator_events[-1]["action"] == "conversation"
    assert operator_events[-1]["ok"] is True
    assert [event["event"] for event in conversation_events] == ["opened", "turn", "turn", "closed"]


def test_cli_successful_file_transfer_send_writes_operator_ledger(tmp_path, monkeypatch, capsys):
    env_file = _env_file(
        tmp_path,
        [
            "SISTER_NODE_URL=http://sister.local",
            "SISTER_SYNC_TOKEN=shared-secret",
            "ESTER_NODE_ID=ester-test",
            "SISTER_OPERATOR_GATE=1",
            "SISTER_OPERATOR_GATE_ARMED=1",
            "SISTER_FILE_TRANSFER=1",
            "SISTER_FILE_TRANSFER_ARMED=1",
            "SISTER_AUTOCHAT=0",
            "SISTER_CONVERSATION_WINDOW=0",
        ],
    )
    source = tmp_path / "probe.txt"
    source.write_text("safe payload", encoding="utf-8")
    operator_root = tmp_path / "operator"

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def read(self, _limit=-1):
            return json.dumps({"status": "quarantined", "file_transfer": {"written_count": 1}}).encode("utf-8")

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    for key in (
        "SISTER_NODE_URL",
        "SISTER_SYNC_TOKEN",
        "ESTER_NODE_ID",
        "SISTER_OPERATOR_GATE",
        "SISTER_OPERATOR_GATE_ARMED",
        "SISTER_FILE_TRANSFER",
        "SISTER_FILE_TRANSFER_ARMED",
        "SISTER_AUTOCHAT",
        "SISTER_CONVERSATION_WINDOW",
    ):
        monkeypatch.delenv(key, raising=False)

    import importlib.util

    spec = importlib.util.spec_from_file_location("synaps_operator_gate_file_under_test", "tools/synaps_operator_gate.py")
    assert spec and spec.loader
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)

    try:
        exit_code = tool.main(
            [
                "--action",
                "file-transfer",
                "--env-file",
                str(env_file),
                "--ledger-root",
                str(operator_root),
                "--file",
                str(source),
                "--include-payload",
                "--send",
                "--confirm",
                OPERATOR_GATE_CONFIRM_PHRASE,
                "--confirm-file-transfer",
                FILE_TRANSFER_CONFIRM_PHRASE,
            ]
        )
    finally:
        for key in (
            "SISTER_NODE_URL",
            "SISTER_SYNC_TOKEN",
            "ESTER_NODE_ID",
            "SISTER_OPERATOR_GATE",
            "SISTER_OPERATOR_GATE_ARMED",
            "SISTER_FILE_TRANSFER",
            "SISTER_FILE_TRANSFER_ARMED",
            "SISTER_AUTOCHAT",
            "SISTER_CONVERSATION_WINDOW",
        ):
            os.environ.pop(key, None)
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)
    operator_events = [json.loads(line) for line in (operator_root / "events.jsonl").read_text(encoding="utf-8").splitlines()]

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["result"]["transfer_id"].startswith("synaps-file-")
    assert operator_events[-1]["action"] == "file_transfer"
    assert operator_events[-1]["summary"]["memory"] == "off"
    assert "shared-secret" not in stdout
    assert "c2FmZSBwYXlsb2Fk" not in stdout


def test_cli_send_both_actions_fails_closed(tmp_path):
    env_file = _env_file(
        tmp_path,
        [
            "SISTER_NODE_URL=http://sister.local",
            "SISTER_SYNC_TOKEN=shared-secret",
            "ESTER_NODE_ID=ester-test",
            "SISTER_OPERATOR_GATE=1",
            "SISTER_OPERATOR_GATE_ARMED=1",
            "SISTER_AUTOCHAT=0",
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_operator_gate.py",
            "--action",
            "both",
            "--env-file",
            str(env_file),
            "--ledger-root",
            str(tmp_path / "operator"),
            "--send",
            "--confirm",
            OPERATOR_GATE_CONFIRM_PHRASE,
        ],
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 2
    assert "operator_gate_allows_one_action_per_tick" in payload["result"]["body"]["problems"]


def test_cli_bootstraps_env_before_modules_imports():
    source = open("tools/synaps_operator_gate.py", encoding="utf-8").read()
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
