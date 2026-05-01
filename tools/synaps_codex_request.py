"""Dry-run-first CLI for the SYNAPS Codex request queue."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, MutableMapping

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
        key = key.strip()
        if key:
            values[key] = _strip_env_value(value)
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
        CODEX_REQUEST_CLAIM_CONFIRM_PHRASE,
        CODEX_REQUEST_COMPLETE_CONFIRM_PHRASE,
        CODEX_REQUEST_CREATE_CONFIRM_PHRASE,
        DEFAULT_CODEX_REQUEST_ROOT,
        CodexRequestPolicy,
        CodexRequestStore,
        codex_request_arm_status,
        validate_codex_request_gate,
    )

    parser = argparse.ArgumentParser(description="Manage fail-closed SYNAPS Codex requests.")
    parser.add_argument("action", choices=("create", "list", "show", "claim", "complete"))
    parser.add_argument("--root", default=str(DEFAULT_CODEX_REQUEST_ROOT))
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--request-id", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--task", default="")
    parser.add_argument("--requester", default="sister")
    parser.add_argument("--origin", default="unknown")
    parser.add_argument("--priority", default="normal", choices=("low", "normal", "high"))
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--transfer-id", action="append", default=[])
    parser.add_argument("--status", default="")
    parser.add_argument("--operator", default="codex")
    parser.add_argument("--summary", default="")
    parser.add_argument("--result-status", default="completed", choices=("completed", "blocked"))
    parser.add_argument("--apply", action="store_true", help="Actually write claim/create/complete events.")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args(raw_argv)

    env = merged_env(args.env_file)
    policy = CodexRequestPolicy.from_env(env)
    store = CodexRequestStore(args.root, policy)

    try:
        if args.action == "create":
            request_record = store.build_request(
                title=args.title,
                task=args.task,
                requester=args.requester,
                origin=args.origin,
                priority=args.priority,
                tags=args.tag,
                related_transfer_ids=args.transfer_id,
                request_id=args.request_id or None,
            )
            payload: dict[str, Any] = {
                "ok": True,
                "dry_run": not args.apply,
                "action": "create",
                "confirm_required": CODEX_REQUEST_CREATE_CONFIRM_PHRASE,
                "arm_status": codex_request_arm_status(env),
                "policy": policy.to_record(),
                "request": request_record,
                "auto_execute": False,
                "auto_ingest": False,
                "memory": "off",
            }
            if args.apply:
                problems = validate_codex_request_gate(env, args.confirm, CODEX_REQUEST_CREATE_CONFIRM_PHRASE)
                if problems:
                    payload["ok"] = False
                    payload["result"] = {"ok": False, "error": "request_gate_failed", "problems": problems}
                    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
                    return 2
                payload["result"] = store.create_request(request_record)
        elif args.action == "list":
            payload = store.list_requests(status=args.status or None)
            payload["dry_run"] = True
        elif args.action == "show":
            if not args.request_id:
                raise ValueError("--request-id is required for show")
            payload = store.inspect_request(args.request_id)
            payload["dry_run"] = True
        elif args.action == "claim":
            if not args.request_id:
                raise ValueError("--request-id is required for claim")
            payload = {
                "ok": True,
                "dry_run": not args.apply,
                "action": "claim",
                "confirm_required": CODEX_REQUEST_CLAIM_CONFIRM_PHRASE,
                "arm_status": codex_request_arm_status(env),
                "request": store.inspect_request(args.request_id),
            }
            if args.apply:
                problems = validate_codex_request_gate(env, args.confirm, CODEX_REQUEST_CLAIM_CONFIRM_PHRASE)
                if problems:
                    payload["ok"] = False
                    payload["result"] = {"ok": False, "error": "request_gate_failed", "problems": problems}
                    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
                    return 2
                payload["result"] = store.claim_request(args.request_id, operator=args.operator)
        else:
            if not args.request_id:
                raise ValueError("--request-id is required for complete")
            payload = {
                "ok": True,
                "dry_run": not args.apply,
                "action": "complete",
                "confirm_required": CODEX_REQUEST_COMPLETE_CONFIRM_PHRASE,
                "arm_status": codex_request_arm_status(env),
                "request": store.inspect_request(args.request_id),
            }
            if args.apply:
                problems = validate_codex_request_gate(env, args.confirm, CODEX_REQUEST_COMPLETE_CONFIRM_PHRASE)
                if problems:
                    payload["ok"] = False
                    payload["result"] = {"ok": False, "error": "request_gate_failed", "problems": problems}
                    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
                    return 2
                payload["result"] = store.complete_request(
                    args.request_id,
                    operator=args.operator,
                    summary=args.summary,
                    status=args.result_status,
                )
    except Exception as exc:
        payload = {"ok": False, "error": exc.__class__.__name__, "message": str(exc)}

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
