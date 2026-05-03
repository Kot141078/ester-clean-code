"""Bounded SYNAPS Codex coordination session CLI."""

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
        CODEX_COORDINATION_SESSION_CONFIRM_PHRASE,
        DEFAULT_CODEX_COORDINATION_SESSION_ROOT,
        CodexCoordinationSessionPolicy,
        load_codex_coordination_session_plan,
        run_codex_coordination_session,
    )

    parser = argparse.ArgumentParser(description="Run a bounded SYNAPS Codex coordination session plan.")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--session-root", default=str(DEFAULT_CODEX_COORDINATION_SESSION_ROOT))
    parser.add_argument("--confirm", default="", help=f"Required: {CODEX_COORDINATION_SESSION_CONFIRM_PHRASE}")
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--max-wall-clock-sec", type=float, default=0.0)
    parser.add_argument("--postcheck-root", action="append", default=[])
    args = parser.parse_args(raw_argv)

    env = merged_env(args.env_file)
    policy = CodexCoordinationSessionPolicy.from_env(env)
    if args.max_steps:
        policy = CodexCoordinationSessionPolicy(
            max_steps=args.max_steps,
            max_wall_clock_sec=policy.max_wall_clock_sec,
        )
    if args.max_wall_clock_sec:
        policy = CodexCoordinationSessionPolicy(
            max_steps=policy.max_steps,
            max_wall_clock_sec=args.max_wall_clock_sec,
        )

    payload = run_codex_coordination_session(
        plan=load_codex_coordination_session_plan(args.plan),
        env=env,
        env_file=args.env_file,
        session_root=args.session_root,
        confirm=args.confirm,
        policy=policy,
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
