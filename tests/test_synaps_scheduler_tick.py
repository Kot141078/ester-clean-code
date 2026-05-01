import ast
import importlib.util
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

from modules.synaps import (
    CONVERSATION_WINDOW_CONFIRM_PHRASE,
    OPERATOR_GATE_CONFIRM_PHRASE,
    SCHEDULER_CONFIRM_PHRASE,
    SchedulerPolicy,
    SchedulerTickStore,
    scheduler_arm_status,
    validate_scheduler_send_gate,
)


def _env_file(tmp_path, lines):
    path = tmp_path / ".env"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_scheduler_policy_caps_interval_and_actions():
    policy = SchedulerPolicy.from_env(
        {
            "SISTER_SCHEDULE_INTERVAL_SEC": "60",
            "SISTER_SCHEDULE_MAX_ACTIONS_PER_TICK": "99",
            "SISTER_SCHEDULE_ALLOW_FILE_TRANSFER": "1",
        }
    )

    assert policy.interval_sec == 3600
    assert policy.max_actions_per_tick == 1
    assert policy.allow_file_transfer is True


def test_scheduler_gate_requires_outer_arm_and_honors_kill_switch(tmp_path):
    env = {"SISTER_SCHEDULE": "1", "SISTER_SCHEDULE_ARMED": "1", "SISTER_AUTOCHAT": "0"}
    store = SchedulerTickStore(tmp_path)
    policy = SchedulerPolicy()

    assert scheduler_arm_status(env)["schedule"] is True
    assert validate_scheduler_send_gate(env, SCHEDULER_CONFIRM_PHRASE, ["conversation"], store, policy) == []

    problems = validate_scheduler_send_gate(
        {**env, "SISTER_SCHEDULE_KILL_SWITCH": "1"},
        SCHEDULER_CONFIRM_PHRASE,
        ["conversation"],
        store,
        policy,
    )

    assert "SISTER_SCHEDULE_KILL_SWITCH_enabled" in problems


def test_scheduler_store_blocks_second_tick_inside_hour(tmp_path):
    store = SchedulerTickStore(tmp_path)
    policy = SchedulerPolicy(interval_sec=3600)
    now = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)

    store.record_tick_result(action="conversation", action_id="w1", ok=True, status=200, now=now)
    blocked = store.can_run("conversation", policy, now=now + timedelta(minutes=30))
    allowed = store.can_run("conversation", policy, now=now + timedelta(hours=2))

    assert blocked.ok is False
    assert blocked.problems == ("schedule_interval_active",)
    assert allowed.ok is True


def test_scheduler_file_transfer_requires_explicit_schedule_allow(tmp_path):
    env = {
        "SISTER_SCHEDULE": "1",
        "SISTER_SCHEDULE_ARMED": "1",
        "SISTER_AUTOCHAT": "0",
    }
    problems = validate_scheduler_send_gate(
        env,
        SCHEDULER_CONFIRM_PHRASE,
        ["file-transfer"],
        SchedulerTickStore(tmp_path),
        SchedulerPolicy(allow_file_transfer=False),
    )

    assert "SISTER_SCHEDULE_ALLOW_FILE_TRANSFER_not_enabled" in problems


def test_cli_dry_run_conversation_redacts_token_and_writes_no_ledger(tmp_path):
    env_file = _env_file(
        tmp_path,
        [
            "SISTER_NODE_URL=http://sister.local",
            "SISTER_SYNC_TOKEN=shared-secret",
            "ESTER_NODE_ID=ester-test",
        ],
    )
    scheduler_root = tmp_path / "scheduler"

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_scheduler_tick.py",
            "--env-file",
            str(env_file),
            "--scheduler-ledger-root",
            str(scheduler_root),
            "--operator-ledger-root",
            str(tmp_path / "operator"),
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
    assert payload["policy"]["interval_sec"] == 3600
    assert payload["action_plan"]["planned"]["max_messages"] == 10
    assert "shared-secret" not in result.stdout
    assert not scheduler_root.exists()


