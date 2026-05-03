import json
import os
import subprocess
import sys

from modules.synaps import (
    CODEX_COORDINATION_SESSION_CONFIRM_PHRASE,
    CODEX_COORDINATION_SESSION_PLAN_SCHEMA,
    CODEX_COORDINATION_SESSION_SCHEMA,
    SynapsConfig,
    SynapsMessageType,
    SynapsQuarantineStore,
    build_envelope,
    build_file_manifest,
    list_codex_front_claims,
    run_codex_coordination_session,
    validate_codex_coordination_session_gate,
)


def _env(**extra):
    base = {
        "SYNAPS_CODEX_COORDINATION_SESSION": "1",
        "SYNAPS_CODEX_COORDINATION_SESSION_ARMED": "1",
        "SISTER_AUTOCHAT": "0",
        "SISTER_NODE_URL": "http://sister.local",
        "SISTER_SYNC_TOKEN": "shared-secret",
        "ESTER_NODE_ID": "ester-test",
    }
    base.update(extra)
    return base


def _config(node_id="liah-test"):
    return SynapsConfig(node_url="http://sister.local", sync_token="shared-secret", node_id=node_id)


def _quarantine_file(
    tmp_path,
    *,
    transfer_id="synaps-file-session",
    name="expected.md",
    kind="codex_report",
    text="# expected\nsafe body\n",
    sender="liah-test",
    note="session note",
):
    source = tmp_path / "source" / transfer_id / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(text, encoding="utf-8")
    manifest = build_file_manifest([source], include_payload=True, transfer_id=transfer_id, kind=kind, note=note)
    envelope = build_envelope(
        _config(sender),
        json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        SynapsMessageType.FILE_MANIFEST,
        message_id=f"incoming-{transfer_id}",
    )
    SynapsQuarantineStore(tmp_path / "quarantine").receive_manifest(envelope)
    record = manifest["files"][0]
    return {"sha256": record["sha256"], "size": record["size"], "transfer_id": transfer_id}


def test_coordination_session_gate_blocks_unsafe_flags():
    assert validate_codex_coordination_session_gate(_env(), confirm=CODEX_COORDINATION_SESSION_CONFIRM_PHRASE) == []

    problems = validate_codex_coordination_session_gate(
        _env(SISTER_AUTOCHAT="1", SYNAPS_CODEX_DAEMON_RUNNER="1"),
        confirm=CODEX_COORDINATION_SESSION_CONFIRM_PHRASE,
    )

    assert "SISTER_AUTOCHAT_must_remain_disabled" in problems
    assert "SYNAPS_CODEX_DAEMON_RUNNER_must_remain_disabled" in problems


def test_coordination_session_send_file_dry_run_redacts_payload(tmp_path):
    source = tmp_path / "handoffs" / "contract.md"
    source.parent.mkdir()
    source.write_text("# contract\nSECRET_BODY_MARKER\n", encoding="utf-8")
    plan = {
        "schema": CODEX_COORDINATION_SESSION_PLAN_SCHEMA,
        "session_id": "session-send",
        "steps": [
            {
                "phase": "send_file",
                "nonce": "session-send-step",
                "file": str(source),
                "base_dir": str(source.parent),
                "kind": "codex_contract",
                "note": "session send",
                "include_payload": True,
            }
        ],
    }

    payload = run_codex_coordination_session(
        plan=plan,
        env=_env(),
        env_file="",
        session_root=tmp_path / "session",
        confirm=CODEX_COORDINATION_SESSION_CONFIRM_PHRASE,
        postcheck_roots=[tmp_path / "memory"],
    )

    dumped = json.dumps(payload, ensure_ascii=False)
    assert payload["ok"] is True
    assert payload["schema"] == CODEX_COORDINATION_SESSION_SCHEMA
    assert payload["steps"][0]["phase_results"][0]["transfer"]["file_count"] == 1
    assert "payload_b64" not in dumped
    assert '"token"' not in dumped
    assert "SECRET_BODY_MARKER" not in dumped
    assert (tmp_path / "session" / "events.jsonl").is_file()


