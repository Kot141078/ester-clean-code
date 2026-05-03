"""Dry-run-first SYNAPS file/log manifest sender.

Real POST requires:

- `--send`
- `--confirm ESTER_READY_FOR_FILE_TRANSFER_MANIFEST`
- effective env: `SISTER_FILE_TRANSFER=1`, `SISTER_FILE_TRANSFER_ARMED=1`

Inbound peers must quarantine payloads and must not auto-ingest them into
memory, passport, vector, chroma, RAG, or reply context.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping, MutableMapping
from uuid import uuid4

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


def redacted_file_request_summary(request: "SynapsPreparedRequest", config: "SynapsConfig") -> dict[str, Any]:
    from modules.synaps import synaps_health, to_record

    payload = dict(request.json)
    if "token" in payload:
        payload["token"] = _redacted_token(config.sync_token)
    if payload.get("type") == "file_manifest":
        payload["content"] = _redact_manifest_content(str(payload.get("content") or ""))
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

    from modules.synaps import (
        FILE_TRANSFER_CONFIRM_PHRASE,
        FileTransferPolicy,
        build_file_manifest,
        build_file_manifest_request,
        config_from_env,
        file_transfer_arm_status,
        synaps_health,
        to_record,
        validate_file_transfer_send_gate,
    )

    parser = argparse.ArgumentParser(description="Dry-run-first SYNAPS file/log manifest sender.")
    parser.add_argument("--file", action="append", default=[], help="File to include in the manifest. Repeatable.")
    parser.add_argument("--base-dir", default=None, help="Optional base directory for safe relative names.")
    parser.add_argument("--kind", default="file", help="Manifest kind label, e.g. log, report, artifact.")
    parser.add_argument("--note", default="", help="Short operator note for the manifest.")
    parser.add_argument("--env-file", default=".env", help="Env file to merge if process env misses keys.")
    parser.add_argument("--include-payload", action="store_true", help="Embed capped payload for quarantine write.")
    parser.add_argument(
        "--split-files",
        action="store_true",
        help="Send repeated --file inputs as separate single-file manifests.",
    )
    parser.add_argument(
        "--allow-multi-file-envelope",
        action="store_true",
        help="Permit one live envelope with multiple files. Prefer --split-files for sister compatibility.",
    )
    parser.add_argument(
        "--chunk-files",
        action="store_true",
        help="Split one large --file into an index plus payload chunks, then use split-file manifests.",
    )
    parser.add_argument("--chunk-bytes", type=int, default=2048, help="Max bytes per generated chunk.")
    parser.add_argument(
        "--chunk-out-dir",
        default=None,
        help="Directory for generated chunk bundle. Defaults to data/synaps/file_transfer_chunks/outbox/<id>.",
    )
    parser.add_argument("--send", action="store_true", help="Actually POST the manifest.")
    parser.add_argument("--confirm", default="", help=f"Required for --send: {FILE_TRANSFER_CONFIRM_PHRASE}")
    args = parser.parse_args(raw_argv)

    env = merged_env(args.env_file)
    config = config_from_env(env)
    policy = FileTransferPolicy.from_env(env)
    status = file_transfer_arm_status(env)

    try:
        chunked: dict[str, Any] | None = None
        file_paths = list(args.file)
        base_dir = args.base_dir
        split_files = bool(args.split_files)
        include_payload = bool(args.include_payload)
        if args.chunk_files:
            chunked = _prepare_chunk_bundle(
                file_paths,
                base_dir=base_dir,
                out_dir=args.chunk_out_dir,
                chunk_bytes=args.chunk_bytes,
            )
            file_paths = list(chunked["files"])
            base_dir = str(chunked["base_dir"])
            split_files = True
            include_payload = True
        if split_files:
            manifests = [
                build_file_manifest(
                    [file_path],
                    policy,
                    include_payload=include_payload,
                    base_dir=base_dir,
                    kind=args.kind,
                    note=args.note,
                )
                for file_path in file_paths
            ]
        else:
            manifests = [
                build_file_manifest(
                    file_paths,
                    policy,
                    include_payload=include_payload,
                    base_dir=base_dir,
                    kind=args.kind,
                    note=args.note,
                )
            ]
        requests = [build_file_manifest_request(config, manifest) for manifest in manifests]
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
                    "synaps_health": to_record(synaps_health(config)),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    total_files = sum(len(manifest["files"]) for manifest in manifests)
    total_bytes = sum(int(manifest["total_bytes"]) for manifest in manifests)
    transfer_records = [
        {
            "transfer_id": manifest["transfer_id"],
            "mode": manifest["mode"],
            "file_count": len(manifest["files"]),
            "total_bytes": manifest["total_bytes"],
            "auto_ingest": False,
            "memory": "off",
        }
        for manifest in manifests
    ]
    output: dict[str, Any] = {
        "ok": True,
        "dry_run": not args.send,
        "arm_status": status,
        "confirm_required": FILE_TRANSFER_CONFIRM_PHRASE,
        "policy": policy.to_record(),
        "transfer": {
            "transfer_id": manifests[0]["transfer_id"] if len(manifests) == 1 else "",
            "mode": manifests[0]["mode"] if len(manifests) == 1 else "split_single_file_manifests",
            "file_count": total_files,
            "total_bytes": total_bytes,
            "auto_ingest": False,
            "memory": "off",
            "split_files": bool(split_files),
            "manifest_count": len(manifests),
        },
        "chunked": chunked,
        "transfers": transfer_records,
        "request": redacted_file_request_summary(requests[0], config) if len(requests) == 1 else None,
        "requests": [redacted_file_request_summary(request, config) for request in requests],
    }

    if args.send:
        problems = validate_file_transfer_send_gate(env, args.confirm)
        if not split_files and total_files > 1 and not args.allow_multi_file_envelope:
            problems.append("multi_file_envelope_blocked_use_split_files_or_explicit_override")
        if problems:
            output["ok"] = False
            output["result"] = {"ok": False, "status": 0, "body": {"error": "send_gate_failed", "problems": problems}}
            print(json.dumps(redacted_send_result(output, config.sync_token), ensure_ascii=False, indent=2, sort_keys=True))
            return 2
        results = []
        for index, request in enumerate(requests, start=1):
            item = redacted_send_result(send_prepared_request(request), config.sync_token)
            results.append(item)
            if not item.get("ok"):
                output["ok"] = False
                output["results"] = results
                output["result"] = {"ok": False, "failed_index": index, "items": results}
                break
        else:
            output["results"] = results
            output["result"] = (
                results[0] if len(results) == 1 else {"ok": all(item.get("ok") for item in results), "items": results}
            )

    print(json.dumps(redacted_send_result(output, config.sync_token), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output.get("ok") else 2


def _redact_manifest_content(content: str) -> str:
    try:
        manifest = json.loads(content)
    except Exception:
        return "<invalid file manifest>"
    if isinstance(manifest, Mapping):
        clean = dict(manifest)
        files = []
        for item in clean.get("files") or []:
            if isinstance(item, Mapping):
                file_item = dict(item)
                if "payload_b64" in file_item:
                    raw = str(file_item["payload_b64"])
                    file_item["payload_b64"] = f"<redacted base64 len={len(raw)}>"
                files.append(file_item)
        clean["files"] = files
        return json.dumps(clean, ensure_ascii=False, sort_keys=True)
    return "<invalid file manifest>"


def _prepare_chunk_bundle(
    file_paths: list[str],
    *,
    base_dir: str | None,
    out_dir: str | None,
    chunk_bytes: int,
) -> dict[str, Any]:
    if len(file_paths) != 1:
        raise ValueError("chunk-files requires exactly one --file")
    if chunk_bytes < 256 or chunk_bytes > 16 * 1024:
        raise ValueError("chunk-bytes must be between 256 and 16384")

    source = Path(file_paths[0]).resolve()
    if not source.is_file():
        raise FileNotFoundError(source.name)
    relative_name = _safe_relative_chunk_source(source, base_dir)
    transfer_id = f"synaps-chunks-{uuid4()}"
    bundle_dir = Path(out_dir).resolve() if out_dir else REPO_ROOT / "data" / "synaps" / "file_transfer_chunks" / "outbox" / transfer_id
    bundle_dir.mkdir(parents=True, exist_ok=False)
    chunks_dir = bundle_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=False)

    payload = source.read_bytes()
    chunks: list[dict[str, Any]] = []
    chunk_paths: list[str] = []
    total = len(payload)
    count = max(1, (total + chunk_bytes - 1) // chunk_bytes)
    for index in range(count):
        start = index * chunk_bytes
        chunk = payload[start : start + chunk_bytes]
        chunk_name = f"{source.name}.part{index + 1:03d}of{count:03d}"
        chunk_path = chunks_dir / chunk_name
        chunk_path.write_bytes(chunk)
        chunk_paths.append(str(chunk_path))
        chunks.append(
            {
                "index": index + 1,
                "name": f"chunks/{chunk_name}",
                "size": len(chunk),
                "sha256": _sha256_bytes(chunk),
            }
        )

    index_path = bundle_dir / f"{source.name}.chunk-index.json"
    index_record = {
        "schema": "ester.synaps.file_transfer_chunks.v1",
        "transfer_id": transfer_id,
        "source_name": relative_name,
        "source_size": total,
        "source_sha256": _sha256_bytes(payload),
        "chunk_bytes": chunk_bytes,
        "chunk_count": count,
        "chunks": chunks,
        "reconstruct": {
            "ordered_names": [item["name"] for item in chunks],
            "expected_sha256": _sha256_bytes(payload),
            "expected_size": total,
        },
    }
    index_path.write_text(json.dumps(index_record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "schema": index_record["schema"],
        "transfer_id": transfer_id,
        "source_name": relative_name,
        "source_size": total,
        "source_sha256": index_record["source_sha256"],
        "chunk_bytes": chunk_bytes,
        "chunk_count": count,
        "index_name": index_path.name,
        "base_dir": str(bundle_dir),
        "files": [str(index_path), *chunk_paths],
    }


def _safe_relative_chunk_source(source: Path, base_dir: str | None) -> str:
    if base_dir:
        try:
            name = str(source.relative_to(Path(base_dir).resolve()))
        except ValueError:
            name = source.name
    else:
        name = source.name
    safe = name.replace("\\", "/").strip().lstrip("/")
    parts = [part for part in safe.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." or ":" in part for part in parts):
        return source.name
    return "/".join(parts)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


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