def test_cli_send_fails_closed_without_schedule_flags(tmp_path):
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
    scheduler_root = tmp_path / "scheduler"

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_scheduler_tick.py",
            "--env-file",
            str(env_file),
            "--scheduler-ledger-root",
            str(scheduler_root),
            "--operator-ledger-root",
            str(tmp_path / "operator"),
            "--conversation-ledger-root",
            str(tmp_path / "conversation"),
            "--send",
            "--confirm-operator",
            OPERATOR_GATE_CONFIRM_PHRASE,
            "--confirm-conversation",
            CONVERSATION_WINDOW_CONFIRM_PHRASE,
        ],
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 2
    assert payload["result"]["body"]["error"] == "send_gate_failed"
    assert "missing_schedule_confirm_phrase" in payload["result"]["body"]["problems"]
    assert "SISTER_SCHEDULE_not_enabled" in payload["result"]["body"]["problems"]
    assert "shared-secret" not in result.stdout
    assert not scheduler_root.exists()


def test_cli_successful_conversation_send_writes_scheduler_operator_and_window_ledgers(
    tmp_path,
    monkeypatch,
    capsys,
):
    env_file = _env_file(
        tmp_path,
        [
            "SISTER_NODE_URL=http://sister.local",
            "SISTER_SYNC_TOKEN=shared-secret",
            "ESTER_NODE_ID=ester-test",
            "SISTER_SCHEDULE=1",
            "SISTER_SCHEDULE_ARMED=1",
            "SISTER_OPERATOR_GATE=1",
            "SISTER_OPERATOR_GATE_ARMED=1",
            "SISTER_CONVERSATION_WINDOW=1",
            "SISTER_CONVERSATION_WINDOW_ARMED=1",
            "SISTER_AUTOCHAT=0",
        ],
    )
    scheduler_root = tmp_path / "scheduler"
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
        "SISTER_SCHEDULE",
        "SISTER_SCHEDULE_ARMED",
        "SISTER_OPERATOR_GATE",
        "SISTER_OPERATOR_GATE_ARMED",
        "SISTER_CONVERSATION_WINDOW",
        "SISTER_CONVERSATION_WINDOW_ARMED",
        "SISTER_AUTOCHAT",
    ):
        monkeypatch.delenv(key, raising=False)

    spec = importlib.util.spec_from_file_location("synaps_scheduler_tick_under_test", "tools/synaps_scheduler_tick.py")
    assert spec and spec.loader
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)

    try:
        exit_code = tool.main(
            [
                "--env-file",
                str(env_file),
                "--scheduler-ledger-root",
                str(scheduler_root),
                "--operator-ledger-root",
                str(operator_root),
                "--conversation-ledger-root",
                str(conversation_root),
                "--send",
                "--confirm",
                SCHEDULER_CONFIRM_PHRASE,
                "--confirm-operator",
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
            "SISTER_SCHEDULE",
            "SISTER_SCHEDULE_ARMED",
            "SISTER_OPERATOR_GATE",
            "SISTER_OPERATOR_GATE_ARMED",
            "SISTER_CONVERSATION_WINDOW",
            "SISTER_CONVERSATION_WINDOW_ARMED",
            "SISTER_AUTOCHAT",
        ):
            os.environ.pop(key, None)
    payload = json.loads(capsys.readouterr().out)
    scheduler_events = [
        json.loads(line) for line in (scheduler_root / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    operator_events = [
        json.loads(line) for line in (operator_root / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    conversation_events = [
        json.loads(line)
        for line in (conversation_root / payload["result"]["window_id"] / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    assert exit_code == 0
    assert payload["ok"] is True
    assert scheduler_events[-1]["action"] == "conversation"
    assert scheduler_events[-1]["summary"]["memory"] == "off"
    assert operator_events[-1]["summary"]["files"] == "manifest_only"
    assert [event["event"] for event in conversation_events] == ["opened", "turn", "turn", "closed"]


def test_cli_bootstraps_env_before_modules_or_tools_imports():
    source = open("tools/synaps_scheduler_tick.py", encoding="utf-8").read()
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
