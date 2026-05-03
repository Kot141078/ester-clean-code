import hashlib
import json
import os
import subprocess
import sys

from modules.synaps import (
    CODEX_COORDINATION_RELAY_PLAN_SCHEMA,
    CODEX_COORDINATION_RELAY_TICK_CONFIRM_PHRASE,
    CODEX_COORDINATION_RELAY_TICK_SCHEMA,
    CodexCoordinationRelayPlanSelector,
    list_codex_front_claims,
    run_codex_coordination_relay_tick,
    validate_codex_coordination_relay_tick_gate,
)


def _env(**extra):
    base = {
        "SYNAPS_CODEX_COORDINATION_RELAY_TICK": "1",
        "SYNAPS_CODEX_COORDINATION_RELAY_TICK_ARMED": "1",
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
        "relay_root": tmp_path / "relay",
        "session_root": tmp_path / "session",
    }


def _write_relay_plan(tmp_path, name="relay.json"):
    plan = {
        "schema": CODEX_COORDINATION_RELAY_PLAN_SCHEMA,
        "relay_id": name.replace(".json", ""),
        "operator": "relay-test",
        "marker": "relay tick marker",
        "request": {"file": str(tmp_path / "request.md"), "base_dir": str(tmp_path), "kind": "codex_contract"},
        "contract": {"expect_name": "contract.md", "expect_sender": "liah-test", "expect_sha256": "a" * 64, "expect_size": 1},
        "response": {"file": str(tmp_path / "response.md"), "base_dir": str(tmp_path), "kind": "codex_report"},
        "final_report": {"expect_name": "final.md", "expect_sender": "liah-test", "expect_sha256": "b" * 64, "expect_size": 1},
    }
    queue = tmp_path / "queue"
    queue.mkdir(exist_ok=True)
    path = queue / name
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def _add_front_claim(path, tmp_path, *, marker="claim-guarded-relay-tick"):
    plan = json.loads(path.read_text(encoding="utf-8"))
    plan["front_claim"] = {
        "root": str(tmp_path / "front_claims"),
        "front_id": "0102",
        "owner": "ester-test",
        "marker": marker,
        "title": "claim guarded relay tick",
        "lease_sec": 600,
        "expect_name": "final.md",
        "expect_sender": "liah-test",
        "expect_note_contains": "relay tick marker",
        "expect_sha256": "b" * 64,
        "expect_size": 1,
    }
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def _sha_size(path):
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def test_relay_tick_gate_blocks_missing_and_unsafe_flags():
    assert validate_codex_coordination_relay_tick_gate(_env(), confirm=CODEX_COORDINATION_RELAY_TICK_CONFIRM_PHRASE) == []

    missing = validate_codex_coordination_relay_tick_gate({}, confirm="")
    assert "missing_codex_coordination_relay_tick_confirm_phrase" in missing
    assert "SYNAPS_CODEX_COORDINATION_RELAY_TICK_not_enabled" in missing

    unsafe = validate_codex_coordination_relay_tick_gate(
        _env(SISTER_AUTOCHAT="1", SYNAPS_CODEX_DAEMON_RUNNER="1", SISTER_SCHEDULE="1"),
        confirm=CODEX_COORDINATION_RELAY_TICK_CONFIRM_PHRASE,
    )
    assert "SISTER_AUTOCHAT_must_remain_disabled" in unsafe
    assert "SYNAPS_CODEX_DAEMON_RUNNER_must_remain_disabled" in unsafe
    assert "SISTER_SCHEDULE_must_remain_disabled" in unsafe