def test_coordination_session_send_file_uses_step_send_timeout(tmp_path):
    source = tmp_path / "handoffs" / "contract.md"
    source.parent.mkdir()
    source.write_text("# contract\n", encoding="utf-8")
    seen_timeouts = []
    plan = {
        "schema": CODEX_COORDINATION_SESSION_PLAN_SCHEMA,
        "session_id": "session-send-timeout",
        "steps": [
            {
                "phase": "send_file",
                "nonce": "session-send-timeout-step",
                "file": str(source),
                "base_dir": str(source.parent),
                "kind": "codex_contract",
                "note": "session send timeout",
                "include_payload": True,
                "send": True,
                "send_timeout_sec": 12.5,
            }
        ],
    }

    def fake_send(request):
        seen_timeouts.append(request.timeout_sec)
        return {"ok": True, "status": 200, "body": {"status": "quarantined"}}

    payload = run_codex_coordination_session(
        plan=plan,
        env=_env(),
        env_file="",
        session_root=tmp_path / "session",
        confirm=CODEX_COORDINATION_SESSION_CONFIRM_PHRASE,
        postcheck_roots=[tmp_path / "memory"],
        send_fn=fake_send,
    )

    assert payload["ok"] is True
    assert seen_timeouts == [12.5]
    assert payload["steps"][0]["phase_results"][0]["request"]["timeout_sec"] == 12.5


def test_coordination_session_wait_report_apply_uses_exact_and_repeat(tmp_path):
    record = _quarantine_file(
        tmp_path,
        transfer_id="synaps-file-session-report",
        name="report.md",
        kind="codex_report",
        note="session report exact",
    )
    plan = {
        "schema": CODEX_COORDINATION_SESSION_PLAN_SCHEMA,
        "session_id": "session-report",
        "steps": [
            {
                "phase": "wait_report",
                "nonce": "session-report-step",
                "expect_name": "report.md",
                "expect_sender": "liah-test",
                "note_contains": "session report",
                "expect_sha256": record["sha256"],
                "expect_size": record["size"],
                "quarantine_root": str(tmp_path / "quarantine"),
                "daemon_root": str(tmp_path / "daemon"),
                "inbox_root": str(tmp_path / "inbox"),
                "receipt_ledger": str(tmp_path / "receipts" / "events.jsonl"),
                "request_root": str(tmp_path / "requests"),
                "apply": True,
            }
        ],
    }

    payload = run_codex_coordination_session(
        plan=plan,
        env=_env(),
        env_file="",
        session_root=tmp_path / "session",
        confirm=CODEX_COORDINATION_SESSION_CONFIRM_PHRASE,
    )

    step = payload["steps"][0]
    assert payload["ok"] is True
    assert step["result"]["status"] == "report_observed"
    assert step["phase_results"][0]["repeat_check"]["candidate_count"] == 0
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / "requests").exists()


def test_coordination_session_front_claim_guard_closes_on_success(tmp_path):
    record = _quarantine_file(
        tmp_path,
        transfer_id="synaps-file-session-claim-report",
        name="report.md",
        kind="codex_report",
        note="claim guarded session",
    )
    claim_root = tmp_path / "front_claims"
    plan = {
        "schema": CODEX_COORDINATION_SESSION_PLAN_SCHEMA,
        "session_id": "session-claim-guard",
        "operator": "ester-test",
        "front_claim": {
            "root": str(claim_root),
            "front_id": "0099",
            "owner": "ester-test",
            "marker": "claim-guarded-session",
            "title": "claim guarded test",
            "lease_sec": 600,
            "expect_name": "report.md",
            "expect_sender": "liah-test",
            "expect_note_contains": "claim guarded",
            "expect_sha256": record["sha256"],
            "expect_size": record["size"],
        },
        "steps": [
            {
                "phase": "wait_report",
                "nonce": "session-claim-guard-step",
                "expect_name": "report.md",
                "expect_sender": "liah-test",
                "note_contains": "claim guarded",
                "expect_sha256": record["sha256"],
                "expect_size": record["size"],
                "quarantine_root": str(tmp_path / "quarantine"),
                "daemon_root": str(tmp_path / "daemon"),
                "inbox_root": str(tmp_path / "inbox"),
                "receipt_ledger": str(tmp_path / "receipts" / "events.jsonl"),
                "request_root": str(tmp_path / "requests"),
                "apply": True,
            }
        ],
    }

    payload = run_codex_coordination_session(
        plan=plan,
        env=_env(SYNAPS_CODEX_FRONT_CLAIM="1", SYNAPS_CODEX_FRONT_CLAIM_ARMED="1"),
        env_file="",
        session_root=tmp_path / "session",
        confirm=CODEX_COORDINATION_SESSION_CONFIRM_PHRASE,
    )
    claims = list_codex_front_claims(claim_root)

    assert payload["ok"] is True
    assert payload["front_claim"]["result"]["status"] == "front_claim_written"
    assert payload["front_claim_close"]["result"]["status"] == "front_claim_closed"
    assert payload["front_claim_close"]["claim"]["status"] == "completed"
    assert claims["claim_count"] == 1
    assert claims["active_count"] == 0
    assert claims["claims"][0]["status"] == "completed"


