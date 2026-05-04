import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from modules.synaps import (
    CODEX_GATE_STALE_POLICY_CONFIRM_PHRASE,
    CodexGateStalePolicy,
    evaluate_codex_gate_stale_policy,
    render_codex_gate_stale_policy_markdown,
    validate_codex_gate_stale_policy_write_gate,
    write_codex_gate_stale_policy,
)


def _ledger(path, *, created_at):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": "ester.synaps.codex_package_ledger.v1",
                "ok": True,
                "front_id": path.stem,
                "created_at": created_at.isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _front(path, *, front_id="0106", status="waiting_peer_silent"):
    return {
        "front_id": front_id,
        "status": status,
        "expected_report_name": f"REPORT_{front_id}.md",
        "peer_activity_status": "peer_silent" if status == "waiting_peer_silent" else "expected_report_observed",
        "path": str(path),
    }


def _dashboard(fronts):
    return {
        "schema": "ester.synaps.codex_gate_dashboard.v1",
        "ok": True,
        "ledger_count": len(fronts),
        "open_count": sum(1 for item in fronts if str(item.get("status") or "").startswith("waiting")),
        "fronts": list(fronts),
        "auto_ingest": False,
        "memory": "off",
        "persistent": False,
    }


def test_stale_policy_pauses_when_peer_silent_count_reaches_threshold(tmp_path):
    now = datetime(2026, 5, 4, 10, 0, tzinfo=timezone.utc)
    fronts = []
    for index in range(3):
        ledger = _ledger(tmp_path / f"010{index}.json", created_at=now - timedelta(hours=1))
        fronts.append(_front(ledger, front_id=f"010{index}"))

    result = evaluate_codex_gate_stale_policy(
        dashboard=_dashboard(fronts),
        policy=CodexGateStalePolicy(max_peer_silent_open=3, stale_after_hours=6),
        now=now,
    )

    assert result["recommendation"] == "pause_new_patch_sends"
    assert result["peer_silent_count"] == 3
    assert "new_patch_send" in result["blocked_actions"]
    assert "single_status_request_only" in result["allowed_actions"]


def test_stale_policy_requests_status_for_aged_gate(tmp_path):
    now = datetime(2026, 5, 4, 10, 0, tzinfo=timezone.utc)
    ledger = _ledger(tmp_path / "0106.json", created_at=now - timedelta(hours=10))

    result = evaluate_codex_gate_stale_policy(
        dashboard=_dashboard([_front(ledger)]),
        policy=CodexGateStalePolicy(max_peer_silent_open=9, stale_after_hours=6),
        now=now,
    )

    assert result["recommendation"] == "request_status_only"
    assert result["stale_count"] == 1
    assert result["fronts"][0]["age_hours"] == 10.0


def test_stale_policy_waits_when_open_below_threshold_and_not_stale(tmp_path):
    now = datetime(2026, 5, 4, 10, 0, tzinfo=timezone.utc)
    ledger = _ledger(tmp_path / "0106.json", created_at=now - timedelta(hours=1))

    result = evaluate_codex_gate_stale_policy(
        dashboard=_dashboard([_front(ledger)]),
        policy=CodexGateStalePolicy(max_peer_silent_open=3, stale_after_hours=6),
        now=now,
    )

    assert result["recommendation"] == "wait"
    assert result["blocked_actions"] == ["persistent_daemon", "real_codex_worker", "scheduler_hourly", "autochat", "memory_ingest"]


def test_stale_policy_clear_when_no_open_gates(tmp_path):
    now = datetime(2026, 5, 4, 10, 0, tzinfo=timezone.utc)
    ledger = _ledger(tmp_path / "0106.json", created_at=now - timedelta(hours=1))

    result = evaluate_codex_gate_stale_policy(
        dashboard=_dashboard([_front(ledger, status="expected_report_observed")]),
        now=now,
    )

    assert result["recommendation"] == "clear"
    assert result["open_count"] == 0
    assert "next_bounded_front" in result["allowed_actions"]


def test_stale_policy_write_requires_confirm(tmp_path):
    evaluation = evaluate_codex_gate_stale_policy(dashboard=_dashboard([]))

    result = write_codex_gate_stale_policy(
        evaluation=evaluation,
        out_json=tmp_path / "policy.json",
        apply=True,
        confirm="",
    )

    assert result["ok"] is False
    assert result["result"]["status"] == "gate_failed"
    assert not (tmp_path / "policy.json").exists()


def test_stale_policy_write_creates_outputs(tmp_path):
    evaluation = evaluate_codex_gate_stale_policy(dashboard=_dashboard([]))

    result = write_codex_gate_stale_policy(
        evaluation=evaluation,
        out_json=tmp_path / "policy.json",
        out_md=tmp_path / "policy.md",
        apply=True,
        confirm=CODEX_GATE_STALE_POLICY_CONFIRM_PHRASE,
    )

    assert result["ok"] is True
    assert result["result"]["status"] == "stale_policy_written"
    assert json.loads((tmp_path / "policy.json").read_text(encoding="utf-8"))["recommendation"] == "clear"
    assert "SYNAPS Codex Gate Stale Policy" in (tmp_path / "policy.md").read_text(encoding="utf-8")


def test_stale_policy_markdown_lists_actions(tmp_path):
    now = datetime(2026, 5, 4, 10, 0, tzinfo=timezone.utc)
    ledger = _ledger(tmp_path / "0106.json", created_at=now - timedelta(hours=10))
    evaluation = evaluate_codex_gate_stale_policy(
        dashboard=_dashboard([_front(ledger)]),
        policy=CodexGateStalePolicy(max_peer_silent_open=9, stale_after_hours=6),
        now=now,
    )

    markdown = render_codex_gate_stale_policy_markdown(evaluation)

    assert "request_status_only" in markdown
    assert "0106" in markdown


def test_cli_stale_policy_write(tmp_path):
    now = datetime(2026, 5, 4, 10, 0, tzinfo=timezone.utc)
    ledger = _ledger(tmp_path / "0106.json", created_at=now - timedelta(hours=1))
    dashboard = tmp_path / "dashboard.json"
    dashboard.write_text(json.dumps(_dashboard([_front(ledger)]), ensure_ascii=False), encoding="utf-8")
    out_json = tmp_path / "out" / "policy.json"
    out_md = tmp_path / "out" / "policy.md"

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_gate_stale_policy.py",
            "--dashboard",
            str(dashboard),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--write",
            "--confirm",
            CODEX_GATE_STALE_POLICY_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["evaluation"]["recommendation"] == "wait"
    assert out_json.is_file()
    assert out_md.is_file()


def test_stale_policy_write_gate_allows_dry_run():
    assert validate_codex_gate_stale_policy_write_gate() == []
