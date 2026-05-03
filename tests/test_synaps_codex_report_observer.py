import json
import os
import subprocess
import sys

from modules.synaps import (
    CODEX_REPORT_OBSERVER_CONFIRM_PHRASE,
    CODEX_REPORT_SELECTOR_CONFIRM_PHRASE,
    CODEX_REPORT_WAITER_CONFIRM_PHRASE,
    CODEX_REPORT_WATCHER_CONFIRM_PHRASE,
    CodexDaemon,
    CodexReportSelector,
    CodexReportWatcherPolicy,
    SynapsConfig,
    SynapsMessageType,
    SynapsQuarantineStore,
    build_envelope,
    build_file_manifest,
    observe_expected_codex_report,
    select_codex_report_by_manifest,
    validate_codex_report_observer_gate,
    wait_for_codex_report_by_manifest,
    watch_codex_report_by_manifest,
    watch_expected_codex_report,
)


def _config(node_id="ester-test") -> SynapsConfig:
    return SynapsConfig(node_url="http://sister.local", sync_token="shared-secret", node_id=node_id)


def _armed_env(**extra):
    env = {
        "SYNAPS_CODEX_DAEMON": "1",
        "SYNAPS_CODEX_DAEMON_ARMED": "1",
        "SYNAPS_CODEX_DAEMON_OBSERVE_REPORTS": "1",
        "SYNAPS_CODEX_DAEMON_OBSERVE_REPORTS_ARMED": "1",
        "SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX": "0",
        "SYNAPS_CODEX_DAEMON_ENQUEUE_HANDOFFS": "0",
        "SYNAPS_CODEX_DAEMON_RUNNER": "0",
        "SYNAPS_CODEX_DAEMON_RUNNER_ARMED": "0",
        "SISTER_AUTOCHAT": "0",
    }
    env.update(extra)
    return env


def _quarantine_report(
    tmp_path,
    *,
    transfer_id="synaps-file-report",
    name="report.md",
    text="# report\nsafe report body\n",
    sender="ester-test",
    note="",
):
    source = tmp_path / "source" / transfer_id / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(text, encoding="utf-8")
    manifest = build_file_manifest([source], include_payload=True, transfer_id=transfer_id, kind="codex_report", note=note)
    envelope = build_envelope(
        _config(sender),
        json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        SynapsMessageType.FILE_MANIFEST,
        message_id="incoming-report",
    )
    SynapsQuarantineStore(tmp_path / "quarantine").receive_manifest(envelope)


def _observer_roots(tmp_path):
    return {
        "daemon_root": tmp_path / "daemon",
        "quarantine_root": tmp_path / "quarantine",
        "inbox_root": tmp_path / "inbox",
        "receipt_ledger": tmp_path / "receipts" / "events.jsonl",
        "request_root": tmp_path / "requests",
    }


def test_report_observer_gate_blocks_unsafe_flags():
    assert validate_codex_report_observer_gate(_armed_env()) == []
    problems = validate_codex_report_observer_gate(_armed_env(SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX="1"))

    assert "SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX_must_remain_disabled" in problems


