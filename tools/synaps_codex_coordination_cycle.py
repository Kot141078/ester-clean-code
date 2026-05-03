"""One-shot SYNAPS Codex coordination cycle CLI."""

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
        CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE,
        DEFAULT_CODEX_COORDINATION_CYCLE_ROOT,
        DEFAULT_CODEX_COORDINATION_SCANNER_ROOT,
        DEFAULT_CODEX_DAEMON_ROOT,
        DEFAULT_CODEX_INBOX_ROOT,
        DEFAULT_CODEX_RECEIPT_LEDGER,
        DEFAULT_CODEX_REQUEST_ROOT,
        DEFAULT_QUARANTINE_ROOT,
        FILE_TRANSFER_CONFIRM_PHRASE,
        PHASE_SEND_FILE,
        PHASE_WAIT_CONTRACT,
        PHASE_WAIT_REPORT,
        CodexCoordinationCyclePolicy,
        CodexCoordinationSelector,
        CodexCoordinationSendSpec,
        CodexReportSelector,
        run_codex_coordination_cycle_phase,
    )

    parser = argparse.ArgumentParser(description="Run one bounded SYNAPS Codex coordination cycle phase.")
    parser.add_argument("--phase", required=True, choices=[PHASE_SEND_FILE, PHASE_WAIT_CONTRACT, PHASE_WAIT_REPORT])
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--operator", default="codex-coordination-cycle")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--cycle-root", default=str(DEFAULT_CODEX_COORDINATION_CYCLE_ROOT))
    parser.add_argument("--confirm", default="", help=f"Required: {CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE}")
    parser.add_argument("--max-cycles", type=int, default=0)
    parser.add_argument("--sleep-sec", type=float, default=-1.0)
    parser.add_argument("--max-wall-clock-sec", type=float, default=0.0)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--file", default="")
    parser.add_argument("--base-dir", default="")
    parser.add_argument("--kind", default="codex_contract")
    parser.add_argument("--note", default="")
    parser.add_argument("--include-payload", action="store_true")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--send-confirm", default="", help=f"Required for --send: {FILE_TRANSFER_CONFIRM_PHRASE}")
    parser.add_argument("--expect-name", default="")
    parser.add_argument("--expect-kind", default="codex_contract", choices=["codex_contract", "codex_report"])
    parser.add_argument("--expect-sender", default="")
    parser.add_argument("--note-contains", default="")
    parser.add_argument("--expect-sha256", default="")
    parser.add_argument("--expect-size", type=int, default=-1)
    parser.add_argument("--scanner-root", default=str(DEFAULT_CODEX_COORDINATION_SCANNER_ROOT))
    parser.add_argument("--quarantine-root", default=str(DEFAULT_QUARANTINE_ROOT))
    parser.add_argument("--inbox-root", default=str(DEFAULT_CODEX_INBOX_ROOT))
    parser.add_argument("--daemon-root", default=str(DEFAULT_CODEX_DAEMON_ROOT))
    parser.add_argument("--receipt-ledger", default=str(DEFAULT_CODEX_RECEIPT_LEDGER))
    parser.add_argument("--request-root", default=str(DEFAULT_CODEX_REQUEST_ROOT))
    parser.add_argument("--postcheck-root", action="append", default=[])
    args = parser.parse_args(raw_argv)

    env = merged_env(args.env_file)
    policy = CodexCoordinationCyclePolicy.from_env(env)
    if args.max_cycles:
        policy = CodexCoordinationCyclePolicy(
            max_cycles=args.max_cycles,
            sleep_sec=policy.sleep_sec,
            max_wall_clock_sec=policy.max_wall_clock_sec,
            require_exact_for_live_wait=policy.require_exact_for_live_wait,
            postcheck_max_file_bytes=policy.postcheck_max_file_bytes,
        )
    if args.sleep_sec >= 0:
        policy = CodexCoordinationCyclePolicy(
            max_cycles=policy.max_cycles,
            sleep_sec=args.sleep_sec,
            max_wall_clock_sec=policy.max_wall_clock_sec,
            require_exact_for_live_wait=policy.require_exact_for_live_wait,
            postcheck_max_file_bytes=policy.postcheck_max_file_bytes,
        )
    if args.max_wall_clock_sec:
        policy = CodexCoordinationCyclePolicy(
            max_cycles=policy.max_cycles,
            sleep_sec=policy.sleep_sec,
            max_wall_clock_sec=args.max_wall_clock_sec,
            require_exact_for_live_wait=policy.require_exact_for_live_wait,
            postcheck_max_file_bytes=policy.postcheck_max_file_bytes,
        )

    selector = None
    if args.phase == PHASE_WAIT_CONTRACT:
        selector = CodexCoordinationSelector(
            expected_name=args.expect_name,
            expected_kind=args.expect_kind,
            expected_sender=args.expect_sender,
            note_contains=args.note_contains,
            expected_sha256=args.expect_sha256,
            expected_size=None if args.expect_size < 0 else args.expect_size,
        )
    elif args.phase == PHASE_WAIT_REPORT:
        selector = CodexReportSelector(
            expected_name=args.expect_name,
            expected_sender=args.expect_sender,
            note_contains=args.note_contains,
            expected_sha256=args.expect_sha256,
            expected_size=None if args.expect_size < 0 else args.expect_size,
        )

    send_spec = None
    if args.phase == PHASE_SEND_FILE:
        send_spec = CodexCoordinationSendSpec(
            file_path=args.file,
            base_dir=args.base_dir,
            kind=args.kind,
            note=args.note,
            include_payload=args.include_payload,
        )

    payload = run_codex_coordination_cycle_phase(
        phase=args.phase,
        nonce=args.nonce,
        operator=args.operator,
        env=env,
        env_file=args.env_file,
        cycle_root=args.cycle_root,
        selector=selector,
        send_spec=send_spec,
        apply=args.apply,
        send=args.send,
        confirm=args.confirm,
        send_confirm=args.send_confirm,
        policy=policy,
        scanner_root=args.scanner_root,
        quarantine_root=args.quarantine_root,
        inbox_root=args.inbox_root,
        daemon_root=args.daemon_root,
        receipt_ledger=args.receipt_ledger,
        request_root=args.request_root,
        postcheck_roots=args.postcheck_root,
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
