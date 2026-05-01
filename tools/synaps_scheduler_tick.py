"""Dry-run-first scheduler tick for bounded SYNAPS actions.

This tool is not a daemon. A real POST requires:

- `--send`
- `--confirm ESTER_READY_FOR_SYNAPS_SCHEDULE_TICK`
- effective env: `SISTER_SCHEDULE=1`, `SISTER_SCHEDULE_ARMED=1`
- operator-gate confirm and env flags
- action-specific confirm and env flags
"""

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


DEFAULT_SCHEDULER_LEDGER_ROOT = Path("data") / "synaps" / "scheduler"
DEFAULT_OPERATOR_LEDGER_ROOT = Path("data") / "synaps" / "operator_gate"
DEFAULT_CONVERSATION_LEDGER_ROOT = Path("data") / "synaps" / "conversation_windows"


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
        ACTION_CONVERSATION,
        ACTION_FILE_TRANSFER,
        CONVERSATION_WINDOW_CONFIRM_PHRASE,
        FILE_TRANSFER_CONFIRM_PHRASE,
        OPERATOR_GATE_CONFIRM_PHRASE,
        SCHEDULER_CONFIRM_PHRASE,
        ConversationWindowPolicy,
        ConversationWindowStore,
        FileTransferPolicy,
        OperatorGatePolicy,
        OperatorGateStore,
        SchedulerPolicy,
        SchedulerTickStore,
        config_from_env,
        normalize_action,
        scheduler_arm_status,
        synaps_health,
        to_record,
        validate_operator_gate_send_gate,
        validate_scheduler_send_gate,
    )
    from tools.synaps_autochat_window import (
        redacted_request_summary as redacted_conversation_request_summary,
        send_prepared_request,
    )
    from tools.synaps_file_transfer import redacted_file_request_summary, redacted_send_result
    from tools.synaps_operator_gate import _build_action_plan, _send_conversation, _send_file_transfer

    parser = argparse.ArgumentParser(description="Dry-run-first SYNAPS scheduler tick.")
    parser.add_argument(
        "--action",
        default="conversation",
        choices=("conversation", "file-transfer"),
        help="One action to plan or run. The scheduler never runs both in one tick.",
    )
    parser.add_argument("--topic", default=None, help="Conversation topic for a bounded first turn.")
    parser.add_argument("--file", action="append", default=[], help="File to include in a file-transfer manifest.")
    parser.add_argument("--base-dir", default=None, help="Optional safe base dir for file manifest names.")
    parser.add_argument("--kind", default="file", help="File manifest kind label.")
    parser.add_argument("--note", default="", help="Short operator note for file transfer.")
    parser.add_argument("--include-payload", action="store_true", help="Embed capped payload for quarantine write.")
    parser.add_argument("--env-file", default=".env", help="Env file to merge if process env misses keys.")
    parser.add_argument("--scheduler-ledger-root", default=str(DEFAULT_SCHEDULER_LEDGER_ROOT))
    parser.add_argument("--operator-ledger-root", default=str(DEFAULT_OPERATOR_LEDGER_ROOT))
    parser.add_argument("--conversation-ledger-root", default=str(DEFAULT_CONVERSATION_LEDGER_ROOT))
    parser.add_argument("--send", action="store_true", help="Actually run the selected one action.")
    parser.add_argument("--confirm", default="", help=f"Required for --send: {SCHEDULER_CONFIRM_PHRASE}")
    parser.add_argument(
        "--confirm-operator",
        default="",
        help=f"Required for --send: {OPERATOR_GATE_CONFIRM_PHRASE}",
    )
    parser.add_argument(
        "--confirm-conversation",
        default="",
        help=f"Required for conversation --send: {CONVERSATION_WINDOW_CONFIRM_PHRASE}",
    )
    parser.add_argument(
        "--confirm-file-transfer",
        default="",
        help=f"Required for file-transfer --send: {FILE_TRANSFER_CONFIRM_PHRASE}",
    )
    args = parser.parse_args(raw_argv)

    env = merged_env(args.env_file)
    config = config_from_env(env)
    action = normalize_action(args.action)
    scheduler_policy = SchedulerPolicy.from_env(env)
    operator_policy = OperatorGatePolicy.from_env(env)
    conversation_policy = ConversationWindowPolicy.from_env(env)
    file_policy = FileTransferPolicy.from_env(env)
    scheduler_store = SchedulerTickStore(args.scheduler_ledger_root)
    operator_store = OperatorGateStore(args.operator_ledger_root)
    conversation_store = ConversationWindowStore(args.conversation_ledger_root)
    topic = args.topic or _default_topic()
    schedule_gate = scheduler_store.can_run(action, scheduler_policy)

    plan = _build_action_plan(
        action=action,
        config=config,
        topic=topic,
        files=args.file,
        base_dir=args.base_dir,
        kind=args.kind,
        note=args.note,
        include_payload=args.include_payload,
        operator_store=operator_store,
        conversation_store=conversation_store,
        operator_policy=operator_policy,
        conversation_policy=conversation_policy,
        file_policy=file_policy,
        redacted_conversation_request_summary=redacted_conversation_request_summary,
        redacted_file_request_summary=redacted_file_request_summary,
    )

    output: dict[str, Any] = {
        "ok": bool(schedule_gate.ok and plan.get("ok")),
        "dry_run": not args.send,
        "action": action,
        "arm_status": scheduler_arm_status(env),
        "confirm_required": SCHEDULER_CONFIRM_PHRASE,
        "policy": scheduler_policy.to_record(),
        "schedule_gate": schedule_gate.to_record(),
        "operator_confirm_required": OPERATOR_GATE_CONFIRM_PHRASE,
        "action_plan": plan,
        "synaps_health": to_record(synaps_health(config)),
    }

    if args.send:
        gate_problems = validate_scheduler_send_gate(env, args.confirm, (action,), scheduler_store, scheduler_policy)
        gate_problems.extend(
            validate_operator_gate_send_gate(
                env,
                args.confirm_operator,
                (action,),
                operator_store,
                operator_policy,
            )
        )
        if gate_problems:
            output["ok"] = False
            output["result"] = {"ok": False, "status": 0, "body": {"error": "send_gate_failed", "problems": gate_problems}}
            print(json.dumps(redacted_send_result(output, config.sync_token), ensure_ascii=False, indent=2, sort_keys=True))
            return 2

        if action == ACTION_CONVERSATION:
            result = _send_conversation(
                env=env,
                confirm=args.confirm_conversation,
                config=config,
                topic=topic,
                operator_store=operator_store,
                conversation_store=conversation_store,
                policy=conversation_policy,
                send_prepared_request=send_prepared_request,
            )
            action_id = str(result.get("window_id") or "")
            summary = {"window_id": action_id, "message_count": 2, "memory": "off", "files": "manifest_only"}
        elif action == ACTION_FILE_TRANSFER:
            result = _send_file_transfer(
                env=env,
                confirm=args.confirm_file_transfer,
                config=config,
                files=args.file,
                base_dir=args.base_dir,
                kind=args.kind,
                note=args.note,
                include_payload=args.include_payload,
                operator_store=operator_store,
                operator_policy=operator_policy,
                file_policy=file_policy,
                send_prepared_request=send_prepared_request,
            )
            action_id = str(result.get("transfer_id") or "")
            summary = {
                "transfer_id": action_id,
                "file_count": len(args.file),
                "auto_ingest": False,
                "memory": "off",
            }
        else:
            result = {"ok": False, "status": 0, "body": {"error": "unknown_scheduler_action"}}
            action_id = ""
            summary = {}

        status = int(result.get("status") or 0)
        if status or result.get("body", {}).get("error") != "send_gate_failed":
            scheduler_store.record_tick_result(
                action=action,
                action_id=action_id,
                ok=bool(result.get("ok")),
                status=status,
                summary=summary,
            )
        output["result"] = result
        if not result.get("ok"):
            output["ok"] = False

    print(json.dumps(redacted_send_result(output, config.sync_token), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output.get("ok") else 2


def _default_topic() -> str:
    from modules.synaps import DEFAULT_WINDOW_TOPIC

    return DEFAULT_WINDOW_TOPIC


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
    sys.exit(main())