def test_report_observer_dry_run_matches_without_writing(tmp_path):
    _quarantine_report(tmp_path)

    payload = observe_expected_codex_report(
        expected_transfer_id="synaps-file-report",
        env=_armed_env(),
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["matched"] is True
    assert payload["preview"]["actions"][0]["transfer_id"] == "synaps-file-report"
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").exists()


def test_report_observer_apply_requires_confirm(tmp_path):
    _quarantine_report(tmp_path)

    payload = observe_expected_codex_report(
        expected_transfer_id="synaps-file-report",
        env=_armed_env(),
        apply=True,
        confirm="",
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "gate_failed"
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").exists()


def test_report_observer_apply_fails_closed_on_transfer_mismatch(tmp_path):
    _quarantine_report(tmp_path)

    payload = observe_expected_codex_report(
        expected_transfer_id="synaps-file-other",
        env=_armed_env(),
        apply=True,
        confirm=CODEX_REPORT_OBSERVER_CONFIRM_PHRASE,
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "expected_transfer_mismatch"
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").exists()


def test_report_observer_fails_closed_when_multiple_reports_are_pending(tmp_path):
    _quarantine_report(tmp_path, transfer_id="synaps-file-report")
    _quarantine_report(tmp_path, transfer_id="synaps-file-other")

    payload = observe_expected_codex_report(
        expected_transfer_id="synaps-file-report",
        env=_armed_env(),
        apply=True,
        confirm=CODEX_REPORT_OBSERVER_CONFIRM_PHRASE,
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "expected_transfer_mismatch"
    assert "expected_exactly_one_observe_report_action:2" in payload["problems"]
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").exists()


def test_report_observer_rechecks_before_apply_when_new_report_arrives(tmp_path, monkeypatch):
    _quarantine_report(tmp_path, transfer_id="synaps-file-report")
    original_cycle = CodexDaemon.cycle
    calls = 0

    def wrapped_cycle(self, *args, **kwargs):
        nonlocal calls
        result = original_cycle(self, *args, **kwargs)
        if not kwargs.get("apply") and calls == 0:
            _quarantine_report(tmp_path, transfer_id="synaps-file-other")
        calls += 1
        return result

    monkeypatch.setattr(CodexDaemon, "cycle", wrapped_cycle)

    payload = observe_expected_codex_report(
        expected_transfer_id="synaps-file-report",
        env=_armed_env(),
        apply=True,
        confirm=CODEX_REPORT_OBSERVER_CONFIRM_PHRASE,
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "pre_apply_mismatch"
    assert "expected_exactly_one_observe_report_action:2" in payload["problems"]
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").exists()
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-other.json").exists()


def test_report_observer_apply_marks_expected_report_only(tmp_path):
    _quarantine_report(tmp_path)

    payload = observe_expected_codex_report(
        expected_transfer_id="synaps-file-report",
        env=_armed_env(),
        apply=True,
        confirm=CODEX_REPORT_OBSERVER_CONFIRM_PHRASE,
        **_observer_roots(tmp_path),
    )
    repeat = observe_expected_codex_report(
        expected_transfer_id="synaps-file-report",
        env=_armed_env(),
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["result"]["status"] == "report_observed"
    assert (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").is_file()
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / "requests").exists()
    assert repeat["matched"] is False
    assert repeat["preview"]["actions"] == []


def test_cli_report_observer_apply(tmp_path):
    _quarantine_report(tmp_path)
    env = os.environ.copy()
    env.update(_armed_env())

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_report_observer.py",
            "--env-file",
            "",
            "--expect-transfer-id",
            "synaps-file-report",
            "--daemon-root",
            str(tmp_path / "daemon"),
            "--quarantine-root",
            str(tmp_path / "quarantine"),
            "--inbox-root",
            str(tmp_path / "inbox"),
            "--request-root",
            str(tmp_path / "requests"),
            "--apply",
            "--confirm",
            CODEX_REPORT_OBSERVER_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["result"]["status"] == "report_observed"
    assert (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").is_file()


def test_report_watcher_dry_run_reports_not_observed_without_writing(tmp_path):
    payload = watch_expected_codex_report(
        expected_transfer_id="synaps-file-report",
        env=_armed_env(),
        watcher_policy=CodexReportWatcherPolicy(max_cycles=3, sleep_sec=0),
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["matched"] is False
    assert payload["result"]["status"] == "not_observed_yet"
    assert len(payload["cycles"]) == 1
    assert not (tmp_path / "daemon").exists()


def test_report_watcher_apply_requires_confirm(tmp_path):
    _quarantine_report(tmp_path)

    payload = watch_expected_codex_report(
        expected_transfer_id="synaps-file-report",
        env=_armed_env(),
        apply=True,
        confirm="",
        watcher_policy=CodexReportWatcherPolicy(max_cycles=1, sleep_sec=0),
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "gate_failed"
    assert "missing_codex_report_watcher_confirm_phrase" in payload["result"]["problems"]
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").exists()


def test_report_watcher_apply_times_out_without_expected_report(tmp_path):
    sleeps = []

    payload = watch_expected_codex_report(
        expected_transfer_id="synaps-file-report",
        env=_armed_env(),
        apply=True,
        confirm=CODEX_REPORT_WATCHER_CONFIRM_PHRASE,
        watcher_policy=CodexReportWatcherPolicy(max_cycles=2, sleep_sec=0.01),
        sleep_fn=sleeps.append,
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "expected_transfer_not_observed"
    assert len(payload["cycles"]) == 2
    assert sleeps == [0.01]


def test_report_watcher_apply_observes_expected_report(tmp_path):
    _quarantine_report(tmp_path)

    payload = watch_expected_codex_report(
        expected_transfer_id="synaps-file-report",
        env=_armed_env(),
        apply=True,
        confirm=CODEX_REPORT_WATCHER_CONFIRM_PHRASE,
        watcher_policy=CodexReportWatcherPolicy(max_cycles=2, sleep_sec=0),
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["result"]["status"] == "report_observed"
    assert (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").is_file()
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / "requests").exists()


def test_cli_report_watcher_apply(tmp_path):
    _quarantine_report(tmp_path)
    env = os.environ.copy()
    env.update(_armed_env())

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_report_watcher.py",
            "--env-file",
            "",
            "--expect-transfer-id",
            "synaps-file-report",
            "--daemon-root",
            str(tmp_path / "daemon"),
            "--quarantine-root",
            str(tmp_path / "quarantine"),
            "--inbox-root",
            str(tmp_path / "inbox"),
            "--request-root",
            str(tmp_path / "requests"),
            "--max-cycles",
            "2",
            "--sleep-sec",
            "0",
            "--apply",
            "--confirm",
            CODEX_REPORT_WATCHER_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["result"]["status"] == "report_observed"
    assert (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").is_file()


def test_report_selector_dry_run_matches_by_manifest_without_writing(tmp_path):
    _quarantine_report(tmp_path, transfer_id="synaps-file-report", name="expected.md", sender="liah-test", note="0056 report")

    payload = select_codex_report_by_manifest(
        selector=CodexReportSelector(expected_name="expected.md", expected_sender="liah-test", note_contains="0056"),
        env=_armed_env(),
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["matched"] is True
    assert payload["selected_transfer_id"] == "synaps-file-report"
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").exists()


def test_report_selector_fails_closed_on_multiple_manifest_matches(tmp_path):
    _quarantine_report(tmp_path, transfer_id="synaps-file-report-a", name="expected.md", sender="liah-test")
    _quarantine_report(tmp_path, transfer_id="synaps-file-report-b", name="expected.md", sender="liah-test")

    payload = select_codex_report_by_manifest(
        selector=CodexReportSelector(expected_name="expected.md", expected_sender="liah-test"),
        env=_armed_env(),
        apply=True,
        confirm=CODEX_REPORT_SELECTOR_CONFIRM_PHRASE,
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "selector_mismatch"
    assert "expected_exactly_one_manifest_report:2" in payload["problems"]
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-report-a.json").exists()
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-report-b.json").exists()


def test_report_selector_apply_marks_only_selected_report_with_other_reports_pending(tmp_path):
    _quarantine_report(tmp_path, transfer_id="synaps-file-target", name="expected.md", sender="liah-test", note="0056 report")
    _quarantine_report(tmp_path, transfer_id="synaps-file-other", name="other.md", sender="liah-test")

    payload = select_codex_report_by_manifest(
        selector=CodexReportSelector(expected_name="expected.md", expected_sender="liah-test", note_contains="0056"),
        env=_armed_env(),
        apply=True,
        confirm=CODEX_REPORT_SELECTOR_CONFIRM_PHRASE,
        **_observer_roots(tmp_path),
    )
    repeat = select_codex_report_by_manifest(
        selector=CodexReportSelector(expected_name="expected.md", expected_sender="liah-test", note_contains="0056"),
        env=_armed_env(),
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["result"]["status"] == "report_observed"
    assert (tmp_path / "daemon" / "promote_seen" / "synaps-file-target.json").is_file()
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-other.json").exists()
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / "requests").exists()
    assert repeat["matched"] is False


def test_report_selector_apply_requires_confirm(tmp_path):
    _quarantine_report(tmp_path, transfer_id="synaps-file-report", name="expected.md")

    payload = select_codex_report_by_manifest(
        selector=CodexReportSelector(expected_name="expected.md"),
        env=_armed_env(),
        apply=True,
        confirm="",
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "gate_failed"
    assert "missing_codex_report_selector_confirm_phrase" in payload["result"]["problems"]
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").exists()


def test_report_selector_watcher_apply(tmp_path):
    _quarantine_report(tmp_path, transfer_id="synaps-file-report", name="expected.md", note="0056 report")

    payload = watch_codex_report_by_manifest(
        selector=CodexReportSelector(expected_name="expected.md", note_contains="0056"),
        env=_armed_env(),
        apply=True,
        confirm=CODEX_REPORT_SELECTOR_CONFIRM_PHRASE,
        watcher_policy=CodexReportWatcherPolicy(max_cycles=2, sleep_sec=0),
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["selected_transfer_id"] == "synaps-file-report"
    assert payload["cycle_count"] == 1
    assert payload["result"]["status"] == "report_observed"
    assert (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").is_file()


def test_report_selector_watcher_apply_waits_for_delayed_report(tmp_path):
    sleeps = []

    def delayed_report_sleep(seconds):
        sleeps.append(seconds)
        _quarantine_report(tmp_path, transfer_id="synaps-file-delayed", name="expected.md", note="0058 report")

    payload = watch_codex_report_by_manifest(
        selector=CodexReportSelector(expected_name="expected.md", note_contains="0058"),
        env=_armed_env(),
        apply=True,
        confirm=CODEX_REPORT_SELECTOR_CONFIRM_PHRASE,
        watcher_policy=CodexReportWatcherPolicy(max_cycles=2, sleep_sec=0.01),
        sleep_fn=delayed_report_sleep,
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["cycle_count"] == 2
    assert payload["selected_transfer_id"] == "synaps-file-delayed"
    assert payload["result"]["status"] == "report_observed"
    assert sleeps == [0.01]
    assert payload["cycles"][0]["matched"] is False
    assert payload["cycles"][1]["matched"] is True
    assert (tmp_path / "daemon" / "promote_seen" / "synaps-file-delayed.json").is_file()
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / "requests").exists()


def test_report_waiter_dry_run_waits_bounded_cycles_without_writing(tmp_path):
    sleeps = []

    payload = wait_for_codex_report_by_manifest(
        selector=CodexReportSelector(expected_name="expected.md", note_contains="0059"),
        env=_armed_env(),
        watcher_policy=CodexReportWatcherPolicy(max_cycles=2, sleep_sec=0.01),
        sleep_fn=sleeps.append,
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["matched"] is False
    assert payload["cycle_count"] == 2
    assert payload["result"]["status"] == "not_observed_yet"
    assert sleeps == [0.01]
    assert not (tmp_path / "daemon").exists()
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / "requests").exists()


def test_report_waiter_apply_waits_for_delayed_report(tmp_path):
    sleeps = []

    def delayed_report_sleep(seconds):
        sleeps.append(seconds)
        _quarantine_report(tmp_path, transfer_id="synaps-file-delayed-0059", name="expected.md", note="0059 report")

    payload = wait_for_codex_report_by_manifest(
        selector=CodexReportSelector(expected_name="expected.md", note_contains="0059"),
        env=_armed_env(),
        apply=True,
        confirm=CODEX_REPORT_WAITER_CONFIRM_PHRASE,
        watcher_policy=CodexReportWatcherPolicy(max_cycles=2, sleep_sec=0.01),
        sleep_fn=delayed_report_sleep,
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["cycle_count"] == 2
    assert payload["selected_transfer_id"] == "synaps-file-delayed-0059"
    assert payload["result"]["status"] == "report_observed"
    assert sleeps == [0.01]
    assert (tmp_path / "daemon" / "promote_seen" / "synaps-file-delayed-0059.json").is_file()
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / "requests").exists()


def test_report_waiter_fails_closed_on_multiple_candidates(tmp_path):
    _quarantine_report(tmp_path, transfer_id="synaps-file-report-a", name="expected.md", note="0059 report")
    _quarantine_report(tmp_path, transfer_id="synaps-file-report-b", name="expected.md", note="0059 report")

    payload = wait_for_codex_report_by_manifest(
        selector=CodexReportSelector(expected_name="expected.md", note_contains="0059"),
        env=_armed_env(),
        apply=True,
        confirm=CODEX_REPORT_WAITER_CONFIRM_PHRASE,
        watcher_policy=CodexReportWatcherPolicy(max_cycles=2, sleep_sec=0),
        **_observer_roots(tmp_path),
    )

    assert payload["ok"] is False
    assert payload["result"]["status"] == "selector_mismatch"
    assert "expected_exactly_one_manifest_report:2" in payload["problems"]
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-report-a.json").exists()
    assert not (tmp_path / "daemon" / "promote_seen" / "synaps-file-report-b.json").exists()


def test_report_waiter_does_not_reselect_observed_report(tmp_path):
    _quarantine_report(tmp_path, transfer_id="synaps-file-report", name="expected.md", note="0059 report")
    first = wait_for_codex_report_by_manifest(
        selector=CodexReportSelector(expected_name="expected.md", note_contains="0059"),
        env=_armed_env(),
        apply=True,
        confirm=CODEX_REPORT_WAITER_CONFIRM_PHRASE,
        watcher_policy=CodexReportWatcherPolicy(max_cycles=1, sleep_sec=0),
        **_observer_roots(tmp_path),
    )
    repeat = wait_for_codex_report_by_manifest(
        selector=CodexReportSelector(expected_name="expected.md", note_contains="0059"),
        env=_armed_env(),
        watcher_policy=CodexReportWatcherPolicy(max_cycles=1, sleep_sec=0),
        **_observer_roots(tmp_path),
    )

    assert first["ok"] is True
    assert repeat["ok"] is True
    assert repeat["matched"] is False
    assert repeat["cycles"][0]["candidate_count"] == 0


def test_cli_report_waiter_apply(tmp_path):
    _quarantine_report(tmp_path, transfer_id="synaps-file-report", name="expected.md", sender="liah-test")
    env = os.environ.copy()
    env.update(_armed_env())

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_report_waiter.py",
            "--env-file",
            "",
            "--expect-name",
            "expected.md",
            "--expect-sender",
            "liah-test",
            "--daemon-root",
            str(tmp_path / "daemon"),
            "--quarantine-root",
            str(tmp_path / "quarantine"),
            "--inbox-root",
            str(tmp_path / "inbox"),
            "--request-root",
            str(tmp_path / "requests"),
            "--max-cycles",
            "2",
            "--sleep-sec",
            "0",
            "--apply",
            "--confirm",
            CODEX_REPORT_WAITER_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["selected_transfer_id"] == "synaps-file-report"
    assert payload["result"]["status"] == "report_observed"
    assert (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").is_file()


def test_cli_report_selector_apply(tmp_path):
    _quarantine_report(tmp_path, transfer_id="synaps-file-report", name="expected.md", sender="liah-test")
    env = os.environ.copy()
    env.update(_armed_env())

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_report_selector.py",
            "--env-file",
            "",
            "--expect-name",
            "expected.md",
            "--expect-sender",
            "liah-test",
            "--daemon-root",
            str(tmp_path / "daemon"),
            "--quarantine-root",
            str(tmp_path / "quarantine"),
            "--inbox-root",
            str(tmp_path / "inbox"),
            "--request-root",
            str(tmp_path / "requests"),
            "--max-cycles",
            "2",
            "--sleep-sec",
            "0",
            "--apply",
            "--confirm",
            CODEX_REPORT_SELECTOR_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["selected_transfer_id"] == "synaps-file-report"
    assert payload["result"]["status"] == "report_observed"
    assert (tmp_path / "daemon" / "promote_seen" / "synaps-file-report.json").is_file()
