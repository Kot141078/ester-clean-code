import json
import subprocess
import sys

from modules.synaps import (
    CODEX_GATE_DASHBOARD_CONFIRM_PHRASE,
    build_codex_gate_dashboard,
    render_codex_gate_dashboard_markdown,
    validate_codex_gate_dashboard_write_gate,
    write_codex_gate_dashboard,
)


def _ledger(path, *, front_id="0109", status="waiting_peer_silent", report="REPORT.md", peer_status="peer_silent"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": "ester.synaps.codex_package_ledger.v1",
                "ok": True,
                "front_id": front_id,
                "status": status,
                "expected_report": {"name": report, "note_contains": front_id, "sender": "liah-test"},
                "peer_activity": {"matched": False, "result": {"status": peer_status}},
                "transfer_record_count": 3,
                "transfer_output_count": 2,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def test_gate_dashboard_builds_open_summary(tmp_path):
    first = _ledger(tmp_path / "a.json", front_id="0106")
    second = _ledger(tmp_path / "b.json", front_id="0107", status="expected_report_observed", peer_status="expected_report_observed")

    dashboard = build_codex_gate_dashboard(ledger_paths=[first, second])

    assert dashboard["ok"] is True
    assert dashboard["ledger_count"] == 2
    assert dashboard["open_count"] == 1
    assert dashboard["status_counts"]["waiting_peer_silent"] == 1
    assert dashboard["fronts"][0]["front_id"] == "0106"


def test_gate_dashboard_can_include_root_ledgers(tmp_path):
    _ledger(tmp_path / "ledgers" / "a.json", front_id="0106")

    dashboard = build_codex_gate_dashboard(ledger_root=tmp_path / "ledgers", include_root=True)

    assert dashboard["ledger_count"] == 1
    assert dashboard["fronts"][0]["front_id"] == "0106"


def test_gate_dashboard_write_requires_confirm(tmp_path):
    dashboard = build_codex_gate_dashboard()
    result = write_codex_gate_dashboard(
        dashboard=dashboard,
        out_json=tmp_path / "dashboard.json",
        apply=True,
        confirm="",
    )

    assert result["ok"] is False
    assert result["result"]["status"] == "gate_failed"
    assert not (tmp_path / "dashboard.json").exists()


def test_gate_dashboard_write_creates_outputs(tmp_path):
    dashboard = build_codex_gate_dashboard(ledger_paths=[_ledger(tmp_path / "a.json")])
    result = write_codex_gate_dashboard(
        dashboard=dashboard,
        out_json=tmp_path / "dashboard.json",
        out_md=tmp_path / "dashboard.md",
        apply=True,
        confirm=CODEX_GATE_DASHBOARD_CONFIRM_PHRASE,
    )

    assert result["ok"] is True
    assert result["result"]["status"] == "dashboard_written"
    assert json.loads((tmp_path / "dashboard.json").read_text(encoding="utf-8"))["ledger_count"] == 1
    assert "Open Gate Dashboard" in (tmp_path / "dashboard.md").read_text(encoding="utf-8")


def test_gate_dashboard_markdown_lists_fronts(tmp_path):
    dashboard = build_codex_gate_dashboard(ledger_paths=[_ledger(tmp_path / "a.json", front_id="0106")])
    markdown = render_codex_gate_dashboard_markdown(dashboard)

    assert "0106" in markdown
    assert "waiting_peer_silent" in markdown


def test_cli_gate_dashboard_write(tmp_path):
    ledger = _ledger(tmp_path / "ledger.json", front_id="0109")
    out_json = tmp_path / "out" / "dashboard.json"
    out_md = tmp_path / "out" / "dashboard.md"

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_gate_dashboard.py",
            "--ledger",
            str(ledger),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--write",
            "--confirm",
            CODEX_GATE_DASHBOARD_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["dashboard"]["open_count"] == 1
    assert out_json.is_file()
    assert out_md.is_file()


def test_gate_dashboard_write_gate_allows_dry_run():
    assert validate_codex_gate_dashboard_write_gate() == []
