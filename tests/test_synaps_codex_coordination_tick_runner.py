import json
import os
import subprocess
import sys

from modules.synaps import (
    CODEX_COORDINATION_SESSION_PLAN_SCHEMA,
    CODEX_COORDINATION_TICK_RUNNER_CONFIRM_PHRASE,
    CODEX_COORDINATION_TICK_RUNNER_SCHEMA,
    CodexCoordinationTickRunnerPolicy,
    run_codex_coordination_tick_runner,
    validate_codex_coordination_tick_runner_gate,
)


def _env(**extra):
    base = {
        "SYNAPS_CODEX_COORDINATION_TICK_RUNNER": "1",
        "SYNAPS_CODEX_COORDINATION_TICK_RUNNER_ARMED": "1",
        "SISTER_AUTOCHAT": "0",
        "SISTER_NODE_URL": "http://sister.local",
        "SISTER_SYNC_TOKEN": "shared-secret",
        "ESTER_NODE_ID": "ester-test",
    }
    base.update(extra)
    return base


def _roots(tmp_path):
    return {
        "queue_root": tmp_path / "queue",
        "completed_root": tmp_path / "completed",
        "failed_root": tmp_path / "failed",
        "tick_ledger_path": tmp_path / "tick" / "events.jsonl",
        "runner_ledger_path": tmp_path / "runner" / "events.jsonl",
        "session_root": tmp_path / "session",
    }


def _write_send_plan(tmp_path, name="plan.json"):
    source = tmp_path / "handoffs" / "contract.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# contract\nSAFE\n", encoding="utf-8")
    plan = {
        "schema": CODEX_COORDINATION_SESSION_PLAN_SCHEMA,
        "session_id": name.replace(".json", ""),
        "steps": [
            {
                "phase": "send_file",
                "nonce": f"{name}-send",
                "file": str(source),
                "base_dir": str(source.parent),
                "kind": "codex_contract",
                "note": "runner dry-run",
                "include_payload": True,
                "send": False,
            }
        ],
    }
    queue = tmp_path / "queue"
    queue.mkdir(exist_ok=True)
    path = queue / name
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def test_tick_runner_gate_blocks_missing_and_unsafe_flags():
    assert validate_codex_coordination_tick_runner_gate(_env(), confirm=CODEX_COORDINATION_TICK_RUNNER_CONFIRM_PHRASE) == []

    missing = validate_codex_coordination_tick_runner_gate({}, confirm="")
    assert "missing_codex_coordination_tick_runner_confirm_phrase" in missing
    assert "SYNAPS_CODEX_COORDINATION_TICK_RUNNER_not_enabled" in missing

    unsafe = validate_codex_coordination_tick_runner_gate(
        _env(SISTER_AUTOCHAT="1", SYNAPS_CODEX_DAEMON_PERSISTENT="1", SISTER_SCHEDULE="1"),
        confirm=CODEX_COORDINATION_TICK_RUNNER_CONFIRM_PHRASE,
    )
    assert "SISTER_AUTOCHAT_must_remain_disabled" in unsafe
    assert "SYNAPS_CODEX_DAEMON_PERSISTENT_must_remain_disabled" in unsafe
    assert "SISTER_SCHEDULE_must_remain_disabled" in unsafe


def test_tick_runner_empty_queue_stops_with_no_work(tmp_path):
    payload = run_codex_coordination_tick_runner(
        env=_env(),
        env_file="",
        confirm=CODEX_COORDINATION_TICK_RUNNER_CONFIRM_PHRASE,
        policy=CodexCoordinationTickRunnerPolicy(max_ticks=3),
        **_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["schema"] == CODEX_COORDINATION_TICK_RUNNER_SCHEMA
    assert payload["result"]["status"] == "no_queued_plan"
    assert len(payload["ticks"]) == 1


def test_tick_runner_runs_one_plan_and_writes_redacted_ledger(tmp_path):
    _write_send_plan(tmp_path)

    payload = run_codex_coordination_tick_runner(
        env=_env(),
        env_file="",
        confirm=CODEX_COORDINATION_TICK_RUNNER_CONFIRM_PHRASE,
        policy=CodexCoordinationTickRunnerPolicy(max_ticks=1),
        **_roots(tmp_path),
    )
    ledger = (tmp_path / "runner" / "events.jsonl").read_text(encoding="utf-8")

    assert payload["ok"] is True
    assert payload["result"]["status"] == "max_ticks_reached"
    assert payload["ticks"][0]["status"] == "tick_completed"
    assert "payload_b64" not in ledger
    assert "shared-secret" not in ledger
    assert '"content"' not in ledger


def test_tick_runner_lease_collision_fails_closed(tmp_path):
    lock = tmp_path / "runner" / "locks" / "bounded_tick_runner.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("busy", encoding="utf-8")

    payload = run_codex_coordination_tick_runner(
        env=_env(),
        env_file="",
        confirm=CODEX_COORDINATION_TICK_RUNNER_CONFIRM_PHRASE,
        **_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "runner_failed"
    assert payload["result"]["error"] == "FileExistsError"


def test_tick_runner_tick_failure_stops_later_ticks(tmp_path):
    calls = []

    def fake_tick(**kwargs):
        calls.append(kwargs)
        return {"ok": False, "result": {"status": "tick_failed"}, "candidate_count": 1}

    payload = run_codex_coordination_tick_runner(
        env=_env(),
        env_file="",
        confirm=CODEX_COORDINATION_TICK_RUNNER_CONFIRM_PHRASE,
        policy=CodexCoordinationTickRunnerPolicy(max_ticks=3),
        tick_fn=fake_tick,
        **_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "tick_failed"
    assert len(calls) == 1


def test_tick_runner_env_change_between_ticks_fails_closed(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("A=1\n", encoding="utf-8")

    def fake_tick(**kwargs):
        env_file.write_text("A=222\n", encoding="utf-8")
        return {"ok": True, "result": {"status": "tick_completed"}, "candidate_count": 1}

    payload = run_codex_coordination_tick_runner(
        env=_env(),
        env_file=env_file,
        confirm=CODEX_COORDINATION_TICK_RUNNER_CONFIRM_PHRASE,
        policy=CodexCoordinationTickRunnerPolicy(max_ticks=2),
        tick_fn=fake_tick,
        **_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "env_file_changed"


def test_cli_tick_runner_empty_queue(tmp_path):
    env = os.environ.copy()
    env.update(_env())

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_coordination_tick_runner.py",
            "--env-file",
            "",
            "--queue-root",
            str(tmp_path / "queue"),
            "--completed-root",
            str(tmp_path / "completed"),
            "--failed-root",
            str(tmp_path / "failed"),
            "--tick-ledger",
            str(tmp_path / "tick" / "events.jsonl"),
            "--runner-ledger",
            str(tmp_path / "runner" / "events.jsonl"),
            "--session-root",
            str(tmp_path / "session"),
            "--confirm",
            CODEX_COORDINATION_TICK_RUNNER_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["result"]["status"] == "no_queued_plan"
