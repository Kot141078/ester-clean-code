"""Dry-run-first SYNAPS probe tool.

By default this tool only builds and prints a redacted request summary. A real
POST requires the explicit `--send` flag.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, MutableMapping

if TYPE_CHECKING:
    from modules.synaps import SynapsConfig, SynapsMessageType, SynapsPreparedRequest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_CONTENT: dict[str, str] = {
    "health": "synaps health probe",
    "chat": "synaps chat probe",
    "thought_request": "synaps thought probe",
}


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
        if not key:
            continue
        values[key] = _strip_env_value(value)
    return values


def bootstrap_env_from_argv(argv: list[str], environ: MutableMapping[str, str] | None = None) -> None:
    """Load --env-file before imports that install runtime network guards."""
    target = os.environ if environ is None else environ
    for key, value in load_env_file(_env_file_from_argv(argv)).items():
        target.setdefault(key, value)


def merged_env(env_file: str | None = ".env", base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    if env_file:
        for key, value in load_env_file(env_file).items():
            env.setdefault(key, value)
    return env


def build_probe_request(
    config: "SynapsConfig",
    message_type: "SynapsMessageType",
    content: str | None = None,
) -> "SynapsPreparedRequest":
    from modules.synaps import build_envelope, prepare_outbound_request

    message_value = _message_type_value(message_type)
    probe_content = content if content is not None else DEFAULT_CONTENT[message_value]
    envelope = build_envelope(
        config,
        probe_content,
        message_type,
        metadata={"probe": "synaps_probe", "mode": message_value},
    )
    timeout = config.opinion_timeout_sec if message_value == "thought_request" else config.timeout_sec
    return prepare_outbound_request(config, envelope, timeout_sec=timeout)


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


def redacted_send_result(result: Mapping[str, Any], token: str) -> dict[str, Any]:
    return _redact_nested(dict(result), token)


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    bootstrap_env_from_argv(raw_argv)

    from modules.synaps import SynapsMessageType, config_from_env, synaps_health, to_record

    parser = argparse.ArgumentParser(description="Dry-run-first SYNAPS health/chat/thought probe.")
    parser.add_argument(
        "--type",
        choices=[SynapsMessageType.HEALTH.value, SynapsMessageType.CHAT.value, SynapsMessageType.THOUGHT_REQUEST.value],
        default=SynapsMessageType.HEALTH.value,
        help="Probe payload type. Default: health.",
    )
    parser.add_argument("--content", default=None, help="Optional probe content.")
    parser.add_argument("--env-file", default=".env", help="Env file to merge if process env misses keys.")
    parser.add_argument("--send", action="store_true", help="Actually POST the probe. Omitted means dry-run only.")
    args = parser.parse_args(raw_argv)

    env = merged_env(args.env_file)
    config = config_from_env(env)
    message_type = SynapsMessageType(args.type)
    try:
        request = build_probe_request(config, message_type, content=args.content)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "dry_run": not args.send,
                    "error": exc.__class__.__name__,
                    "message": str(exc),
                    "synaps_health": to_record(synaps_health(config)),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    output: dict[str, Any] = {
        "ok": True,
        "dry_run": not args.send,
        "request": redacted_request_summary(request, config),
    }
    if args.send:
        output["result"] = redacted_send_result(send_prepared_request(request), config.sync_token)

    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _strip_env_value(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1]
    return stripped


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


def _env_file_from_argv(argv: list[str]) -> str:
    for index, item in enumerate(argv):
        if item == "--env-file" and index + 1 < len(argv):
            return argv[index + 1]
        if item.startswith("--env-file="):
            return item.split("=", 1)[1]
    return ".env"


def _message_type_value(message_type: "SynapsMessageType") -> str:
    return str(getattr(message_type, "value", message_type))


if __name__ == "__main__":
    sys.exit(main())
