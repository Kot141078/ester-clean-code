"""Dry-run-first scheduler/operator gate for SYNAPS conversations and files.

This tool is not a daemon. A real POST requires:

- `--send`
- `--confirm ESTER_READY_FOR_SYNAPS_OPERATOR_GATE`
- effective env: `SISTER_OPERATOR_GATE=1`, `SISTER_OPERATOR_GATE_ARMED=1`
- action-specific env and confirm from the existing conversation/file tools
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


DEFAULT_CONVERSATION_LEDGER_ROOT = Path("data") / "synaps" / "conversation_windows"
DEFAULT_OPERATOR_LEDGER_ROOT = Path("data") / "synaps" / "operator_gate"


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
        ConversationWindowPolicy,
        ConversationWindowStore,
        FileTransferPolicy,
        OperatorGatePolicy,
        OperatorGateStore,
        build_conversation_turn_request,
        build_file_manifest,
        build_file_manifest_request,
        config_from_env,
        normalize_actions,
        operator_gate_arm_status,
        synaps_health,
        to_record,
        validate_conversation_send_gate,
        validate_file_transfer_send_gate,
        validate_operator_gate_send_gate,
    )
    from tools.synaps_autochat_window import (
        redacted_request_summary as redacted_conversation_request_summary,
        send_prepared_request,
    )
    from tools.synaps_file_transfer import (
        redacted_file_request_summary,
        redacted_send_result,
    )

    parser = argparse.ArgumentParser(description="Dry-run-first SYNAPS scheduler/operator gate.")
    parser.add_argument(
        "--action",
        default="conversation",
        choices=("conversation", "file-transfer", "both"),
        help="Action to plan. Real --send is limited to one action per tick.",
    )
    parser.add_argument("--topic", default=None, help="Conversation topic for a bounded first turn.")
    parser.add_argument("--file", action="append", default=[], help="File to include in a file-transfer manifest.")
    parser.add_argument("--base-dir", default=None, help="Optional safe base dir for file manifest names.")
    parser.add_argument("--kind", default="file", help="File manifest kind label.")
    parser.add_argument("--note", default="", help="Short operator note for file transfer.")
    parser.add_argument("--include-payload", action="store_true", help="Embed capped payload for quarantine write.")
    parser.add_argument("--env-file", default=".env", help="Env file to merge if process env misses keys.")
    parser.add_argument("--ledger-root", default=str(DEFAULT_OPERATOR_LEDGER_ROOT), help="Operator gate ledger root.")
    parser.add_argument(
        "--conversation-ledger-root",
        default=str(DEFAULT_CONVERSATION_LEDGER_ROOT),
        help="Conversation window ledger root.",
    )
    parser.add_argument("--send", action="store_true", help="Actually run the selected one action.")
    parser.add_argument("--confirm", default="", help=f"Required for --send: {OPERATOR_GATE_CONFIRM_PHRASE}")
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
    operator_policy = OperatorGatePolicy.from_env(env)
    conversation_policy = ConversationWindowPolicy.from_env(env)
    file_policy = FileTransferPolicy.from_env(env)
    operator_store = OperatorGateStore(args.ledger_root)
    conversation_store = ConversationWindowStore(args.conversation_ledger_root)
    actions = normalize_actions(args.action)
    topic = args.topic or _default_topic()

    output: dict[str, Any] = {
        "ok": True,
        "dry_run": not args.send,
        "action": args.action,
        "actions": [],
        "arm_status": operator_gate_arm_status(env),
        "confirm_required": OPERATOR_GATE_CONFIRM_PHRASE,
        "policy": operator_policy.to_record(),
        "synaps_health": to_record(synaps_health(config)),
    }

    for action in actions:
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
        output["actions"].append(plan)
        if not plan.get("ok"):
            output["ok"] = False

    if args.send:
        gate_problems = validate_operator_gate_send_gate(
            env,
            args.confirm,
            actions,
            operator_store,
            operator_policy,
        )
        if gate_problems:
            output["ok"] = False
            output["result"] = {"ok": False, "status": 0, "body": {"error": "send_gate_failed", "problems": gate_problems}}
            print(json.dumps(redacted_send_result(output, config.sync_token), ensure_ascii=False, indent=2, sort_keys=True))
            return 2

        if actions == (ACTION_CONVERSATION,):
            output["result"] = _send_conversation(
                env=env,
                confirm=args.confirm_conversation,
                config=config,
                topic=topic,
                operator_store=operator_store,
                conversation_store=conversation_store,
                policy=conversation_policy,
                send_prepared_request=send_prepared_request,
            )
        elif actions == (ACTION_FILE_TRANSFER,):
            output["result"] = _send_file_transfer(
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
        else:
            output["result"] = {
                "ok": False,
                "status": 0,
                "body": {"error": "send_gate_failed", "problems": ["operator_gate_allows_one_action_per_tick"]},
            }

        if not output["result"].get("ok"):
            output["ok"] = False

    print(json.dumps(redacted_send_result(output, config.sync_token), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output.get("ok") else 2


def _build_action_plan(
    *,
    action: str,
    config: Any,
    topic: str,
    files: list[str],
    base_dir: str | None,
    kind: str,
    note: str,
    include_payload: bool,
    operator_store: Any,
    conversation_store: Any,
    operator_policy: Any,
    conversation_policy: Any,
    file_policy: Any,
    redacted_conversation_request_summary: Any,
    redacted_file_request_summary: Any,
) -> dict[str, Any]:
    from modules.synaps import (
        ACTION_CONVERSATION,
        ACTION_FILE_TRANSFER,
        build_conversation_turn_request,
        build_file_manifest,
        build_file_manifest_request,
    )

    if action == ACTION_CONVERSATION:
        gate = conversation_store.can_open(conversation_policy)
        try:
            request = build_conversation_turn_request(
                config,
                conversation_policy,
                window_id=f"synaps-window-preview-{config.node_id}",
                content=topic,
                message_index=1,
            )
        except Exception as exc:
            return _error_plan(action, exc)
        return {
            "action": ACTION_CONVERSATION,
            "ok": gate.ok,
            "gate": gate.to_record(),
            "confirm_required": "ESTER_READY_FOR_CONVERSATION_WINDOW",
            "planned": {
                "message_cost_first_turn": 2,
                "max_duration_sec": conversation_policy.max_duration_sec,
                "max_messages": conversation_policy.max_messages,
                "cooldown_sec": conversation_policy.cooldown_sec,
                "memory": "off",
                "files": "manifest_only",
            },
            "request": redacted_conversation_request_summary(request, config),
        }

    if action == ACTION_FILE_TRANSFER:
        gate = operator_store.can_run_file_transfer(operator_policy)
        try:
            manifest = build_file_manifest(
                files,
                file_policy,
                include_payload=include_payload,
                base_dir=base_dir,
                kind=kind,
                note=note,
            )
            request = build_file_manifest_request(config, manifest)
        except Exception as exc:
            return _error_plan(action, exc, gate=gate.to_record())
        return {
            "action": ACTION_FILE_TRANSFER,
            "ok": gate.ok,
            "gate": gate.to_record(),
            "confirm_required": "ESTER_READY_FOR_FILE_TRANSFER_MANIFEST",
            "planned": {
                "transfer_id": manifest["transfer_id"],
                "mode": manifest["mode"],
                "file_count": len(manifest["files"]),
                "total_bytes": manifest["total_bytes"],
                "cooldown_sec": operator_policy.file_transfer_cooldown_sec,
                "auto_ingest": False,
                "memory": "off",
            },
            "request": redacted_file_request_summary(request, config),
        }

    return {"action": action, "ok": False, "error": "unknown_operator_action"}


def _send_conversation(
    *,
    env: Mapping[str, str],
    confirm: str,
    config: Any,
    topic: str,
    operator_store: Any,
    conversation_store: Any,
    policy: Any,
    send_prepared_request: Any,
) -> dict[str, Any]:
    from modules.synaps import ACTION_CONVERSATION, build_conversation_turn_request, validate_conversation_send_gate

    problems = validate_conversation_send_gate(env, confirm, conversation_store, policy)
    if problems:
        return {"ok": False, "status": 0, "body": {"error": "send_gate_failed", "problems": problems}}

    open_record = conversation_store.open_window(policy, topic)
    window_id = str(open_record["window_id"])
    request = build_conversation_turn_request(config, policy, window_id=window_id, content=topic, message_index=1)
    conversation_store.record_turn(
        window_id,
        direction="outbound",
        message_index=1,
        content=topic,
        status="prepared",
        policy=policy,
    )
    result = send_prepared_request(request)
    status = int(result.get("status") or 0)
    conversation_store.record_turn(
        window_id,
        direction="inbound",
        message_index=2,
        content=_result_content(result),
        status=str(status),
        policy=policy,
        extra={"ok": bool(result.get("ok"))},
    )
    close_reason = "single_turn_complete" if result.get("ok") else ("send_failed_no_http" if status == 0 else "send_failed_http")
    conversation_store.close_window(window_id, close_reason, policy, message_count=2)
    operator_store.record_action_result(
        action=ACTION_CONVERSATION,
        action_id=window_id,
        ok=bool(result.get("ok")),
        status=status,
        summary={"window_id": window_id, "message_count": 2, "memory": "off", "files": "manifest_only"},
    )
    return {"ok": bool(result.get("ok")), "status": status, "body": result.get("body", {}), "window_id": window_id}


def _send_file_transfer(
    *,
    env: Mapping[str, str],
    confirm: str,
    config: Any,
    files: list[str],
    base_dir: str | None,
    kind: str,
    note: str,
    include_payload: bool,
    operator_store: Any,
    operator_policy: Any,
    file_policy: Any,
    send_prepared_request: Any,
) -> dict[str, Any]:
    from modules.synaps import (
        ACTION_FILE_TRANSFER,
        build_file_manifest,
        build_file_manifest_request,
        validate_file_transfer_send_gate,
    )

    file_gate = operator_store.can_run_file_transfer(operator_policy)
    problems = validate_file_transfer_send_gate(env, confirm)
    if not file_gate.ok:
        problems.extend(file_gate.problems)
    if problems:
        return {"ok": False, "status": 0, "body": {"error": "send_gate_failed", "problems": problems}}

    manifest = build_file_manifest(
        files,
        file_policy,
        include_payload=include_payload,
        base_dir=base_dir,
        kind=kind,
        note=note,
    )
    request = build_file_manifest_request(config, manifest)
    result = send_prepared_request(request)
    status = int(result.get("status") or 0)
    operator_store.record_action_result(
        action=ACTION_FILE_TRANSFER,
        action_id=str(manifest.get("transfer_id") or ""),
        ok=bool(result.get("ok")),
        status=status,
        summary={
            "transfer_id": str(manifest.get("transfer_id") or ""),
            "mode": str(manifest.get("mode") or ""),
            "file_count": len(manifest.get("files") or []),
            "total_bytes": int(manifest.get("total_bytes") or 0),
            "auto_ingest": False,
            "memory": "off",
        },
    )
    return {
        "ok": bool(result.get("ok")),
        "status": status,
        "body": result.get("body", {}),
        "transfer_id": str(manifest.get("transfer_id") or ""),
    }


def _default_topic() -> str:
    from modules.synaps import DEFAULT_WINDOW_TOPIC

    return DEFAULT_WINDOW_TOPIC


def _error_plan(action: str, exc: Exception, gate: Mapping[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "action": action,
        "ok": False,
        "error": exc.__class__.__name__,
        "message": str(exc),
    }
    if gate is not None:
        out["gate"] = dict(gate)
    return out


def _result_content(result: Mapping[str, Any]) -> str:
    body = result.get("body")
    if isinstance(body, Mapping):
        content = body.get("content")
        if content:
            return str(content)
        return json.dumps(dict(body), ensure_ascii=False, sort_keys=True)
    return str(body or "")


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
