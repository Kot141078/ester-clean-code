# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


EXIT_OK = 0
EXIT_BASELINE_CREATED = 2
EXIT_FAIL_REACHABLE = 3
EXIT_FAIL_INCREASE = 4
EXIT_FAIL_ALLOWLIST = 5

_TRUE_VALUES = {"1", "true", "yes", "on", "y"}


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in _TRUE_VALUES


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"jsonl not found: {path}")
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            s = line.strip()
            if not s:
                continue
            try:
                row = json.loads(s)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {idx}: {exc}") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_kind: Dict[str, int] = {}
    reachable = 0
    for row in rows:
        kind = str(row.get("stub_kind") or "unknown")
        by_kind[kind] = by_kind.get(kind, 0) + 1
        if bool(row.get("reachable")):
            reachable += 1
    return {
        "total_stubs": len(rows),
        "reachable_stubs": reachable,
        "by_kind": dict(sorted(by_kind.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


def _default_baseline_payload(summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "created_at": int(time.time()),
        "total_stubs": int(summary.get("total_stubs") or 0),
        "reachable_stubs": int(summary.get("reachable_stubs") or 0),
        "by_kind": dict(summary.get("by_kind") or {}),
    }


def _load_baseline(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"baseline must be JSON object: {path}")
    return data


def _write_baseline(path: Path, summary: Dict[str, Any]) -> None:
    payload = _default_baseline_payload(summary)
    _write_json_atomic(path, payload)


def _write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{int(time.time() * 1000)}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        # Some Windows ACL setups disallow atomic replace in-place. Keep gate usable with direct write fallback.
        path.write_text(tmp.read_text(encoding="utf-8"), encoding="utf-8")
        try:
            tmp.unlink()
        except Exception:
            pass


def _normalize_allowlist_entries(raw: Any) -> Tuple[List[Dict[str, str]], List[str]]:
    issues: List[str] = []
    entries: List[Dict[str, str]] = []
    if raw is None:
        return entries, issues
    if isinstance(raw, dict):
        raw_items = raw.get("allow") if isinstance(raw.get("allow"), list) else raw.get("entries")
    else:
        raw_items = raw
    if raw_items is None:
        return entries, issues
    if not isinstance(raw_items, list):
        raise ValueError("allowlist must be a list or object with list field allow/entries")
    for idx, item in enumerate(raw_items):
        if isinstance(item, str):
            pattern = item.strip()
            if not pattern:
                continue
            entries.append({"pattern": pattern, "status": "legacy"})
            continue
        if not isinstance(item, dict):
            issues.append(f"entry[{idx}] has unsupported type")
            continue
        pattern = str(item.get("path") or item.get("pattern") or "").strip()
        status = str(item.get("status") or item.get("mode") or item.get("kind") or "").strip().lower()
        if not pattern:
            issues.append(f"entry[{idx}] has empty path/pattern")
            continue
        entries.append({"pattern": pattern, "status": status or "legacy"})
    return entries, issues


def _load_allowlist(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    if not path.exists():
        return [], []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _normalize_allowlist_entries(raw)


def _allowlist_violations(rows: List[Dict[str, Any]], entries: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    if not entries:
        return []
    allowed_statuses = {"legacy", "quarantine"}
    problems: List[Dict[str, Any]] = []
    for row in rows:
        path = str(row.get("path") or "")
        if not path:
            continue
        matches = [entry for entry in entries if fnmatch.fnmatch(path, entry["pattern"])]
        if not matches:
            continue
        if any(m.get("status") in allowed_statuses for m in matches):
            continue
        problems.append(
            {
                "path": path,
                "symbol": str(row.get("symbol") or ""),
                "stub_kind": str(row.get("stub_kind") or ""),
                "matched_allowlist": matches,
            }
        )
    return problems


def _print(payload: Dict[str, Any], quiet: bool) -> None:
    if quiet:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="Offline gate for stubs regressions.")
    ap.add_argument("--jsonl", default="data/reports/stubs_kill_list.jsonl")
    ap.add_argument("--baseline", default="docs/stubs_baseline.json")
    ap.add_argument("--allowlist", default="docs/stubs_allowlist.json")
    ap.add_argument("--fail-on-reachable", default="1")
    ap.add_argument("--fail-on-increase", default="1")
    ap.add_argument("--ratchet", default="0")
    ap.add_argument("--quiet", default="0")
    args = ap.parse_args(argv)

    quiet = _as_bool(args.quiet)
    fail_on_reachable = _as_bool(args.fail_on_reachable)
    fail_on_increase = _as_bool(args.fail_on_increase)
    ratchet = _as_bool(args.ratchet)

    jsonl_path = Path(str(args.jsonl)).resolve()
    baseline_path = Path(str(args.baseline)).resolve()
    allowlist_path = Path(str(args.allowlist)).resolve()

    rows = _load_jsonl(jsonl_path)
    summary = _summary(rows)
    baseline = _load_baseline(baseline_path)
    allowlist_entries, allowlist_issues = _load_allowlist(allowlist_path)
    allowlist_failures = _allowlist_violations(rows, allowlist_entries)

    payload: Dict[str, Any] = {
        "ok": True,
        "status": "ok",
        "jsonl": str(jsonl_path),
        "baseline": str(baseline_path),
        "allowlist": str(allowlist_path),
        "summary": summary,
        "baseline_created": False,
        "baseline_updated": False,
        "baseline_old_total": None,
        "baseline_new_total": None,
        "allowlist_issues": allowlist_issues,
        "allowlist_matches": len(allowlist_entries),
        "allowlist_failures": allowlist_failures[:20],
    }

    if baseline is None:
        _write_baseline(baseline_path, summary)
        payload["ok"] = True
        payload["status"] = "baseline_created"
        payload["baseline_created"] = True
        payload["baseline_new_total"] = int(summary.get("total_stubs") or 0)
        payload["baseline_total_stubs"] = int(summary.get("total_stubs") or 0)
        payload["total_delta"] = 0
        _print(payload, quiet)
        return EXIT_BASELINE_CREATED

    baseline_total = int(baseline.get("total_stubs") or 0)
    current_total = int(summary.get("total_stubs") or 0)
    current_reachable = int(summary.get("reachable_stubs") or 0)

    payload["baseline_old_total"] = baseline_total
    payload["baseline_new_total"] = baseline_total

    if fail_on_reachable and current_reachable > 0:
        payload["baseline_total_stubs"] = baseline_total
        payload["total_delta"] = current_total - baseline_total
        payload["ok"] = False
        payload["status"] = "fail_reachable"
        payload["error"] = f"reachable_stubs={current_reachable} > 0"
        _print(payload, quiet)
        return EXIT_FAIL_REACHABLE

    if fail_on_increase and current_total > baseline_total:
        payload["baseline_total_stubs"] = baseline_total
        payload["total_delta"] = current_total - baseline_total
        payload["ok"] = False
        payload["status"] = "fail_increase"
        payload["error"] = f"total_stubs increased from {baseline_total} to {current_total}"
        _print(payload, quiet)
        return EXIT_FAIL_INCREASE

    if allowlist_failures or allowlist_issues:
        payload["ok"] = False
        payload["status"] = "fail_allowlist"
        payload["error"] = "allowlist contains non-legacy/quarantine matches or malformed entries"
        _print(payload, quiet)
        return EXIT_FAIL_ALLOWLIST

    if ratchet and current_total < baseline_total:
        _write_baseline(baseline_path, summary)
        payload["baseline_updated"] = True
        payload["baseline_new_total"] = current_total
        baseline_total = current_total

    payload["baseline_total_stubs"] = baseline_total
    payload["total_delta"] = current_total - baseline_total
    _print(payload, quiet)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
