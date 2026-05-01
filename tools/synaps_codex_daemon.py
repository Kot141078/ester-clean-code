"""Dry-run-first local SYNAPS Codex bridge daemon."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
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
        CODEX_DAEMON_BASELINE_CONFIRM_PHRASE,
        CODEX_DAEMON_CONFIRM_PHRASE,
        CODEX_DAEMON_PERSISTENT_CONFIRM_PHRASE,
        DEFAULT_CODEX_DAEMON_ROOT,
        DEFAULT_CODEX_INBOX_ROOT,
        DEFAULT_CODEX_RECEIPT_LEDGER,
        DEFAULT_CODEX_REQUEST_ROOT,
        DEFAULT_QUARANTINE_ROOT,
        CodexDaemon,
        CodexDaemonPolicy,
        codex_daemon_arm_status,
        validate_codex_daemon_persistent_gate,
    )

    parser = argparse.ArgumentParser(description="Run one dry-run/apply cycle of the SYNAPS Codex daemon.")
    parser.add_argument("action", choices=("status", "baseline", "cycle", "daemon"), nargs="?", default="cycle")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--daemon-root", default=str(DEFAULT_CODEX_DAEMON_ROOT))
    parser.add_argument("--quarantine-root", default=str(DEFAULT_QUARANTINE_ROOT))
    parser.add_argument("--inbox-root", default=str(DEFAULT_CODEX_INBOX_ROOT))
    parser.add_argument("--receipt-ledger", default=str(DEFAULT_CODEX_RECEIPT_LEDGER))
    parser.add_argument("--request-root", default=str(DEFAULT_CODEX_REQUEST_ROOT))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--operator", default="codex-daemon")
    parser.add_argument("--max-cycles", type=int, default=0, help="Only for daemon; 0 means forever.")
    args = parser.parse_args(raw_argv)

    env = merged_env(args.env_file)
    policy = CodexDaemonPolicy.from_env(env)
    daemon = CodexDaemon(
        daemon_root=args.daemon_root,
        quarantine_root=args.quarantine_root,
        inbox_root=args.inbox_root,
        receipt_ledger=args.receipt_ledger,
        request_root=args.request_root,
        policy=policy,
    )

    if args.action == "status":
        payload = {
            "ok": True,
            "dry_run": True,
            "confirm_required": CODEX_DAEMON_CONFIRM_PHRASE,
            "baseline_confirm_required": CODEX_DAEMON_BASELINE_CONFIRM_PHRASE,
            "persistent_confirm_required": CODEX_DAEMON_PERSISTENT_CONFIRM_PHRASE,
            "arm_status": codex_daemon_arm_status(env),
            "policy": policy.to_record(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if args.action == "baseline":
        payload = daemon.baseline_existing(env=env, apply=args.apply, confirm=args.confirm, operator=args.operator)
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if payload.get("ok") else 2

    if args.action == "cycle":
        payload = daemon.cycle(env=env, apply=args.apply, confirm=args.confirm, operator=args.operator)
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if payload.get("ok") else 2

    persistent_mode = args.max_cycles == 0
    if persistent_mode:
        problems = validate_codex_daemon_persistent_gate(env, args.confirm)
        if problems:
            payload = {
                "ok": False,
                "dry_run": not args.apply,
                "action": "daemon",
                "confirm_required": CODEX_DAEMON_PERSISTENT_CONFIRM_PHRASE,
                "arm_status": codex_daemon_arm_status(env),
                "policy": policy.to_record(),
                "result": {"ok": False, "error": "persistent_daemon_gate_failed", "problems": problems},
                "auto_ingest": False,
                "memory": "off",
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            return 2

    cycles = 0
    cycle_confirm = CODEX_DAEMON_CONFIRM_PHRASE if persistent_mode else args.confirm
    while True:
        payload = daemon.cycle(env=env, apply=args.apply, confirm=cycle_confirm, operator=args.operator)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)
        if not payload.get("ok"):
            return 2
        cycles += 1
        if args.max_cycles and cycles >= args.max_cycles:
            return 0
        time.sleep(policy.poll_interval_sec)


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