def test_relay_tick_empty_queue_stops_with_no_work(tmp_path):
    payload = run_codex_coordination_relay_tick(
        env=_env(),
        env_file="",
        confirm=CODEX_COORDINATION_RELAY_TICK_CONFIRM_PHRASE,
        **_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["schema"] == CODEX_COORDINATION_RELAY_TICK_SCHEMA
    assert payload["result"]["status"] == "no_queued_plan"


def test_relay_tick_runs_one_plan_marks_completed(tmp_path):
    _write_relay_plan(tmp_path)

    def fake_relay(**kwargs):
        assert kwargs["env"]["SYNAPS_CODEX_COORDINATION_RELAY"] == "1"
        assert kwargs["env"]["SYNAPS_CODEX_COORDINATION_RELAY_ARMED"] == "1"
        return {"ok": True, "result": {"status": "relay_complete"}, "session": {"steps": []}}

    payload = run_codex_coordination_relay_tick(
        env=_env(),
        env_file="",
        confirm=CODEX_COORDINATION_RELAY_TICK_CONFIRM_PHRASE,
        relay_fn=fake_relay,
        **_roots(tmp_path),
    )
    ledger = (tmp_path / "tick" / "events.jsonl").read_text(encoding="utf-8")

    assert payload["ok"] is True
    assert payload["result"]["status"] == "relay_tick_completed"
    assert list((tmp_path / "completed").glob("*.json"))
    assert "payload_b64" not in ledger
    assert "shared-secret" not in ledger
    assert '"content"' not in ledger


def test_relay_tick_front_claim_guard_closes_on_success(tmp_path):
    _add_front_claim(_write_relay_plan(tmp_path), tmp_path)

    def fake_relay(**kwargs):
        assert kwargs["env"]["SYNAPS_CODEX_COORDINATION_RELAY"] == "1"
        assert kwargs["env"]["SYNAPS_CODEX_COORDINATION_RELAY_ARMED"] == "1"
        return {"ok": True, "result": {"status": "relay_complete"}, "session": {"steps": []}}

    payload = run_codex_coordination_relay_tick(
        env=_env(SYNAPS_CODEX_FRONT_CLAIM="1", SYNAPS_CODEX_FRONT_CLAIM_ARMED="1"),
        env_file="",
        confirm=CODEX_COORDINATION_RELAY_TICK_CONFIRM_PHRASE,
        relay_fn=fake_relay,
        **_roots(tmp_path),
    )
    claims = list_codex_front_claims(tmp_path / "front_claims")

    assert payload["ok"] is True
    assert payload["front_claim"]["result"]["status"] == "front_claim_written"
    assert payload["front_claim_close"]["result"]["status"] == "front_claim_closed"
    assert payload["front_claim_close"]["claim"]["status"] == "completed"
    assert payload["result"]["status"] == "relay_tick_completed"
    assert claims["claim_count"] == 1
    assert claims["active_count"] == 0
    assert claims["claims"][0]["status"] == "completed"
    assert list((tmp_path / "completed").glob("*.json"))


def test_relay_tick_front_claim_guard_fails_closed_without_claim_gate(tmp_path):
    _add_front_claim(_write_relay_plan(tmp_path), tmp_path, marker="claim-gate-missing")
    calls = []

    def fake_relay(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "result": {"status": "relay_complete"}}

    payload = run_codex_coordination_relay_tick(
        env=_env(),
        env_file="",
        confirm=CODEX_COORDINATION_RELAY_TICK_CONFIRM_PHRASE,
        relay_fn=fake_relay,
        **_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert calls == []
    assert payload["result"]["status"] == "relay_tick_failed"
    assert payload["result"]["error"] == "front_claim_write_failed"
    assert payload["front_claim"]["result"]["status"] == "front_claim_gate_failed"
    assert "SYNAPS_CODEX_FRONT_CLAIM_not_enabled" in payload["front_claim"]["problems"]
    assert list((tmp_path / "failed").glob("*.json"))
    assert not (tmp_path / "front_claims" / "claims").exists()


def test_relay_tick_front_claim_guard_closes_failed_on_relay_failure(tmp_path):
    _add_front_claim(_write_relay_plan(tmp_path), tmp_path, marker="claim-relay-failed")

    def fake_relay(**kwargs):
        return {"ok": False, "result": {"status": "relay_failed"}, "problems": ["boom"]}

    payload = run_codex_coordination_relay_tick(
        env=_env(SYNAPS_CODEX_FRONT_CLAIM="1", SYNAPS_CODEX_FRONT_CLAIM_ARMED="1"),
        env_file="",
        confirm=CODEX_COORDINATION_RELAY_TICK_CONFIRM_PHRASE,
        relay_fn=fake_relay,
        **_roots(tmp_path),
    )
    claims = list_codex_front_claims(tmp_path / "front_claims")

    assert payload["ok"] is False
    assert payload["front_claim"]["result"]["status"] == "front_claim_written"
    assert payload["front_claim_close"]["result"]["status"] == "front_claim_closed"
    assert payload["front_claim_close"]["claim"]["status"] == "failed"
    assert payload["result"]["status"] == "relay_tick_failed"
    assert claims["active_count"] == 0
    assert claims["claims"][0]["status"] == "failed"
    assert list((tmp_path / "failed").glob("*.json"))


def test_relay_tick_failed_plan_marks_failed_and_repeat_no_work(tmp_path):
    _write_relay_plan(tmp_path)

    def fake_relay(**kwargs):
        return {"ok": False, "result": {"status": "relay_failed"}, "problems": ["boom"]}

    payload = run_codex_coordination_relay_tick(
        env=_env(),
        env_file="",
        confirm=CODEX_COORDINATION_RELAY_TICK_CONFIRM_PHRASE,
        relay_fn=fake_relay,
        **_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "relay_tick_failed"
    assert list((tmp_path / "failed").glob("*.json"))

    repeat = run_codex_coordination_relay_tick(
        env=_env(),
        env_file="",
        confirm=CODEX_COORDINATION_RELAY_TICK_CONFIRM_PHRASE,
        relay_fn=fake_relay,
        **_roots(tmp_path),
    )
    assert repeat["ok"] is True
    assert repeat["result"]["status"] == "no_queued_plan"


def test_relay_tick_multiple_plans_fail_without_exact_selector(tmp_path):
    _write_relay_plan(tmp_path, name="one.json")
    _write_relay_plan(tmp_path, name="two.json")

    payload = run_codex_coordination_relay_tick(
        env=_env(),
        env_file="",
        confirm=CODEX_COORDINATION_RELAY_TICK_CONFIRM_PHRASE,
        **_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert "expected_exactly_one_relay_plan:2" in payload["problems"]


def test_relay_tick_exact_selector_selects_one_plan(tmp_path):
    _write_relay_plan(tmp_path, name="one.json")
    selected = _write_relay_plan(tmp_path, name="two.json")
    sha, size = _sha_size(selected)

    def fake_relay(**kwargs):
        return {"ok": True, "result": {"status": "relay_complete"}}

    payload = run_codex_coordination_relay_tick(
        env=_env(),
        env_file="",
        selector=CodexCoordinationRelayPlanSelector("two.json", sha, size),
        confirm=CODEX_COORDINATION_RELAY_TICK_CONFIRM_PHRASE,
        relay_fn=fake_relay,
        **_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["selected_plan"]["name"] == "two.json"


def test_cli_relay_tick_empty_queue(tmp_path):
    env = os.environ.copy()
    env.update(_env())

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_coordination_relay_tick.py",
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
            "--relay-root",
            str(tmp_path / "relay"),
            "--session-root",
            str(tmp_path / "session"),
            "--confirm",
            CODEX_COORDINATION_RELAY_TICK_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["result"]["status"] == "no_queued_plan"
