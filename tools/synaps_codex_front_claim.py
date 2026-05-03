"""Bounded SYNAPS Codex front-claim CLI."""

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
    if not str(path or "").strip() or not env_path.is_file():
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
        CODEX_FRONT_CLAIM_CLOSE_CONFIRM_PHRASE,
        CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
        DEFAULT_CODEX_FRONT_CLAIM_ROOT,
        CodexFrontClaimPolicy,
        build_codex_front_claim,
        close_codex_front_claim,
        list_codex_front_claims,
        write_codex_front_claim,
    )

    parser = argparse.ArgumentParser(description="Write or list bounded SYNAPS Codex front claims.")
    parser.add_argument("--mode", choices=["write", "list", "close"], default="write")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--root", default=str(DEFAULT_CODEX_FRONT_CLAIM_ROOT))
    parser.add_argument("--front-id", default="")
    parser.add_argument("--claim-id", default="")
    parser.add_argument("--owner", default="")
    parser.add_argument("--marker", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--status", default="claimed")
    parser.add_argument("--close-status", default="completed")
    parser.add_argument("--close-reason", default="")
    parser.add_argument("--lease-sec", type=int, default=1800)
    parser.add_argument("--supersedes", action="append", default=[])
    parser.add_argument("--expect-name", default="")
    parser.add_argument("--expect-sender", default="")
    parser.add_argument("--expect-note-contains", default="")
    parser.add_argument("--expect-sha256", default="")
    parser.add_argument("--expect-size", type=int, default=0)
    parser.add_argument("--operator", default="codex-front-claim")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--confirm",
        default="",
        help=f"Required for write --apply: {CODEX_FRONT_CLAIM_CONFIRM_PHRASE}; close --apply: {CODEX_FRONT_CLAIM_CLOSE_CONFIRM_PHRASE}",
    )
    args = parser.parse_args(raw_argv)

    env = merged_env(args.env_file)
    if args.mode == "list":
        payload = list_codex_front_claims(args.root)
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if payload.get("ok") else 2
    if args.mode == "close":
        payload = close_codex_front_claim(
            args.claim_id,
            status=args.close_status,
            reason=args.close_reason,
            env=env,
            root=args.root,
            apply=args.apply,
            confirm=args.confirm,
            operator=args.operator,
            policy=CodexFrontClaimPolicy.from_env(env),
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if payload.get("ok") else 2

    claim = build_codex_front_claim(
        front_id=args.front_id,
        owner=args.owner,
        marker=args.marker,
        title=args.title,
        status=args.status,
        lease_seconds=args.lease_sec,
        supersedes=args.supersedes,
        expected_report={
            "name": args.expect_name,
            "sender": args.expect_sender,
            "note_contains": args.expect_note_contains,
            "sha256": args.expect_sha256,
            "size": args.expect_size,
            "kind": "codex_report",
        },
    )
    payload = write_codex_front_claim(
        claim,
        env=env,
        root=args.root,
        apply=args.apply,
        confirm=args.confirm,
        operator=args.operator,
        policy=CodexFrontClaimPolicy.from_env(env),
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
