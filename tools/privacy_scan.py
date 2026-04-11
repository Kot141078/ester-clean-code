from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON_OUT = REPO_ROOT / "artifacts" / "reports" / "privacy_scan_report.json"
DEFAULT_MD_OUT = REPO_ROOT / "artifacts" / "reports" / "privacy_scan_report.md"

ALLOWED_SYNTHETIC_ROOTS = ("tests/fixtures/", "docs/examples/")
FORBIDDEN_ROOT_RUNTIME = {
    ".ester_env_state.json",
    "qa.json",
    "resp.json",
    "dod_status.json",
    "net_search_log_dump.json",
}
CRITICAL_PATH_DIR_PARTS = {
    "logs",
    "state",
    "data",
    "vstore",
    "chroma",
    "telegram_files",
    "patch_backups",
    "out_log",
}
CRITICAL_SUFFIXES = (
    ".jsonl",
    ".log",
    ".sqlite",
    ".sqlite3",
    ".db",
    ".token",
    ".pem",
    ".p12",
    ".key",
)
REVIEW_NAME_TERMS = (
    "persist_dir",
    "session",
    "state",
    "history",
    "transcript",
    "contexts",
    "debug",
    "response",
    "dump",
    "memory",
    "chat",
)
TEXT_SUFFIX_ALLOWLIST = {
    "",
    ".py",
    ".ps1",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".cfg",
    ".ini",
    ".toml",
    ".sh",
    ".bat",
    ".cmd",
    ".js",
    ".ts",
    ".tsx",
    ".html",
    ".css",
    ".csv",
    ".tsv",
}
PLACEHOLDER_MARKERS = (
    "placeholder",
    "redacted",
    "dummy",
    "example",
    "sample",
    "test",
    "<user>",
    "<path>",
    "<repo-root>",
    "<restore-root>",
    "<dump-dir>",
    "<lan-share>",
    "<data-root>",
    "<game-dir>",
    "<archive-path>",
    "<installer-source>",
    "%userprofile%",
    "%ester_home%",
    "$home",
    "$env:ester_home",
)
PATTERN_TOOL_ALLOWLIST = {
    "tools/privacy_scan.py",
    "tools/r8_secret_scan.py",
    "tools/scan_repo.ps1",
    "tools/write_public_docs.py",
}


@dataclass
class Finding:
    path: str
    rule_id: str
    severity: str
    note: str


def _git_ls_files(root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        text=False,
        check=True,
    )
    raw = proc.stdout.decode("utf-8", errors="replace")
    return [item for item in raw.split("\x00") if item]


def _is_allowed_synthetic(relpath: str) -> bool:
    rel = relpath.replace("\\", "/")
    return any(rel.startswith(prefix) for prefix in ALLOWED_SYNTHETIC_ROOTS)


def _looks_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIX_ALLOWLIST


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _add_finding(
    findings: list[Finding],
    seen: set[tuple[str, str]],
    *,
    path: str,
    rule_id: str,
    severity: str,
    note: str,
) -> None:
    key = (path, rule_id)
    if key in seen:
        return
    seen.add(key)
    findings.append(Finding(path=path, rule_id=rule_id, severity=severity, note=note))


def _scan_path_rules(relpath: str, findings: list[Finding], seen: set[tuple[str, str]]) -> None:
    rel = relpath.replace("\\", "/")
    basename = Path(rel).name
    parts = {part.lower() for part in Path(rel).parts}
    is_synthetic = _is_allowed_synthetic(rel)

    if basename in FORBIDDEN_ROOT_RUNTIME and not is_synthetic:
        _add_finding(
            findings,
            seen,
            path=rel,
            rule_id="critical_root_runtime_artifact",
            severity="CRITICAL",
            note="tracked runtime/debug artifact in public tree",
        )

    if any(part in CRITICAL_PATH_DIR_PARTS for part in parts) and not is_synthetic:
        _add_finding(
            findings,
            seen,
            path=rel,
            rule_id="critical_runtime_directory",
            severity="CRITICAL",
            note="tracked file under runtime/private directory",
        )

    if Path(rel).suffix.lower() in CRITICAL_SUFFIXES and not is_synthetic:
        _add_finding(
            findings,
            seen,
            path=rel,
            rule_id="critical_sensitive_suffix",
            severity="CRITICAL",
            note="tracked file uses blocked runtime/secret suffix",
        )

    basename_low = basename.lower()
    suffix_low = Path(rel).suffix.lower()
    if suffix_low in {".json", ".md", ".txt", ".csv", ".tsv", ".html"}:
        for term in REVIEW_NAME_TERMS:
            if term in basename_low:
                _add_finding(
                    findings,
                    seen,
                    path=rel,
                    rule_id=f"review_name_{term}",
                    severity="REVIEW",
                    note="filename contains review-term",
                )


