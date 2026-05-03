import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from modules.synaps import (
    CODEX_FRONT_CLAIM_CLOSE_CONFIRM_PHRASE,
    CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
    CODEX_FRONT_CLAIM_SCHEMA,
    build_codex_front_claim,
    close_codex_front_claim,
    list_codex_front_claims,
    validate_codex_front_claim_gate,
    write_codex_front_claim,
)


def _env(**extra):
    base = {
        "SYNAPS_CODEX_FRONT_CLAIM": "1",
        "SYNAPS_CODEX_FRONT_CLAIM_ARMED": "1",
        "SISTER_AUTOCHAT": "0",
    }
    base.update(extra)
    return base


def _expected(name="report.md"):
    return {
        "name": name,
        "sender": "liah_secondary",
        "note_contains": "0096",
        "sha256": "a" * 64,
        "size": 123,
    }


def _claim(front_id="0096", owner="ester", marker="0096-front-claim"):
    return build_codex_front_claim(
        front_id=front_id,
        owner=owner,
        marker=marker,
        title="front claim test",
        lease_seconds=1800,
        expected_report=_expected(),
        created_at="2026-05-03T21:00:00+00:00",
    )


def test_front_claim_gate_blocks_missing_and_unsafe_flags():
    assert validate_codex_front_claim_gate(_env(), apply=True, confirm=CODEX_FRONT_CLAIM_CONFIRM_PHRASE) == []

    missing = validate_codex_front_claim_gate({}, apply=True, confirm="")
    assert "missing_codex_front_claim_confirm_phrase" in missing
    assert "SYNAPS_CODEX_FRONT_CLAIM_not_enabled" in missing

    unsafe = validate_codex_front_claim_gate(
        _env(SISTER_AUTOCHAT="1", SYNAPS_CODEX_DAEMON_RUNNER="1", SISTER_SCHEDULE="1"),
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
    )
    assert "SISTER_AUTOCHAT_must_remain_disabled" in unsafe
    assert "SYNAPS_CODEX_DAEMON_RUNNER_must_remain_disabled" in unsafe
    assert "schedule_must_remain_disabled" in unsafe


def test_front_claim_dry_run_does_not_write(tmp_path):
    payload = write_codex_front_claim(_claim(), env=_env(), root=tmp_path, apply=False)

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["result"]["status"] == "would_write_front_claim"
    assert not (tmp_path / "claims").exists()


def test_front_claim_apply_writes_metadata_only(tmp_path):
    claim = _claim()
    payload = write_codex_front_claim(
        claim,
        env=_env(),
        root=tmp_path,
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
    )
    claim_files = list((tmp_path / "claims").glob("*.json"))
    ledger = (tmp_path / "events.jsonl").read_text(encoding="utf-8")

    assert payload["ok"] is True
    assert payload["schema"] == CODEX_FRONT_CLAIM_SCHEMA
    assert payload["result"]["status"] == "front_claim_written"
    assert len(claim_files) == 1
    assert "payload_b64" not in ledger
    assert "shared-secret" not in ledger
    assert "content" not in ledger


def test_front_claim_apply_requires_confirm(tmp_path):
    payload = write_codex_front_claim(_claim(), env=_env(), root=tmp_path, apply=True, confirm="")

    assert payload["ok"] is False
    assert payload["result"]["status"] == "front_claim_gate_failed"
    assert "missing_codex_front_claim_confirm_phrase" in payload["problems"]
    assert not (tmp_path / "claims").exists()


def test_front_claim_conflict_blocks_second_active_claim(tmp_path):
    first = write_codex_front_claim(
        _claim(owner="ester", marker="0096-a"),
        env=_env(),
        root=tmp_path,
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
    )
    second = write_codex_front_claim(
        _claim(owner="liah", marker="0096-b"),
        env=_env(),
        root=tmp_path,
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
        now=datetime(2026, 5, 3, 21, 10, tzinfo=timezone.utc),
    )

    assert first["ok"] is True
    assert second["ok"] is False
    assert second["result"]["status"] == "front_claim_conflict"
    assert "active_front_claim_conflict:" in second["problems"][0]
    assert len(list((tmp_path / "claims").glob("*.json"))) == 1


def test_front_claim_supersedes_allows_replacement(tmp_path):
    first_claim = _claim(owner="ester", marker="0096-a")
    first = write_codex_front_claim(
        first_claim,
        env=_env(),
        root=tmp_path,
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
    )
    replacement = build_codex_front_claim(
        front_id="0096",
        owner="liah",
        marker="0096-b",
        expected_report=_expected(),
        supersedes=[first_claim["claim_id"]],
        created_at="2026-05-03T21:05:00+00:00",
    )
    second = write_codex_front_claim(
        replacement,
        env=_env(),
        root=tmp_path,
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
        now=datetime(2026, 5, 3, 21, 10, tzinfo=timezone.utc),
    )

    assert first["ok"] is True
    assert second["ok"] is True
    assert len(list((tmp_path / "claims").glob("*.json"))) == 2


def test_front_claim_expired_claim_does_not_conflict(tmp_path):
    expired = _claim(owner="ester", marker="0096-expired")
    write_codex_front_claim(
        expired,
        env=_env(),
        root=tmp_path,
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
    )
    fresh = _claim(owner="liah", marker="0096-fresh")
    payload = write_codex_front_claim(
        fresh,
        env=_env(),
        root=tmp_path,
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
        now=datetime(2026, 5, 4, tzinfo=timezone.utc),
    )

    assert payload["ok"] is True
    assert len(list((tmp_path / "claims").glob("*.json"))) == 2


