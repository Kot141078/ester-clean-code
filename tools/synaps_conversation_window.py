"""Dry-run-first controller for bounded SYNAPS sister conversation windows."""

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

from modules.synaps.window import (  # noqa: E402
    CONVERSATION_WINDOW_CONFIRM_PHRASE,
    DEFAULT_WINDOW_TOPIC,
    ConversationWindowPolicy,
    ConversationWindowStore,
    build_conversation_turn_request,
    conversation_window_arm_status,
    validate_conversation_send_gate,
)
from tools.synaps_autochat_window import (  # noqa: E402
    load_env_file,
    redacted_request_summary,
    redacted_send_result,
    send_prepared_request,
)


DEFAULT_LEDGER_ROOT = Path("data") / "synaps" / "conversation_windows"


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

    from modules.synaps import config_from_env, synaps_health, to_record

    parser = argparse.ArgumentParser(description="Dry-run-first SYNAPS conversation window controller.")
    parser.add_argument("--topic", default=DEFAULT_WINDOW_TOPIC, help="Bounded first-turn topic.")
    parser.add_argument("--env-file", default=".env", help="Env file to merge if process env misses keys.")
    parser.add_argument("--ledger-root", default=str(DEFAULT_LEDGER_ROOT), help="Explicit window ledger root.")
    parser.add_argument("--send", action="store_true", help="Actually send the first bounded window turn.")
    parser.add_argument("--confirm", default="", help=f"Required for --send: {CONVERSATION_WINDOW_CONFIRM_PHRASE}")
    args = parser.parse_args(raw_argv)

    env = merged_env(args.env_file)
    config = config_from_env(env)
    policy = ConversationWindowPolicy.from_env(env)
    store = ConversationWindowStore(args.ledger_root)
    window_id = f"synaps-window-preview-{to_record(synaps_health(config))['node_id']}"
    status = conversation_window_arm_status(env)
    gate = store.can_open(policy)

    try:
        request = build_conversation_turn_request(
            config,
            policy,
            window_id=window_id,
            content=args.topic,
            message_index=1,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "dry_run": not args.send,
                    "error": exc.__class__.__name__,
                    "message": str(exc),
                    "arm_status": status,
                    "policy": policy.to_record(),
                    "gate": gate.to_record(),
                    "synaps_health": to_record(synaps_health(config)),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    output: dict[str, Any] = {
        "ok": True,
        "dry_run": not args.send,
        "arm_status": status,
        "confirm_required": CONVERSATION_WINDOW_CONFIRM_PHRASE,
        "gate": gate.to_record(),
        "policy": policy.to_record(),
        "planned": {
            "message_budget": policy.max_messages,
            "message_cost_first_turn": 2,
            "max_duration_sec": policy.max_duration_sec,
            "cooldown_sec": policy.cooldown_sec,
            "memory": "off",
            "files": "manifest_only",
            "ledger_root": str(Path(args.ledger_root)),
        },
        "request": redacted_request_summary(request, config),
    }

    if args.send:
        problems = validate_conversation_send_gate(env, args.confirm, store, policy)
        if problems:
            output["ok"] = False
            output["result"] = {"ok": False, "status": 0, "body": {"error": "send_gate_failed", "problems": problems}}
            print(json.dumps(redacted_send_result(output, config.sync_token), ensure_ascii=False, indent=2, sort_keys=True))
            return 2

        open_record = store.open_window(policy, args.topic)
        actual_window_id = str(open_record["window_id"])
        request = build_conversation_turn_request(
            config,
            policy,
            window_id=actual_window_id,
            content=args.topic,
            message_index=1,
        )
        store.record_turn(
            actual_window_id,
            direction="outbound",
            message_index=1,
            content=args.topic,
            status="prepared",
            policy=policy,
        )
        result = send_prepared_request(request)
        store.record_turn(
            actual_window_id,
            direction="inbound",
            message_index=2,
            content=_result_content(result),
            status=str(result.get("status", 0)),
            policy=policy,
            extra={"ok": bool(result.get("ok"))},
        )
        if not result.get("ok"):
            store.close_window(actual_window_id, "send_failed", policy, message_count=2)
        output["request"] = redacted_request_summary(request, config)
        output["window"] = open_record
        output["result"] = redacted_send_result(result, config.sync_token)

    print(json.dumps(redacted_send_result(output, config.sync_token), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _env_file_from_argv(argv: list[str]) -> str:
    for index, item in enumerate(argv):
        if item == "--env-file" and index + 1 < len(argv):
            return argv[index + 1]
        if item.startswith("--env-file="):
            return item.split("=", 1)[1]
    return ".env"


def _result_content(result: Mapping[str, Any]) -> str:
    body = result.get("body")
    if isinstance(body, Mapping):
        content = body.get("content")
        if content:
            return str(content)
        return json.dumps(dict(body), ensure_ascii=False, sort_keys=True)
    return str(body or "")


if __name__ == "__main__":
    sys.exit(main())
