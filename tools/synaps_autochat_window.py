"""Dry-run-first operator window for one SYNAPS sister autochat turn.

This tool is not a background loop. A real POST requires:

- `--send`
- `--confirm ESTER_READY_FOR_AUTOCHAT_ONESHOT_WINDOW`
- effective env: SISTER_AUTOCHAT=1, SISTER_AUTOCHAT_ARMED=1,
  SISTER_AUTOCHAT_ONESHOT=1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping, MutableMapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CONFIRM_PHRASE = "ESTER_READY_FOR_AUTOCHAT_ONESHOT_WINDOW"
DEFAULT_CONTENT = (
    "One-shot sister autochat window. Reply with two short grounded sentences "
    "about current SYNAPS readiness; do not include private data."
)


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


def build_window_request(config: "SynapsConfig", content: str = DEFAULT_CONTENT) -> "SynapsPreparedRequest":
    from modules.synaps import SynapsMessageType, build_envelope, prepare_outbound_request

    envelope = build_envelope(
        config,
        content,
        SynapsMessageType.THOUGHT_REQUEST,
        metadata={
            "autochat_window": "oneshot",
            "memory": "off",
            "mode": "autochat_oneshot",
            "operator_window": True,
        },
    )
    return prepare_outbound_request(config, envelope, timeout_sec=config.opinion_timeout_sec)


def redacted_request_summary(request: "SynapsPreparedRequest", config: "SynapsConfig") -> dict[str, Any]:
    from modules.synaps import synaps_health, to_record

    payload = dict(request.json)
    if "token" in payload:
        payload["token"] = _redacted_token(config.sync_token)
    return {
        "url": request.url,
        "timeout_sec": request.timeout_sec,
        "headers": dict(request.headers),
        "json": payload,
        "synaps_health": to_record(synaps_health(config)),
    }


def send_prepared_request(request: "SynapsPreparedRequest") -> dict[str, Any]:
    data = json.dumps(request.json).encode("utf-8")
    http_request = urllib.request.Request(
        request.url,
        data=data,
        headers=request.headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(http_request, timeout=request.timeout_sec) as response:
            body = response.read(4096).decode("utf-8", errors="replace")
            return {
                "ok": 200 <= int(response.status) < 300,
                "status": int(response.status),
                "body": _parse_json_body(body),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(4096).decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status": int(exc.code),
            "body": _parse_json_body(body),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": 0,
            "body": {"error": exc.__class__.__name__},
        }


def arm_status(env: Mapping[str, str]) -> dict[str, bool]:
    return {
        "autochat": _env_bool(env.get("SISTER_AUTOCHAT", "0")),
        "armed": _env_bool(env.get("SISTER_AUTOCHAT_ARMED", "0")),
        "oneshot": _env_bool(env.get("SISTER_AUTOCHAT_ONESHOT", "0")),
    }


def validate_send_gate(env: Mapping[str, str], confirm: str) -> list[str]:
    problems: list[str] = []
    status = arm_status(env)
    if confirm != CONFIRM_PHRASE:
        problems.append("missing_confirm_phrase")
    if not status["autochat"]:
        problems.append("SISTER_AUTOCHAT_not_enabled")
    if not status["armed"]:
        problems.append("SISTER_AUTOCHAT_ARMED_not_enabled")
    if not status["oneshot"]:
        problems.append("SISTER_AUTOCHAT_ONESHOT_not_enabled")
    return problems


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    bootstrap_env_from_argv(raw_argv)

    from modules.synaps import config_from_env, synaps_health, to_record

    parser = argparse.ArgumentParser(description="Dry-run-first one-shot SYNAPS sister autochat window.")
    parser.add_argument("--content", default=DEFAULT_CONTENT, help="Bounded one-shot prompt.")
    parser.add_argument("--env-file", default=".env", help="Env file to merge if process env misses keys.")
    parser.add_argument("--send", action="store_true", help="Actually POST the one-shot window request.")
    parser.add_argument("--confirm", default="", help=f"Required for --send: {CONFIRM_PHRASE}")
    args = parser.parse_args(raw_argv)

    env = merged_env(args.env_file)
    config = config_from_env(env)
    status = arm_status(env)
    try:
        request = build_window_request(config, content=args.content)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "dry_run": not args.send,
                    "error": exc.__class__.__name__,
                    "message": str(exc),
                    "arm_status": status,
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
        "confirm_required": CONFIRM_PHRASE,
        "request": redacted_request_summary(request, config),
    }
    if args.send:
        problems = validate_send_gate(env, args.confirm)
        if problems:
            output["ok"] = False
            output["result"] = {"ok": False, "status": 0, "body": {"error": "send_gate_failed", "problems": problems}}
            print(json.dumps(_redact_nested(output, config.sync_token), ensure_ascii=False, indent=2, sort_keys=True))
            return 2
        output["result"] = redacted_send_result(send_prepared_request(request), config.sync_token)

    print(json.dumps(_redact_nested(output, config.sync_token), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def redacted_send_result(result: Mapping[str, Any], token: str) -> dict[str, Any]:
    return _redact_nested(dict(result), token)


def _strip_env_value(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1]
    return stripped


def _env_bool(raw: str) -> bool:
    return str(raw or "0").strip().lower() in {"1", "true", "yes", "on", "y"}


def _env_file_from_argv(argv: list[str]) -> str:
    for index, item in enumerate(argv):
        if item == "--env-file" and index + 1 < len(argv):
            return argv[index + 1]
        if item.startswith("--env-file="):
            return item.split("=", 1)[1]
    return ".env"


def _redacted_token(token: str) -> str:
    from modules.synaps import SynapsConfig, synaps_health, to_record

    if not token:
        return "<missing>"
    return f"<set len={len(token)} sha256_prefix={to_record(synaps_health(SynapsConfig(sync_token=token)))['token_sha256_prefix']}>"


def _parse_json_body(body: str) -> Any:
    try:
        return json.loads(body) if body else {}
    except Exception:
        return {"text": body[:500]}


def _redact_nested(value: Any, token: str) -> Any:
    if isinstance(value, str):
        return value.replace(token, _redacted_token(token)) if token else value
    if isinstance(value, list):
        return [_redact_nested(item, token) for item in value]
    if isinstance(value, tuple):
        return [_redact_nested(item, token) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _redact_nested(item, token) for key, item in value.items()}
    return value


if __name__ == "__main__":
    sys.exit(main())
