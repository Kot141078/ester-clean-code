from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

import privacy_scan


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPECTED_TAG = "v0.2.5"
DEFAULT_REPORT = REPO_ROOT / "artifacts" / "reports" / "public_release_safety_report.md"
FORBIDDEN_ROOT_FILES = [
    ".ester_env_state.json",
    "qa.json",
    "resp.json",
    "dod_status.json",
    "net_search_log_dump.json",
]


def _git_output(*args: str) -> str:
    proc = subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def _must_exist(relpath: str, problems: list[str]) -> Path:
    path = REPO_ROOT / relpath
    if not path.exists():
        problems.append(f"missing required file: {relpath}")
    return path


def _load_text(relpath: str, problems: list[str]) -> str:
    path = _must_exist(relpath, problems)
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:
        problems.append(f"cannot read {relpath}: {exc}")
        return ""


def _check_privacy(expected_tag: str, problems: list[str], lines: list[str]) -> None:
    payload = privacy_scan.build_report(REPO_ROOT)
    privacy_scan._write_json(REPO_ROOT / "artifacts" / "reports" / "privacy_scan_report.json", payload)
    privacy_scan._write_markdown(REPO_ROOT / "artifacts" / "reports" / "privacy_scan_report.md", payload)

    counts = dict(payload.get("counts") or {})
    lines.extend(
        [
            "## Privacy Scan",
            "",
            f"- OK: `{bool(payload.get('ok'))}`",
            f"- CRITICAL: `{int(counts.get('CRITICAL') or 0)}`",
            f"- REVIEW: `{int(counts.get('REVIEW') or 0)}`",
            "",
        ]
    )
    if not bool(payload.get("ok")):
        problems.append("privacy scan reported CRITICAL findings")


def _check_forbidden_root_files(problems: list[str], lines: list[str]) -> None:
    remaining = [name for name in FORBIDDEN_ROOT_FILES if (REPO_ROOT / name).exists()]
    lines.extend(
        [
            "## Forbidden Root Files",
            "",
            f"- Remaining: `{len(remaining)}`",
        ]
    )
    if remaining:
        for name in remaining:
            lines.append(f"- `{name}`")
        problems.append("forbidden root-level runtime/private artifacts remain tracked in working tree")
    else:
        lines.append("- none")
    lines.append("")


def _check_release_truth(expected_tag: str, problems: list[str], lines: list[str]) -> None:
    changelog = _load_text("CHANGELOG.md", problems)
    version = _load_text("VERSION", problems).strip()
    release_version = _load_text("release/VERSION", problems).strip()
    readme = _load_text("README.md", problems)
    machine_entry = _load_text("MACHINE_ENTRY.md", problems)
    llms = _load_text("llms.txt", problems)
    release_notes_rel = f"docs/RELEASE_NOTES_{expected_tag}.md"
    release_notes = _load_text(release_notes_rel, problems)

    if f"## [{expected_tag[1:]}]" not in changelog:
        problems.append(f"CHANGELOG.md missing entry for {expected_tag}")
    if version != expected_tag:
        problems.append(f"VERSION is not aligned to {expected_tag}")
    if release_version != expected_tag:
        problems.append(f"release/VERSION is not aligned to {expected_tag}")

    stable_refs = {
        "README.md": readme,
        "MACHINE_ENTRY.md": machine_entry,
        "llms.txt": llms,
    }
    for name, text in stable_refs.items():
        if expected_tag not in text:
            problems.append(f"{name} does not reference {expected_tag}")
        if "v0.2.4" in text:
            problems.append(f"{name} still references outdated stable tag v0.2.4")

    if expected_tag not in release_notes:
        problems.append(f"{release_notes_rel} does not mention {expected_tag}")

    lines.extend(
        [
            "## Release Truth",
            "",
            f"- Expected tag: `{expected_tag}`",
            f"- VERSION: `{version}`",
            f"- release/VERSION: `{release_version}`",
            f"- Release notes file: `{release_notes_rel}`",
            "",
        ]
    )