def test_front_claim_list_reports_active_claims(tmp_path):
    write_codex_front_claim(
        _claim(),
        env=_env(),
        root=tmp_path,
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
    )

    payload = list_codex_front_claims(tmp_path, now=datetime(2026, 5, 3, 21, 10, tzinfo=timezone.utc))

    assert payload["ok"] is True
    assert payload["claim_count"] == 1
    assert payload["active_count"] == 1


def test_front_claim_close_releases_active_claim(tmp_path):
    claim = _claim()
    write_codex_front_claim(
        claim,
        env=_env(),
        root=tmp_path,
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
    )

    closed = close_codex_front_claim(
        claim["claim_id"],
        status="released",
        reason="proof complete",
        env=_env(),
        root=tmp_path,
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CLOSE_CONFIRM_PHRASE,
        operator="tester",
        now=datetime(2026, 5, 3, 21, 15, tzinfo=timezone.utc),
    )
    listed = list_codex_front_claims(tmp_path, now=datetime(2026, 5, 3, 21, 16, tzinfo=timezone.utc))

    assert closed["ok"] is True
    assert closed["result"]["status"] == "front_claim_closed"
    assert closed["claim"]["status"] == "released"
    assert closed["claim"]["previous_status"] == "claimed"
    assert closed["claim"]["closed_by"] == "tester"
    assert listed["claim_count"] == 1
    assert listed["active_count"] == 0


def test_front_claim_close_allows_new_active_claim(tmp_path):
    first_claim = _claim(owner="ester", marker="0096-close-a")
    write_codex_front_claim(
        first_claim,
        env=_env(),
        root=tmp_path,
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
    )
    close_codex_front_claim(
        first_claim["claim_id"],
        env=_env(),
        root=tmp_path,
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CLOSE_CONFIRM_PHRASE,
    )

    second = write_codex_front_claim(
        _claim(owner="liah", marker="0096-close-b"),
        env=_env(),
        root=tmp_path,
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
        now=datetime(2026, 5, 3, 21, 10, tzinfo=timezone.utc),
    )

    assert second["ok"] is True
    assert second["result"]["status"] == "front_claim_written"
    assert len(list((tmp_path / "claims").glob("*.json"))) == 2


def test_front_claim_close_requires_gate_and_is_idempotent(tmp_path):
    claim = _claim()
    write_codex_front_claim(
        claim,
        env=_env(),
        root=tmp_path,
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
    )

    blocked = close_codex_front_claim(claim["claim_id"], env=_env(), root=tmp_path, apply=True, confirm="")
    closed = close_codex_front_claim(
        claim["claim_id"],
        env=_env(),
        root=tmp_path,
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CLOSE_CONFIRM_PHRASE,
    )
    repeated = close_codex_front_claim(
        claim["claim_id"],
        env=_env(),
        root=tmp_path,
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CLOSE_CONFIRM_PHRASE,
    )

    assert blocked["ok"] is False
    assert blocked["result"]["status"] == "front_claim_close_gate_failed"
    assert "missing_codex_front_claim_close_confirm_phrase" in blocked["problems"]
    assert closed["ok"] is True
    assert repeated["ok"] is True
    assert repeated["result"]["status"] == "front_claim_already_closed"


def test_front_claim_cli_apply(tmp_path):
    env = os.environ.copy()
    env.update(_env())

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_front_claim.py",
            "--env-file",
            "",
            "--root",
            str(tmp_path),
            "--front-id",
            "0096",
            "--owner",
            "ester",
            "--marker",
            "0096-cli",
            "--expect-name",
            "report.md",
            "--expect-sender",
            "liah_secondary",
            "--expect-note-contains",
            "0096",
            "--expect-sha256",
            "a" * 64,
            "--expect-size",
            "123",
            "--apply",
            "--confirm",
            CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["result"]["status"] == "front_claim_written"
    assert list((tmp_path / "claims").glob("*.json"))


def test_front_claim_cli_close(tmp_path):
    env = os.environ.copy()
    env.update(_env())

    write_result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_front_claim.py",
            "--env-file",
            "",
            "--root",
            str(tmp_path),
            "--front-id",
            "0096",
            "--owner",
            "ester",
            "--marker",
            "0096-cli-close",
            "--expect-name",
            "report.md",
            "--expect-sender",
            "liah_secondary",
            "--expect-note-contains",
            "0096",
            "--expect-sha256",
            "a" * 64,
            "--expect-size",
            "123",
            "--apply",
            "--confirm",
            CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    claim_id = json.loads(write_result.stdout)["claim"]["claim_id"]
    close_result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_front_claim.py",
            "--env-file",
            "",
            "--root",
            str(tmp_path),
            "--mode",
            "close",
            "--claim-id",
            claim_id,
            "--close-status",
            "completed",
            "--close-reason",
            "cli smoke",
            "--apply",
            "--confirm",
            CODEX_FRONT_CLAIM_CLOSE_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(close_result.stdout)

    assert payload["ok"] is True
    assert payload["result"]["status"] == "front_claim_closed"
    assert payload["claim"]["status"] == "completed"