def _scan_content_rules(relpath: str, text: str, findings: list[Finding], seen: set[tuple[str, str]]) -> None:
    rel = relpath.replace("\\", "/")
    is_synthetic = _is_allowed_synthetic(rel)
    is_pattern_tool = rel in PATTERN_TOOL_ALLOWLIST

    for line in text.splitlines():
        low = line.casefold()

        if ("begin private key" in low) and not is_pattern_tool:
            _add_finding(findings, seen, path=rel, rule_id="critical_private_key_pem", severity="CRITICAL", note="private key marker detected")
        if ("openssh private key" in low) and not is_pattern_tool:
            _add_finding(findings, seen, path=rel, rule_id="critical_private_key_openssh", severity="CRITICAL", note="private key marker detected")
        if re.search(r"(?i)\bAuthorization:\s*(?:Bearer|token)\s+(?!\$\{|\$[A-Z_]+|<|JWT\b|token\b)[A-Za-z0-9._=-]{20,}", line):
            _add_finding(findings, seen, path=rel, rule_id="critical_authorization_header", severity="CRITICAL", note="authorization header-like content detected")
        if re.search(r"(?i)\bBearer\s+(?!\$\{|\$[A-Z_]+|<|JWT\b|token\b)[A-Za-z0-9._=-]{20,}", line):
            _add_finding(findings, seen, path=rel, rule_id="critical_bearer_token", severity="CRITICAL", note="bearer token-like content detected")
        if re.search(r"(?i)\bcookie\s*=\s*(?!\$\{|\$[A-Z_]+|<)[A-Za-z0-9._%=-]{20,}", line):
            _add_finding(findings, seen, path=rel, rule_id="critical_cookie_assignment", severity="CRITICAL", note="cookie-like content detected")
        if re.search(r"(?i)\bx-api-key\s*:\s*(?!\$\{|\$[A-Z_]+|<)[A-Za-z0-9._=-]{16,}", line):
            _add_finding(findings, seen, path=rel, rule_id="critical_x_api_key", severity="CRITICAL", note="x-api-key header-like content detected")
        if re.search(r"(?i)\bapi[_-]?key\b\s*[:=]\s*[\"'](?!placeholder|redacted|dummy|example|sample|test|changeme|lm-studio)[A-Za-z0-9_\-]{16,}[\"']", line):
            _add_finding(findings, seen, path=rel, rule_id="critical_api_key_assignment", severity="CRITICAL", note="api_key-like assignment detected")
        if re.search(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b", line):
            _add_finding(findings, seen, path=rel, rule_id="critical_telegram_token", severity="CRITICAL", note="telegram token-like content detected")
        if re.search(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", line):
            _add_finding(findings, seen, path=rel, rule_id="critical_github_token", severity="CRITICAL", note="github token-like content detected")
        if re.search(r"\bsk-[A-Za-z0-9]{20,}\b", line):
            _add_finding(findings, seen, path=rel, rule_id="critical_openai_token", severity="CRITICAL", note="openai-style token-like content detected")
        if re.search(r"\bAIza[0-9A-Za-z\-_]{20,}\b", line):
            _add_finding(findings, seen, path=rel, rule_id="critical_google_api_key", severity="CRITICAL", note="google api key-like content detected")

        path_match = (
            re.search(r"(?i)C:\\Users\\(?!user\\|username\\|yourname\\|example\\|<user>)[^\\\r\n\"']+\\", line)
            or re.search(r"(?i)C:\\(?:Ester|ester)\\[^\r\n\"']+", line)
            or re.search(
                r"(?i)[DEZ]:\\[^\r\n\"']*(?:ester|dump|bundle|vm|iso|launcher|chrome|data|repo|backup|state|release|tools|logs|lan|game)[^\r\n\"']*",
                line,
            )
            or re.search(r"(?i)/mnt/[a-z]/", line)
            or re.search(r"(?i)/home/(?!user/|%u/|<user>/|example/)[^/\r\n\"']+/", line)
            or re.search(r"(?i)/Users/(?!Shared/|example/|<user>/)[^/\r\n\"']+/", line)
        )
        regex_like = ("re.search(" in line) or ("Regex =" in line) or ("regex =" in line)
        if path_match and not is_pattern_tool and not regex_like:
            placeholder_safe = is_synthetic and any(marker in low for marker in PLACEHOLDER_MARKERS)
            if not placeholder_safe:
                _add_finding(
                    findings,
                    seen,
                    path=rel,
                    rule_id="critical_local_absolute_path",
                    severity="CRITICAL",
                    note="local absolute path detected",
                )


def build_report(root: Path) -> dict[str, object]:
    findings: list[Finding] = []
    seen: set[tuple[str, str]] = set()

    tracked = _git_ls_files(root)
    for relpath in tracked:
        rel = relpath.replace("\\", "/")
        path = root / relpath
        _scan_path_rules(rel, findings, seen)
        if not path.exists() or not path.is_file() or not _looks_text_file(path):
            continue
        text = _read_text(path)
        if not text:
            continue
        _scan_content_rules(rel, text, findings, seen)

    findings.sort(key=lambda item: (item.severity, item.path, item.rule_id))
    counts = {"CRITICAL": 0, "REVIEW": 0, "INFO": 0}
    for item in findings:
        counts[item.severity] = counts.get(item.severity, 0) + 1

    return {
        "ok": counts.get("CRITICAL", 0) == 0,
        "tracked_files_scanned": len(tracked),
        "counts": counts,
        "findings": [asdict(item) for item in findings],
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    counts = dict(payload.get("counts") or {})
    findings = list(payload.get("findings") or [])

    lines = [
        "# Privacy Scan Report",
        "",
        f"- OK: `{bool(payload.get('ok'))}`",
        f"- Tracked files scanned: `{int(payload.get('tracked_files_scanned') or 0)}`",
        f"- CRITICAL: `{int(counts.get('CRITICAL') or 0)}`",
        f"- REVIEW: `{int(counts.get('REVIEW') or 0)}`",
        f"- INFO: `{int(counts.get('INFO') or 0)}`",
        "",
        "## Findings",
        "",
    ]

    if not findings:
        lines.append("- none")
    else:
        for item in findings:
            lines.append(
                f"- `{item.get('severity')}` `{item.get('rule_id')}` `{item.get('path')}`"
                f" — {item.get('note')}"
            )

    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scan tracked files for privacy/runtime leaks.")
    ap.add_argument("--json-out", default=str(DEFAULT_JSON_OUT), help="JSON report path.")
    ap.add_argument("--md-out", default=str(DEFAULT_MD_OUT), help="Markdown report path.")
    args = ap.parse_args(list(argv) if argv is not None else None)

    payload = build_report(REPO_ROOT)
    _write_json(Path(args.json_out), payload)
    _write_markdown(Path(args.md_out), payload)

    print(
        json.dumps(
            {
                "ok": payload.get("ok"),
                "tracked_files_scanned": payload.get("tracked_files_scanned"),
                "counts": payload.get("counts"),
                "json_out": str(Path(args.json_out)),
                "md_out": str(Path(args.md_out)),
            },
            ensure_ascii=True,
        )
    )
    return 0 if bool(payload.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