def test_coordination_session_front_claim_guard_fails_closed_without_claim_gate(tmp_path):
    plan = {
        "schema": CODEX_COORDINATION_SESSION_PLAN_SCHEMA,
        "session_id": "session-claim-missing-gate",
        "front_claim": {
            "root": str(tmp_path / "front_claims"),
            "front_id": "0099",
            "owner": "ester-test",
            "marker": "claim-missing-gate",
            "expect_name": "report.md",
            "expect_sender": "liah-test",
            "expect_note_contains": "claim missing",
            "expect_sha256": "a" * 64,
            "expect_size": 123,
        },
        "steps": [
            {
                "phase": "wait_report",
                "expect_name": "report.md",
                "expect_sender": "liah-test",
                "note_contains": "claim missing",
                "expect_sha256": "a" * 64,
                "expect_size": 123,
                "apply": True,
            }
        ],
    }

    payload = run_codex_coordination_session(
        plan=plan,
        env=_env(),
        env_file="",
        session_root=tmp_path / "session",
        confirm=CODEX_COORDINATION_SESSION_CONFIRM_PHRASE,
    )

    assert payload["ok"] is False
    assert "front_claim_write_failed" in payload["problems"]
    assert payload["front_claim"]["result"]["status"] == "front_claim_gate_failed"
    assert "SYNAPS_CODEX_FRONT_CLAIM_not_enabled" in payload["front_claim"]["problems"]


def test_coordination_session_wait_contract_apply_uses_exact_and_repeat(tmp_path):
    record = _quarantine_file(
        tmp_path,
        transfer_id="synaps-file-session-contract",
        name="contract.md",
        kind="codex_contract",
        note="session contract exact",
    )
    plan = {
        "schema": CODEX_COORDINATION_SESSION_PLAN_SCHEMA,
        "session_id": "session-contract",
        "steps": [
            {
                "phase": "wait_contract",
                "nonce": "session-contract-step",
                "expect_name": "contract.md",
                "expect_kind": "codex_contract",
                "expect_sender": "liah-test",
                "note_contains": "session contract",
                "expect_sha256": record["sha256"],
                "expect_size": record["size"],
                "quarantine_root": str(tmp_path / "quarantine"),
                "scanner_root": str(tmp_path / "scanner"),
                "inbox_root": str(tmp_path / "inbox"),
                "apply": True,
            }
        ],
    }

    payload = run_codex_coordination_session(
        plan=plan,
        env=_env(),
        env_file="",
        session_root=tmp_path / "session",
        confirm=CODEX_COORDINATION_SESSION_CONFIRM_PHRASE,
    )

    step = payload["steps"][0]
    assert payload["ok"] is True
    assert step["result"]["status"] == "scanner_seen"
    assert step["phase_results"][0]["repeat_check"]["candidate_count"] == 0
    assert (tmp_path / "scanner" / "seen" / "synaps-file-session-contract.json").is_file()
    assert not (tmp_path / "inbox").exists()


def test_coordination_session_live_wait_requires_exact_hash_and_size(tmp_path):
    plan = {
        "schema": CODEX_COORDINATION_SESSION_PLAN_SCHEMA,
        "session_id": "session-missing-exact",
        "steps": [
            {
                "phase": "wait_report",
                "expect_name": "report.md",
                "expect_sender": "liah-test",
                "apply": True,
            }
        ],
    }

    payload = run_codex_coordination_session(
        plan=plan,
        env=_env(),
        env_file="",
        session_root=tmp_path / "session",
        confirm=CODEX_COORDINATION_SESSION_CONFIRM_PHRASE,
    )

    assert payload["ok"] is False
    assert "step_1_expected_sha256_required" in payload["problems"]
    assert "step_1_expected_size_required" in payload["problems"]


def test_cli_coordination_session_send_file_dry_run(tmp_path):
    source = tmp_path / "handoffs" / "contract.md"
    source.parent.mkdir()
    source.write_text("# contract\n", encoding="utf-8")
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "schema": CODEX_COORDINATION_SESSION_PLAN_SCHEMA,
                "session_id": "cli-session",
                "steps": [
                    {
                        "phase": "send_file",
                        "nonce": "cli-session-step",
                        "file": str(source),
                        "base_dir": str(source.parent),
                        "kind": "codex_contract",
                        "note": "cli session",
                        "include_payload": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(_env())

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_coordination_session.py",
            "--env-file",
            "",
            "--plan",
            str(plan),
            "--session-root",
            str(tmp_path / "session"),
            "--confirm",
            CODEX_COORDINATION_SESSION_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["session_id"] == "cli-session"
    assert "payload_b64" not in result.stdout
