"""Fail-closed local Codex bridge daemon.

The daemon coordinates SYNAPS Codex handoffs without giving runtime a raw
shell. It can promote validated mailbox files, turn promoted handoffs into
bounded Codex requests, and optionally run a local `codex exec` worker.
Everything is gated by explicit env flags plus a confirm phrase.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .codex_request import (
    DEFAULT_CODEX_REQUEST_ROOT,
    REQUEST_STATUS_QUEUED,
    CodexRequestPolicy,
    CodexRequestStore,
)
from .mailbox import (
    CODEX_MAILBOX_CONFIRM_PHRASE,
    DEFAULT_CODEX_INBOX_ROOT,
    DEFAULT_CODEX_RECEIPT_LEDGER,
    inspect_codex_mailbox_transfer,
    list_codex_mailbox_transfers,
    promote_codex_mailbox_transfer,
)
from .protocol import SynapsValidationError


CODEX_DAEMON_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_DAEMON_RUN"
CODEX_DAEMON_BASELINE_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_DAEMON_BASELINE"
CODEX_DAEMON_EVENT_SCHEMA = "ester.synaps.codex_daemon_event.v1"
DEFAULT_CODEX_DAEMON_ROOT = Path("data") / "synaps" / "codex_bridge" / "daemon"
DEFAULT_CODEX_DAEMON_LEDGER = DEFAULT_CODEX_DAEMON_ROOT / "events.jsonl"

_TASK_KINDS = {"codex_contract", "codex_handoff"}


@dataclass(frozen=True)
class CodexDaemonPolicy:
    poll_interval_sec: int = 30
    max_promotions_per_cycle: int = 5
    max_requests_per_cycle: int = 1
    runner_timeout_sec: int = 900
    max_task_chars: int = 3000
    max_output_chars: int = 3000
    workdir: str = "."
    codex_command: str = "codex"
    sandbox: str = "workspace-write"
    model: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CodexDaemonPolicy":
        source = os.environ if env is None else env
        return cls(
            poll_interval_sec=_bounded_int(source.get("SYNAPS_CODEX_DAEMON_POLL_SEC"), 30, 5, 3600),
            max_promotions_per_cycle=_bounded_int(source.get("SYNAPS_CODEX_DAEMON_MAX_PROMOTIONS"), 5, 0, 20),
            max_requests_per_cycle=_bounded_int(source.get("SYNAPS_CODEX_DAEMON_MAX_REQUESTS"), 1, 0, 5),
            runner_timeout_sec=_bounded_int(source.get("SYNAPS_CODEX_DAEMON_TIMEOUT_SEC"), 900, 60, 7200),
            max_task_chars=_bounded_int(source.get("SYNAPS_CODEX_DAEMON_MAX_TASK_CHARS"), 3000, 200, 8000),
            max_output_chars=_bounded_int(source.get("SYNAPS_CODEX_DAEMON_MAX_OUTPUT_CHARS"), 3000, 200, 12000),
            workdir=str(source.get("SYNAPS_CODEX_DAEMON_WORKDIR") or "."),
            codex_command=str(source.get("SYNAPS_CODEX_COMMAND") or "codex"),
            sandbox=str(source.get("SYNAPS_CODEX_DAEMON_SANDBOX") or "workspace-write"),
            model=str(source.get("SYNAPS_CODEX_DAEMON_MODEL") or ""),
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def codex_daemon_arm_status(env: Mapping[str, str]) -> dict[str, bool]:
    return {
        "daemon": _env_bool(env.get("SYNAPS_CODEX_DAEMON", "0")),
        "armed": _env_bool(env.get("SYNAPS_CODEX_DAEMON_ARMED", "0")),
        "promote_mailbox": _env_bool(env.get("SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX", "0")),
        "enqueue_handoffs": _env_bool(env.get("SYNAPS_CODEX_DAEMON_ENQUEUE_HANDOFFS", "0")),
        "runner": _env_bool(env.get("SYNAPS_CODEX_DAEMON_RUNNER", "0")),
        "kill_switch": _env_bool(env.get("SYNAPS_CODEX_DAEMON_KILL_SWITCH", "0"))
        or _env_bool(env.get("CODEX_DAEMON_KILL_SWITCH", "0")),
        "legacy_autochat": _env_bool(env.get("SISTER_AUTOCHAT", "0")),
    }


def validate_codex_daemon_gate(
    env: Mapping[str, str],
    confirm: str,
    expected_confirm: str = CODEX_DAEMON_CONFIRM_PHRASE,
) -> list[str]:
    status = codex_daemon_arm_status(env)
    problems: list[str] = []
    if confirm != expected_confirm:
        problems.append("missing_confirm_phrase")
    if not status["daemon"]:
        problems.append("SYNAPS_CODEX_DAEMON_not_enabled")
    if not status["armed"]:
        problems.append("SYNAPS_CODEX_DAEMON_ARMED_not_enabled")
    if status["kill_switch"]:
        problems.append("SYNAPS_CODEX_DAEMON_KILL_SWITCH_enabled")
    if status["legacy_autochat"]:
        problems.append("SISTER_AUTOCHAT_must_remain_disabled")
    return problems


class CodexDaemon:
    def __init__(
        self,
        *,
        daemon_root: str | Path = DEFAULT_CODEX_DAEMON_ROOT,
        quarantine_root: str | Path = Path("data") / "synaps" / "quarantine",
        inbox_root: str | Path = DEFAULT_CODEX_INBOX_ROOT,
        receipt_ledger: str | Path = DEFAULT_CODEX_RECEIPT_LEDGER,
        request_root: str | Path = DEFAULT_CODEX_REQUEST_ROOT,
        policy: CodexDaemonPolicy | None = None,
    ) -> None:
        self.root = Path(daemon_root)
        self.quarantine_root = Path(quarantine_root)
        self.inbox_root = Path(inbox_root)
        self.receipt_ledger = Path(receipt_ledger)
        self.request_root = Path(request_root)
        self.policy = policy or CodexDaemonPolicy()
        self.ledger = self.root / "events.jsonl"
        self.request_store = CodexRequestStore(self.request_root, CodexRequestPolicy(max_task_chars=self.policy.max_task_chars))

    def cycle(self, *, env: Mapping[str, str], apply: bool = False, confirm: str = "", operator: str = "codex-daemon") -> dict[str, Any]:
        status = codex_daemon_arm_status(env)
        output: dict[str, Any] = {
            "ok": True,
            "dry_run": not apply,
            "confirm_required": CODEX_DAEMON_CONFIRM_PHRASE,
            "arm_status": status,
            "policy": self.policy.to_record(),
            "actions": [],
            "auto_ingest": False,
            "memory": "off",
        }
        if apply:
            problems = validate_codex_daemon_gate(env, confirm)
            if problems:
                output["ok"] = False
                output["result"] = {"ok": False, "error": "daemon_gate_failed", "problems": problems}
                return output

        if status["promote_mailbox"]:
            output["actions"].extend(self._promote_ready_mailbox(apply=apply, operator=operator))
        if status["enqueue_handoffs"]:
            output["actions"].extend(self._enqueue_promoted_handoffs(apply=apply, operator=operator))
        if status["runner"]:
            output["actions"].extend(self._run_queued_requests(apply=apply, operator=operator))

        if apply:
            self._append_event({"event": "cycle", "operator": operator, "action_count": len(output["actions"])})
        return output

    def baseline_existing(
        self,
        *,
        env: Mapping[str, str],
        apply: bool = False,
        confirm: str = "",
        operator: str = "codex-daemon",
    ) -> dict[str, Any]:
        status = codex_daemon_arm_status(env)
        transfers = self._baseline_candidates()
        output: dict[str, Any] = {
            "ok": True,
            "dry_run": not apply,
            "action": "baseline",
            "confirm_required": CODEX_DAEMON_BASELINE_CONFIRM_PHRASE,
            "arm_status": status,
            "count": len(transfers),
            "transfers": transfers,
            "auto_ingest": False,
            "memory": "off",
        }
        if apply:
            problems = validate_codex_daemon_gate(env, confirm, CODEX_DAEMON_BASELINE_CONFIRM_PHRASE)
            if problems:
                output["ok"] = False
                output["result"] = {"ok": False, "error": "daemon_gate_failed", "problems": problems}
                return output
            for transfer in transfers:
                self._mark_handoff_seen(
                    str(transfer["transfer_id"]),
                    operator,
                    {"ok": True, "status": "baseline_existing", "source": transfer["source"]},
                )
            self._append_event({"event": "baseline_existing", "operator": operator, "count": len(transfers)})
            output["result"] = {"ok": True, "status": "baselined", "count": len(transfers)}
        return output

    def _promote_ready_mailbox(self, *, apply: bool, operator: str) -> list[dict[str, Any]]:
        listing = list_codex_mailbox_transfers(self.quarantine_root, self.inbox_root)
        actions: list[dict[str, Any]] = []
        for item in listing.get("transfers") or []:
            if len(actions) >= self.policy.max_promotions_per_cycle:
                break
            if not item.get("ok") or item.get("status") != "ready":
                continue
            transfer_id = str(item["transfer_id"])
            action: dict[str, Any] = {"action": "promote_mailbox", "transfer_id": transfer_id, "dry_run": not apply}
            if apply:
                result = promote_codex_mailbox_transfer(
                    transfer_id,
                    self.quarantine_root,
                    self.inbox_root,
                    self.receipt_ledger,
                    apply=True,
                    confirm=CODEX_MAILBOX_CONFIRM_PHRASE,
                    operator=operator,
                )
                action["result"] = _compact_result(result)
                self._append_event({"event": "mailbox_promoted", "transfer_id": transfer_id, "operator": operator})
            actions.append(action)
        return actions

    def _baseline_candidates(self) -> list[dict[str, Any]]:
        candidates: dict[str, dict[str, Any]] = {}
        if self.inbox_root.exists():
            for item in sorted(self.inbox_root.iterdir(), key=lambda entry: entry.name):
                if item.is_dir():
                    candidates[item.name] = {"transfer_id": item.name, "source": "inbox", "seen": self._handoff_seen_path(item.name).exists()}

        listing = list_codex_mailbox_transfers(self.quarantine_root, self.inbox_root)
        for item in listing.get("transfers") or []:
            transfer_id = str(item.get("transfer_id") or "")
            if not transfer_id:
                continue
            if not item.get("ok") or item.get("status") not in {"ready", "already_promoted"}:
                continue
            kinds = set(item.get("kinds") or [])
            if not kinds.intersection(_TASK_KINDS):
                continue
            candidates.setdefault(
                transfer_id,
                {"transfer_id": transfer_id, "source": "quarantine", "seen": self._handoff_seen_path(transfer_id).exists()},
            )
        return [item for item in sorted(candidates.values(), key=lambda row: str(row["transfer_id"])) if not item["seen"]]

    def _enqueue_promoted_handoffs(self, *, apply: bool, operator: str) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        if not self.inbox_root.exists():
            return actions
        for transfer_dir in sorted(self.inbox_root.iterdir(), key=lambda entry: entry.name):
            if len(actions) >= self.policy.max_requests_per_cycle:
                break
            if not transfer_dir.is_dir() or self._handoff_seen_path(transfer_dir.name).exists():
                continue
            try:
                inspection = inspect_codex_mailbox_transfer(transfer_dir.name, self.quarantine_root, self.inbox_root)
            except Exception:
                continue
            task_files = [
                item for item in inspection.get("files") or []
                if item.get("kind") in _TASK_KINDS and str(item.get("name") or "").lower().endswith((".md", ".txt", ".json"))
            ]
            if not task_files:
                continue
            request_id = f"codex-bridge-{transfer_dir.name}"
            task = self._request_task_for_transfer(transfer_dir.name, task_files)
            action: dict[str, Any] = {
                "action": "enqueue_handoff",
                "transfer_id": transfer_dir.name,
                "request_id": request_id,
                "dry_run": not apply,
            }
            if apply:
                record = self.request_store.build_request(
                    request_id=request_id,
                    title=f"SYNAPS handoff {transfer_dir.name}",
                    task=task,
                    requester="synaps_mailbox",
                    origin="codex_daemon",
                    priority="normal",
                    tags=["synaps", "codex-daemon"],
                    related_transfer_ids=[transfer_dir.name],
                )
                try:
                    result = self.request_store.create_request(record)
                    action["result"] = {"ok": True, "status": result["status"]}
                except Exception as exc:
                    action["result"] = {"ok": False, "error": exc.__class__.__name__, "message": str(exc)}
                self._mark_handoff_seen(transfer_dir.name, operator, action["result"])
                self._append_event({"event": "handoff_enqueued", "transfer_id": transfer_dir.name, "request_id": request_id})
            actions.append(action)
        return actions

    def _run_queued_requests(self, *, apply: bool, operator: str) -> list[dict[str, Any]]:
        listing = self.request_store.list_requests(status=REQUEST_STATUS_QUEUED)
        actions: list[dict[str, Any]] = []
        for item in listing.get("requests") or []:
            if len(actions) >= self.policy.max_requests_per_cycle:
                break
            request_id = str(item.get("request_id") or "")
            action: dict[str, Any] = {"action": "run_request", "request_id": request_id, "dry_run": not apply}
            if apply:
                action["result"] = self._run_request(request_id, operator=operator)
            actions.append(action)
        return actions

    def _run_request(self, request_id: str, *, operator: str) -> dict[str, Any]:
        lease_dir = self._lease_dir(request_id)
        try:
            lease_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            return {"ok": False, "status": "leased"}

        run_dir = self.root / "runs" / request_id / _timestamp_slug()
        run_dir.mkdir(parents=True, exist_ok=True)
        try:
            request = self.request_store.inspect_request(request_id)["request"]
            self.request_store.claim_request(request_id, operator=operator)
            prompt_path = run_dir / "prompt.md"
            output_path = run_dir / "last_message.md"
            prompt_path.write_text(self._build_prompt(request), encoding="utf-8")
            result = self._run_codex(prompt_path, output_path, run_dir)
            summary = _preview(result.get("last_message") or result.get("stderr") or result.get("stdout") or "no output", self.policy.max_output_chars)
            final_status = "completed" if result["returncode"] == 0 else "blocked"
            self.request_store.complete_request(request_id, operator=operator, summary=summary, status=final_status)
            (run_dir / "run.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            self._append_event({"event": "request_ran", "request_id": request_id, "returncode": result["returncode"], "status": final_status})
            return {"ok": result["returncode"] == 0, "status": final_status, "run_dir": str(run_dir), "returncode": result["returncode"]}
        except Exception as exc:
            self._append_event({"event": "request_run_failed", "request_id": request_id, "error": exc.__class__.__name__})
            return {"ok": False, "status": "blocked", "error": exc.__class__.__name__, "message": str(exc)}
        finally:
            (lease_dir / "released.json").write_text(json.dumps({"released_at": _iso_now()}, sort_keys=True), encoding="utf-8")

    def _run_codex(self, prompt_path: Path, output_path: Path, run_dir: Path) -> dict[str, Any]:
        command_prefix = shlex.split(self.policy.codex_command, posix=(os.name != "nt"))
        command = command_prefix + [
            "exec",
            "--cd",
            str(Path(self.policy.workdir).resolve()),
            "--sandbox",
            self.policy.sandbox,
            "--ask-for-approval",
            "never",
            "--output-last-message",
            str(output_path),
            "-",
        ]
        if self.policy.model:
            command[len(command_prefix) + 1:len(command_prefix) + 1] = ["--model", self.policy.model]
        proc = subprocess.run(
            command,
            input=prompt_path.read_text(encoding="utf-8"),
            capture_output=True,
            text=True,
            timeout=self.policy.runner_timeout_sec,
            cwd=str(Path(self.policy.workdir).resolve()),
        )
        stdout = _redact(_preview(proc.stdout, self.policy.max_output_chars))
        stderr = _redact(_preview(proc.stderr, self.policy.max_output_chars))
        last_message = ""
        if output_path.is_file():
            last_message = _redact(_preview(output_path.read_text(encoding="utf-8", errors="replace"), self.policy.max_output_chars))
        (run_dir / "stdout.txt").write_text(stdout, encoding="utf-8")
        (run_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
        return {"ok": proc.returncode == 0, "returncode": proc.returncode, "stdout": stdout, "stderr": stderr, "last_message": last_message}

    def _build_prompt(self, request: Mapping[str, Any]) -> str:
        return "\n".join(
            [
                "You are a local Codex worker in the SYNAPS family coordination mesh.",
                "Complete the bounded request below and write a concise final report.",
                "Hard constraints: do not expose secrets; do not edit .env; do not touch memory/passport/vector/chroma/RAG; do not run live SYNAPS sends, scheduler, hourly, or autochat unless the request explicitly includes a matching approved gate.",
                "Use dry-run and tests first. If blocked, report the blocker and stop.",
                "",
                f"Request id: {request.get('request_id')}",
                f"Title: {request.get('title')}",
                f"Related transfers: {', '.join(request.get('related_transfer_ids') or [])}",
                "",
                "Task:",
                str(request.get("task") or ""),
            ]
        )

    def _request_task_for_transfer(self, transfer_id: str, task_files: Sequence[Mapping[str, Any]]) -> str:
        file_lines = [f"- {item.get('path')}" for item in task_files]
        return "\n".join(
            [
                f"Inspect promoted SYNAPS Codex handoff transfer {transfer_id}.",
                "Follow the handoff instructions in these local inbox/quarantine files:",
                *file_lines,
                "Do not execute arbitrary patches blindly; inspect, apply only safe code changes, run tests, and report back.",
            ]
        )

    def _handoff_seen_path(self, transfer_id: str) -> Path:
        return self.root / "inbox_seen" / f"{_safe_identifier(transfer_id)}.json"

    def _mark_handoff_seen(self, transfer_id: str, operator: str, result: Mapping[str, Any]) -> None:
        path = self._handoff_seen_path(transfer_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"transfer_id": transfer_id, "operator": operator, "result": dict(result), "created_at": _iso_now()}, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _lease_dir(self, request_id: str) -> Path:
        return self.root / "leases" / _safe_identifier(request_id)

    def _append_event(self, event: Mapping[str, Any]) -> None:
        record = {"schema": CODEX_DAEMON_EVENT_SCHEMA, "created_at": _iso_now(), "auto_ingest": False, "memory": "off", **dict(event)}
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _compact_result(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(result.get("ok")),
        "dry_run": bool(result.get("dry_run")),
        "status": (result.get("result") or {}).get("status") if isinstance(result.get("result"), Mapping) else None,
    }


def _bounded_int(raw: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(raw if raw is not None else default).strip())
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _env_bool(raw: str) -> bool:
    return str(raw or "0").strip().lower() in {"1", "true", "yes", "on", "y", "enabled"}


def _safe_identifier(raw: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(raw or "").strip())
    safe = safe.strip("-_")
    if not safe:
        raise SynapsValidationError("identifier is required")
    return safe[:120]


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _preview(text: str, limit: int) -> str:
    return str(text or "")[:limit]


def _redact(text: str) -> str:
    redacted = str(text or "")
    for marker in ("OPENAI_API_KEY=", "SISTER_SYNC_TOKEN=", "Authorization: Bearer ", "authorization: bearer "):
        lower = redacted.lower()
        start = lower.find(marker.lower())
        while start >= 0:
            end = redacted.find("\n", start)
            if end < 0:
                end = len(redacted)
            redacted = redacted[:start] + marker + "<redacted>" + redacted[end:]
            lower = redacted.lower()
            start = lower.find(marker.lower(), start + len(marker))
    return redacted