def _check_workflows(problems: list[str], lines: list[str]) -> None:
    workflow_dir = REPO_ROOT / ".github" / "workflows"
    canonical = workflow_dir / "ci.yml"
    lint_tests = workflow_dir / "lint-and-tests.yml"

    if not canonical.exists():
        problems.append("canonical workflow .github/workflows/ci.yml is missing")
    else:
        try:
            parsed = yaml.safe_load(canonical.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                problems.append("ci.yml does not parse to a YAML mapping")
        except Exception as exc:
            problems.append(f"ci.yml failed YAML parse: {exc}")

    if lint_tests.exists():
        try:
            raw = lint_tests.read_text(encoding="utf-8")
            if raw.lstrip().startswith("```") or raw.lstrip().startswith("---\n\n###"):
                problems.append("lint-and-tests.yml still contains markdown/document wrapper")
            parsed = yaml.safe_load(raw)
            if not isinstance(parsed, dict):
                problems.append("lint-and-tests.yml does not parse to a YAML mapping")
        except Exception as exc:
            problems.append(f"lint-and-tests.yml failed YAML parse: {exc}")

    lines.extend(
        [
            "## Workflow Check",
            "",
            f"- Canonical workflow present: `{canonical.exists()}`",
            f"- Optional lint-and-tests workflow present: `{lint_tests.exists()}`",
            "",
        ]
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_hash_manifests(problems: list[str], lines: list[str]) -> None:
    hash_dir = REPO_ROOT / "hashes"
    manifests = sorted(hash_dir.glob("SHA256SUMS*.txt"))
    checked = 0

    for manifest in manifests:
        raw = manifest.read_text(encoding="utf-8", errors="replace").splitlines()
        for row in raw:
            line = row.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) != 2:
                problems.append(f"{manifest.relative_to(REPO_ROOT)} has malformed row")
                continue
            expected_sha, relpath = parts
            target = REPO_ROOT / relpath.strip()
            if not target.exists():
                problems.append(f"{manifest.relative_to(REPO_ROOT)} references missing file {relpath.strip()}")
                continue
            actual_sha = _sha256_file(target)
            checked += 1
            if actual_sha.lower() != expected_sha.lower():
                problems.append(f"{manifest.relative_to(REPO_ROOT)} is stale for {relpath.strip()}")

    lines.extend(
        [
            "## Hash Manifests",
            "",
            f"- Checked entries: `{checked}`",
            "",
        ]
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Check public release safety for the repository.")
    ap.add_argument("--expected-tag", default=DEFAULT_EXPECTED_TAG, help="Expected stable tag/version marker.")
    ap.add_argument("--report-out", default=str(DEFAULT_REPORT), help="Markdown report path.")
    args = ap.parse_args()

    expected_tag = str(args.expected_tag or DEFAULT_EXPECTED_TAG).strip()
    report_out = Path(args.report_out)
    problems: list[str] = []
    lines: list[str] = [
        "# Public Release Safety Report",
        "",
        f"- Expected tag: `{expected_tag}`",
        f"- HEAD: `{_git_output('rev-parse', 'HEAD')}`",
        "",
    ]

    _check_privacy(expected_tag, problems, lines)
    _check_forbidden_root_files(problems, lines)
    _check_release_truth(expected_tag, problems, lines)
    _check_workflows(problems, lines)
    _check_hash_manifests(problems, lines)

    lines.extend(["## Verdict", ""])
    if problems:
        lines.append("- FAIL")
        lines.append("")
        lines.append("## Blockers")
        lines.append("")
        for problem in problems:
            lines.append(f"- {problem}")
    else:
        lines.append("- PASS")

    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": not problems,
                "expected_tag": expected_tag,
                "problem_count": len(problems),
                "report_out": str(report_out),
            },
            ensure_ascii=True,
        )
    )
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
