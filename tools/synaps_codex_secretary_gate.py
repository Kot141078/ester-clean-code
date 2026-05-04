#!/usr/bin/env python3
"""Run one bounded Secretary-Codex response gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _bootstrap_repo_path() -> None:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _load_env_file(path: str) -> dict[str, str]:
    if not path:
        return {}
    env_path = Path(path)
    if not env_path.exists():
        return {}
    data: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _optional_size(value: str) -> int | None:
    if value == "":
        return None
    return int(value)


def main(argv: list[str] | None = None) -> int:
    _bootstrap_repo_path()
    from modules.synaps import (
        CODEX_SECRETARY_GATE_CONFIRM_PHRASE,
        CodexCoordinationSelector,
        CodexSecretaryResponsePolicy,
        CodexSecretaryResponseSelectors,
        run_codex_secretary_response_gate,
    )

    parser = argparse.ArgumentParser(description="Wait for one bounded Secretary-Codex next-work or idle response.")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--secretary-root", default="data/synaps/codex_bridge/secretary_gate")
    parser.add_argument("--scanner-root", default="data/synaps/codex_bridge/coordination_scanner")
    parser.add_argument("--quarantine-root", default="data/synaps/quarantine")
    parser.add_argument("--inbox-root", default="data/synaps/codex_bridge/inbox")
    parser.add_argument("--next-name", required=True)
    parser.add_argument("--idle-name", required=True)
    parser.add_argument("--expect-sender", default="")
    parser.add_argument("--note-contains", default="")
    parser.add_argument("--next-sha256", default="")
    parser.add_argument("--next-size", default="")
    parser.add_argument("--idle-sha256", default="")
    parser.add_argument("--idle-size", default="")
    parser.add_argument("--max-cycles", type=int, default=3)
    parser.add_argument("--sleep-sec", type=float, default=5.0)
    parser.add_argument("--operator", default="codex-secretary-gate")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args(argv)

    env = _load_env_file(args.env_file)
    import os

    merged_env = dict(os.environ)
    merged_env.update({key: value for key, value in env.items() if key not in merged_env})
    selectors = CodexSecretaryResponseSelectors(
        next_work=CodexCoordinationSelector(
            expected_name=args.next_name,
            expected_kind="codex_contract",
            expected_sender=args.expect_sender,
            note_contains=args.note_contains,
            expected_sha256=args.next_sha256,
            expected_size=_optional_size(args.next_size),
        ),
        idle=CodexCoordinationSelector(
            expected_name=args.idle_name,
            expected_kind="codex_report",
            expected_sender=args.expect_sender,
            note_contains=args.note_contains,
            expected_sha256=args.idle_sha256,
            expected_size=_optional_size(args.idle_size),
        ),
    )
    payload = run_codex_secretary_response_gate(
        selectors=selectors,
        env=merged_env,
        apply=args.apply,
        confirm=args.confirm,
        operator=args.operator,
        secretary_root=args.secretary_root,
        scanner_root=args.scanner_root,
        quarantine_root=args.quarantine_root,
        inbox_root=args.inbox_root,
        policy=CodexSecretaryResponsePolicy(max_cycles=args.max_cycles, sleep_sec=args.sleep_sec),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
