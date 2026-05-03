import json
import os
import subprocess
import sys

from modules.synaps import (
    CODEX_COORDINATION_SESSION_PLAN_SCHEMA,
    CODEX_COORDINATION_SESSION_TICK_CONFIRM_PHRASE,
    CODEX_COORDINATION_SESSION_TICK_SCHEMA,
    CodexCoordinationSessionPlanSelector,
    run_codex_coordination_session_tick,
    validate_codex_coordination_session_tick_gate,
)


def _env(**extra):
    base = {
        "SYNAPS_CODEX_COORDINATION_SESSION_TICK": "1",
        "SYNAPS_CODEX_COORDINATION_SESSION_TICK_ARMED": "1",
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
        "ledger_path": tmp_path / "tick" / "events.jsonl",
        "session_root": tmp_path / "session",
    }


def _write_send_plan(tmp_path, name="plan.json", *, include_payload=True, send=False, marker="SAFE_BODY"):
    source = tmp_path / "handoffs" / "contract.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(f"# contract\n{marker}\n", encoding="utf-8")
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
                "note": "tick send dry-run",
                "include_payload": include_payload,
                "send": send,
            }
        ],
    }
    queue = tmp_path / "queue"
    queue.mkdir(exist_ok=True)
    path = queue / name
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def _sha_size(path):
    import hashlib

    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def test_session_tick_gate_blocks_missing_and_unsafe_flags():
    assert validate_codex_coordination_session_tick_gate(_env(), confirm=CODEX_COORDINATION_SESSION_TICK_CONFIRM_PHRASE) == []

    missing = validate_codex_coordination_session_tick_gate({}, confirm="")
    assert "missing_codex_coordination_session_tick_confirm_phrase" in missing
    assert "SYNAPS_CODEX_COORDINATION_SESSION_TICK_not_enabled" in missing

    unsafe = validate_codex_coordination_session_tick_gate(
        _env(SISTER_AUTOCHAT="1", SYNAPS_CODEX_DAEMON_RUNNER="1", SISTER_SCHEDULE="1"),
        confirm=CODEX_COORDINATION_SESSION_TICK_CONFIRM_PHRASE,
    )
    assert "SISTER_AUTOCHAT_must_remain_disabled" in unsafe
    assert "SYNAPS_CODEX_DAEMON_RUNNER_must_remain_disabled" in unsafe
    assert "SISTER_SCHEDULE_must_remain_disabled" in unsafe


def test_session_tick_runs_one_plan_marks_completed_and_repeat_no_work(tmp_path):
    plan = _write_send_plan(tmp_path, marker="SECRET_BODY_MARKER")
    payload = run_codex_coordination_session_tick(
        env=_env(),
        env_file="",
        confirm=CODEX_COORDINATION_SESSION_TICK_CONFIRM_PHRASE,
        postcheck_roots=[tmp_path / "memory"],
        **_roots(tmp_path),
    )

    dumped = json.dumps(payload, ensure_ascii=False)
    assert payload["ok"] is True
    assert payload["schema"] == CODEX_COORDINATION_SESSION_TICK_SCHEMA
    assert payload["result"]["status"] == "tick_completed"
    assert payload["session"]["result"]["status"] == "session_complete"
    assert "payload_b64" not in dumped
    assert '"token"' not in dumped
    assert "SECRET_BODY_MARKER" not in dumped
    assert list((tmp_path / "completed").glob("*.json"))

    repeat = run_codex_coordination_session_tick(
        env=_env(),
        env_file="",
        confirm=CODEX_COORDINATION_SESSION_TICK_CONFIRM_PHRASE,
        **_roots(tmp_path),
    )
    assert repeat["ok"] is True
    assert repeat["result"]["status"] == "no_queued_plan"
    assert repeat["candidate_count"] == 0
    assert plan.exists()


def test_session_tick_failed_plan_marks_failed_and_repeat_no_work(tmp_path):
    _write_send_plan(tmp_path, include_payload=False, send=True)

    payload = run_codex_coordination_session_tick(
        env=_env(),
        env_file="",
        confirm=CODEX_COORDINATION_SESSION_TICK_CONFIRM_PHRASE,
        **_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "tick_failed"
    assert list((tmp_path / "failed").glob("*.json"))

    repeat = run_codex_coordination_session_tick(
        env=_env(),
        env_file="",
        confirm=CODEX_COORDINATION_SESSION_TICK_CONFIRM_PHRASE,
        **_roots(tmp_path),
    )
    assert repeat["ok"] is True
    assert repeat["result"]["status"] == "no_queued_plan"


def test_session_tick_multiple_plans_fail_without_exact_selector(tmp_path):
    _write_send_plan(tmp_path, name="one.json")
    _write_send_plan(tmp_path, name="two.json")

    payload = run_codex_coordination_session_tick(
        env=_env(),
        env_file="",
        confirm=CODEX_COORDINATION_SESSION_TICK_CONFIRM_PHRASE,
        **_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert "expected_exactly_one_plan:2" in payload["problems"]


def test_session_tick_exact_selector_selects_one_plan(tmp_path):
    _write_send_plan(tmp_path, name="one.json")
    selected = _write_send_plan(tmp_path, name="two.json")
    sha, size = _sha_size(selected)

    payload = run_codex_coordination_session_tick(
        env=_env(),
        env_file="",
        selector=CodexCoordinationSessionPlanSelector("two.json", sha, size),
        confirm=CODEX_COORDINATION_SESSION_TICK_CONFIRM_PHRASE,
        **_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["selected_plan"]["name"] == "two.json"


def test_session_tick_symlink_escape_is_ignored_or_rejected(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    queue = tmp_path / "queue"
    queue.mkdir()
    link = queue / "escape.json"
    try:
        link.symlink_to(outside)
    except OSError:
        return

    payload = run_codex_coordination_session_tick(
        env=_env(),
        env_file="",
        confirm=CODEX_COORDINATION_SESSION_TICK_CONFIRM_PHRASE,
        **_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["result"]["status"] == "no_queued_plan"


def test_session_tick_postcheck_marker_fails_closed(tmp_path):
    plan = _write_send_plan(tmp_path)
    memory = tmp_path / "memory"
    memory.mkdir()
    (memory / "leak.txt").write_text(plan.name, encoding="utf-8")

    payload = run_codex_coordination_session_tick(
        env=_env(),
        env_file="",
        confirm=CODEX_COORDINATION_SESSION_TICK_CONFIRM_PHRASE,
        postcheck_roots=[memory],
        **_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert "postcheck_marker_found" in payload["problems"]


def test_cli_session_tick_runs_one_plan(tmp_path):
    _write_send_plan(tmp_path, name="cli.json")
    env = os.environ.copy()
    env.update(_env())

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_coordination_session_tick.py",
            "--env-file",
            "",
            "--queue-root",
            str(tmp_path / "queue"),
            "--completed-root",
            str(tmp_path / "completed"),
            "--failed-root",
            str(tmp_path / "failed"),
            "--ledger",
            str(tmp_path / "tick" / "events.jsonl"),
            "--session-root",
            str(tmp_path / "session"),
            "--confirm",
            CODEX_COORDINATION_SESSION_TICK_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["result"]["status"] == "tick_completed"
