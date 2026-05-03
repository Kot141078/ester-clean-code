"""Bounded report waiter for one expected SYNAPS Codex report."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Mapping, MutableMapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_env_file(path: str | Path) -> dict[str, str]:
    env_path = Path(path)
    if not env_path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip():
            values[key.strip()] = _strip_env_value(value)
    return values


def bootstrap_env_from_argv(argv: list[str], environ: MutableMapping[str, str] | None = None) -> None:
    target = os.environ if environ is None else environ
    for key, value in load_env_file(_env_file_from_argv(argv)).items():
        target.setdefault(key, value)


def merged_env(env_file: str | None = ".env", base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    if env_file:
        for key, value in load_env_file(env_file).items():
            env.setdefault(key, value)
    return env


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    bootstrap_env_from_argv(raw_argv)

    from modules.synaps import (
        CODEX_REPORT_WAITER_CONFIRM_PHRASE,
        DEFAULT_CODEX_DAEMON_ROOT,
        DEFAULT_CODEX_INBOX_ROOT,
        DEFAULT_CODEX_RECEIPT_LEDGER,
        DEFAULT_CODEX_REQUEST_ROOT,
        DEFAULT_QUARANTINE_ROOT,
        CodexReportSelector,
        CodexReportWatcherPolicy,
        wait_for_codex_report_by_manifest,
    )

    parser = argparse.ArgumentParser(description="Wait bounded cycles for one expected Codex report by manifest metadata.")
    parser.add_argument("--expect-name", required=True, help="Exact expected report filename from the quarantined manifest.")
    parser.add_argument(
        "--expect-name-alias",
        action="append",
        default=[],
        help="Additional pre-approved report filename accepted only with the same sender/note/SHA/size selector.",
    )
    parser.add_argument("--expect-sender", default="", help="Optional exact manifest received_from value.")
    parser.add_argument("--note-contains", default="", help="Optional substring expected in manifest note.")
    parser.add_argument("--expect-sha256", default="", help="Optional exact file SHA256 from manifest.")
    parser.add_argument("--expect-size", type=int, default=-1, help="Optional exact file size in bytes.")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--daemon-root", default=str(DEFAULT_CODEX_DAEMON_ROOT))
    parser.add_argument("--quarantine-root", default=str(DEFAULT_QUARANTINE_ROOT))
    parser.add_argument("--inbox-root", default=str(DEFAULT_CODEX_INBOX_ROOT))
    parser.add_argument("--receipt-ledger", default=str(DEFAULT_CODEX_RECEIPT_LEDGER))
    parser.add_argument("--request-root", default=str(DEFAULT_CODEX_REQUEST_ROOT))
    parser.add_argument("--operator", default="codex-report-waiter")
    parser.add_argument("--max-cycles", type=int, default=0)
    parser.add_argument("--sleep-sec", type=float, default=-1.0)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="", help=f"Required for --apply: {CODEX_REPORT_WAITER_CONFIRM_PHRASE}")
    args = parser.parse_args(raw_argv)

    env = merged_env(args.env_file)
    policy = CodexReportWatcherPolicy.from_env(env)
    if args.max_cycles:
        policy = CodexReportWatcherPolicy(max_cycles=args.max_cycles, sleep_sec=policy.sleep_sec)
    if args.sleep_sec >= 0:
        policy = CodexReportWatcherPolicy(max_cycles=policy.max_cycles, sleep_sec=args.sleep_sec)

    selector = CodexReportSelector(
        expected_name=args.expect_name,
        expected_sender=args.expect_sender,
        note_contains=args.note_contains,
        expected_sha256=args.expect_sha256,
        expected_size=None if args.expect_size < 0 else args.expect_size,
        expected_name_aliases=tuple(args.expect_name_alias),
    )
    payload = wait_for_codex_report_by_manifest(
        selector=selector,
        env=env,
        apply=args.apply,
        confirm=args.confirm,
        operator=args.operator,
        daemon_root=args.daemon_root,
        quarantine_root=args.quarantine_root,
        inbox_root=args.inbox_root,
        receipt_ledger=args.receipt_ledger,
        request_root=args.request_root,
        watcher_policy=policy,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 2


def _strip_env_value(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1]
    return stripped


def _env_file_from_argv(argv: list[str]) -> str:
    for index, item in enumerate(argv):
        if item == "--env-file" and index + 1 < len(argv):
            return argv[index + 1]
        if item.startswith("--env-file="):
            return item.split("=", 1)[1]
    return ".env"


if __name__ == "__main__":
    raise SystemExit(main())
