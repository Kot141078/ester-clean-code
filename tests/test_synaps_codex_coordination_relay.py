import json
import os
import subprocess
import sys

from modules.synaps import (
    CODEX_COORDINATION_RELAY_CONFIRM_PHRASE,
    CODEX_COORDINATION_RELAY_PLAN_SCHEMA,
    CODEX_COORDINATION_RELAY_SCHEMA,
    CODEX_COORDINATION_SESSION_CONFIRM_PHRASE,
    CODEX_COORDINATION_SESSION_PLAN_SCHEMA,
    SynapsValidationError,
    build_codex_coordination_relay_session_plan,
    dry_run_codex_coordination_relay,
    run_codex_coordination_relay,
    validate_codex_coordination_relay_gate,
)


def _env(**extra):
    base = {
        "SYNAPS_CODEX_COORDINATION_RELAY": "1",
        "SYNAPS_CODEX_COORDINATION_RELAY_ARMED": "1",
        "SISTER_AUTOCHAT": "0",
        "SISTER_NODE_URL": "http://sister.local",
        "SISTER_SYNC_TOKEN": "shared-secret",
        "ESTER_NODE_ID": "ester-test",
    }
    base.update(extra)
    return base


def _relay_plan(tmp_path):
    source = tmp_path / "handoffs"
    source.mkdir()
    request = source / "request.md"
    response = source / "response.md"
    request.write_text("# request\n", encoding="utf-8")
    response.write_text("# response\n", encoding="utf-8")
    return {
        "schema": CODEX_COORDINATION_RELAY_PLAN_SCHEMA,
        "relay_id": "relay-0087",
        "operator": "ester-test",
        "marker": "relay-marker-0087",
        "request": {
            "file": str(request),
            "base_dir": str(source),
            "kind": "codex_contract",
        },
        "contract": {
            "expect_name": "contract.md",
            "expect_kind": "codex_contract",
            "expect_sender": "liah-test",
            "expect_sha256": "a" * 64,
            "expect_size": 123,
            "max_cycles": 2,
            "sleep_sec": 0,
        },
        "response": {
            "file": str(response),
            "base_dir": str(source),
            "kind": "codex_report",
            "send_timeout_sec": 12.5,
        },
        "final_report": {
            "expect_name": "final.md",
            "expect_sender": "liah-test",
            "expect_sha256": "b" * 64,
            "expect_size": 456,
            "max_cycles": 2,
            "sleep_sec": 0,
        },
    }


def test_coordination_relay_gate_blocks_missing_and_unsafe_flags():
    assert validate_codex_coordination_relay_gate(_env(), confirm=CODEX_COORDINATION_RELAY_CONFIRM_PHRASE) == []

    missing = validate_codex_coordination_relay_gate({}, confirm="")
    assert "missing_codex_coordination_relay_confirm_phrase" in missing
    assert "SYNAPS_CODEX_COORDINATION_RELAY_not_enabled" in missing

    unsafe = validate_codex_coordination_relay_gate(
        _env(SISTER_AUTOCHAT="1", SYNAPS_CODEX_DAEMON_RUNNER="1"),
        confirm=CODEX_COORDINATION_RELAY_CONFIRM_PHRASE,
    )
    assert "SISTER_AUTOCHAT_must_remain_disabled" in unsafe
    assert "SYNAPS_CODEX_DAEMON_RUNNER_must_remain_disabled" in unsafe


def test_build_coordination_relay_session_plan_has_four_safe_steps(tmp_path):
    session_plan = build_codex_coordination_relay_session_plan(_relay_plan(tmp_path))

    assert session_plan["schema"] == CODEX_COORDINATION_SESSION_PLAN_SCHEMA
    assert session_plan["session_id"] == "relay-0087"
    assert [step["phase"] for step in session_plan["steps"]] == [
        "send_file",
        "wait_contract",
        "send_file",
        "wait_report",
    ]
    assert session_plan["steps"][0]["send"] is True
    assert session_plan["steps"][0]["send_timeout_sec"] == 10.0
    assert session_plan["steps"][1]["apply"] is True
    assert session_plan["steps"][2]["kind"] == "codex_report"
    assert session_plan["steps"][2]["send_timeout_sec"] == 12.5
    assert session_plan["steps"][3]["expect_sha256"] == "b" * 64


def test_coordination_relay_requires_exact_hashes(tmp_path):
    plan = _relay_plan(tmp_path)
    plan["contract"]["expect_sha256"] = "short"

    try:
        build_codex_coordination_relay_session_plan(plan)
    except SynapsValidationError as exc:
        assert "expect_sha256 must be sha256" in str(exc)
    else:
        raise AssertionError("invalid relay plan should fail")


def test_coordination_relay_dry_run_builds_without_running(tmp_path):
    payload = dry_run_codex_coordination_relay(_relay_plan(tmp_path))
    dumped = json.dumps(payload, ensure_ascii=False)

    assert payload["ok"] is True
    assert payload["schema"] == CODEX_COORDINATION_RELAY_SCHEMA
    assert payload["result"]["status"] == "relay_plan_built"
    assert payload["step_count"] == 4
    assert "payload_b64" not in dumped
    assert "shared-secret" not in dumped


def test_coordination_relay_fail_closed_without_gates(tmp_path):
    payload = run_codex_coordination_relay(
        plan=_relay_plan(tmp_path),
        env={},
        env_file="",
        relay_root=tmp_path / "relay",
        confirm=CODEX_COORDINATION_RELAY_CONFIRM_PHRASE,
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "relay_gate_failed"
    assert "SYNAPS_CODEX_COORDINATION_RELAY_not_enabled" in payload["problems"]
    assert (tmp_path / "relay" / "events.jsonl").is_file()


def test_coordination_relay_invokes_session_with_process_local_session_gate(tmp_path):
    calls = []

    def fake_session(**kwargs):
        calls.append(kwargs)
        assert kwargs["confirm"] == CODEX_COORDINATION_SESSION_CONFIRM_PHRASE
        assert kwargs["env"]["SYNAPS_CODEX_COORDINATION_SESSION"] == "1"
        assert kwargs["env"]["SYNAPS_CODEX_COORDINATION_SESSION_ARMED"] == "1"
        return {"ok": True, "result": {"status": "session_complete"}, "steps": []}

    payload = run_codex_coordination_relay(
        plan=_relay_plan(tmp_path),
        env=_env(),
        env_file="",
        relay_root=tmp_path / "relay",
        confirm=CODEX_COORDINATION_RELAY_CONFIRM_PHRASE,
        session_fn=fake_session,
    )

    assert payload["ok"] is True
    assert payload["result"]["status"] == "relay_complete"
    assert calls and calls[0]["plan"]["session_id"] == "relay-0087"


def test_cli_coordination_relay_dry_run(tmp_path):
    plan = tmp_path / "relay.json"
    plan.write_text(json.dumps(_relay_plan(tmp_path)), encoding="utf-8")
    env = os.environ.copy()
    env.update(_env())

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_coordination_relay.py",
            "--env-file",
            "",
            "--plan",
            str(plan),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["result"]["status"] == "relay_plan_built"
    assert "payload_b64" not in result.stdout
